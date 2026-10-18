"""召唤式守护进程: 低配机上把"每次都重付一遍的启动开销"摊到一次.

为什么要它: gitx 是 Python 写的, 每条命令都要重新解释一遍 typer / rich 那一堆模块
(低配机 / 机械盘上约 1-2 秒, 占了 `gitx status` 这类命令的大半耗时)。开启 `daemon = true`
后, 运行任何 gitx 命令时若发现后台没有守护进程, 就顺手拉起一个: 它先把这些重模块导入好,
之后每条命令把"参数 + 工作目录 + 标准输入输出"交给它, 由它 **fork 出一个已经预热的子进程**
来执行 —— fork 出来的是预加载过的内存副本, 因此省掉重复导入, 而每条命令仍跑在自己的进程里
(状态不会互相污染, Ctrl+C 也只影响当次命令)。

设计取舍:
  - Unix 域套接字 (~/.cache/gitx/daemon.sock), 不占端口、不监听网络;
  - 用 SCM_RIGHTS 把客户端 stdin/stdout/stderr 传过去, 所以交互式命令 (选择器 / 确认 /
    进度条) 与终端配色照常工作, 输出顺序也不变;
  - 每个请求 fork 一个子进程执行: 隔离 + 预热兼得, 不必操心并发与残留状态;
  - 空闲超过 daemon_idle 秒自己退出 (不留常驻进程), 也可 `gitx daemon stop`;
  - 版本不一致 (刚升级) / 连不上 / 平台不支持 → 静默回退本地执行, 功能永远不受影响。
"""

from __future__ import annotations

import array
import contextlib
import importlib
import json
import os
import socket
import struct
import sys
import time
from pathlib import Path
from typing import Any

# 预热清单: 这些导入就是"启动慢"的来源, 守护进程先替命令行导好
WARMUP = ("typer", "rich.console", "rich.table", "rich.text", "rich.markup", "rich.cells",
          "rich.panel", "rich.progress", "rich.prompt", "prompt_toolkit", "questionary",
          "gitx.console", "gitx.config", "gitx.dispatch", "gitx.cli",
          "gitx.hub", "gitx.ghrepo", "gitx.repo", "gitx.branch")

_SOCK = socket.SOCK_STREAM
_INT = array.array("i").itemsize


# 守护进程自己(以及它的 serve 进程)带着这个环境变量跑, 入口据此不再重复路由
IN_DAEMON = "GITX_IN_DAEMON"


def in_daemon() -> bool:
    return os.environ.get(IN_DAEMON) == "1"


def log_path() -> Path:
    """守护进程的日志 (起不来时看它)."""
    return _log_path()


def _log_path() -> Path:
    from . import config

    return config.cache_dir() / "daemon.log"


def _fail_path() -> Path:
    from . import config

    return config.cache_dir() / "daemon.fail"


def socket_path() -> Path:
    from . import config

    return config.cache_dir() / "daemon.sock"


def enabled() -> bool:
    """配置里 daemon = true 才启用 (默认关闭, 不影响既有行为)."""
    from . import config

    with contextlib.suppress(Exception):
        return bool(config.load().get("daemon"))
    return False


def _idle_seconds() -> int:
    from . import config

    with contextlib.suppress(Exception):
        return max(1, int(config.load().get("daemon_idle", 300)))
    return 300


def _own_version() -> str:
    from . import __version__

    return __version__


def _probe(path: Path, timeout: float = 0.05) -> bool:
    """套接字还能连上 = 守护进程活着."""
    sock = socket.socket(socket.AF_UNIX, _SOCK)
    sock.settimeout(timeout)
    try:
        sock.connect(str(path))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def running() -> bool:
    return _probe(socket_path())


# ---------------------------------------------------------------- 控制命令 (快速通道)

# `gitx daemon ...` 是"管守护进程自己"的命令, 必须本地跑 (交给守护进程执行会死锁: 它单线程
# 收请求, 正等着这个子进程结束, 而子进程在等它回 stop 的应答)。既然跑在本地, 就别导入
# typer / rich —— 控制命令该是秒回的。所以这里自己读配置、自己上色, 只依赖标准库。

_RESET = "\033[0m"


def _colors() -> bool:
    """快速通道要不要上色 (看 NO_COLOR / FORCE_COLOR / 配置 color)."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if not sys.stdout.isatty():
        return False
    return str(_fast_config("color", "auto")).lower() != "never"


def _fast_config(key: str, default: Any) -> Any:
    """直接读 config.toml, 不导入 config 模块 (它连带 rich, 而快速通道要避免的正是这个)."""
    root = os.environ.get("XDG_CONFIG_HOME")
    path = (Path(root) if root else Path.home() / ".config") / "gitx" / "config.toml"
    with contextlib.suppress(OSError, ValueError, ImportError):
        import tomllib

        with open(path, "rb") as handle:
            return tomllib.load(handle).get(key, default)
    return default


def _say(text: str, style: str = "") -> None:
    """快速通道的打印 (style: ok / warn / info / dim)."""
    codes = {"ok": "\033[1;32m", "warn": "\033[1;33m", "info": "\033[32m",
             "step": "\033[36m", "dim": "\033[90m"}
    prefix = {"ok": "[ok] ", "warn": "[!] ", "info": "[+] ", "step": "[*] "}.get(style, "")
    if style and _colors():
        print(f"{codes.get(style, '')}{prefix}{text}{_RESET}")
    else:
        print(f"{prefix}{text}")


def control(argv: list[str]) -> int:
    """`gitx daemon [status|start|stop|restart]`: 不导入 typer / rich 的快速通道."""
    what = argv[0] if argv else "status"
    if what in ("-h", "--help"):
        print("用法: gitx daemon [status|start|stop|restart|bench]\n"
              "  status   看配置与后台进程 (默认)\n"
              "  start    立刻召唤一个守护进程 (之后命令由它执行)\n"
              "  stop     让它退出 (不留常驻进程)\n"
              "  restart  停掉再召唤 (升级后想立刻用新代码)\n"
              "  bench    实测有/没有守护进程的启动耗时 (这个要用 typer, 会慢一点)")
        return 0
    if what == "stop":
        if stop():
            _say("守护进程已退出", "ok")
        else:
            _say("守护进程本来就没在跑", "info")
        return 0
    if what in ("start", "restart"):
        if what == "restart" and stop():
            _say("旧进程已退出, 正在重新召唤 ...", "info")
        if running():
            _say("守护进程已经在跑了", "info")
            return 0
        _say("召唤守护进程 ...", "step")
        if spawn(force=True, wait=8.0):
            _say(f"守护进程已就绪: {socket_path()}", "ok")
            return 0
        _say("守护进程没能启动 (原因见 ~/.cache/gitx/daemon.log)", "warn")
        _say("不加守护进程也能用, 只是每条命令都要重付一次导入开销")
        return 1
    if what != "status":
        _say(f"未知子命令: {what} (可用: status / start / stop / restart / bench)", "warn")
        return 2
    on = bool(_fast_config("daemon", False))
    alive = running()
    palette = str(_fast_config("palette", "auto"))
    actual = "terminal" if (palette == "auto" and on) else ("mocha" if palette == "auto" else palette)
    print(f"实例 {socket_path()}")
    print(f"配置 daemon      : {'已开启' if on else '未开启 (gitx config set daemon true 打开)'}")
    print(f"后台进程         : {'在跑' if alive else '没有在跑'}")
    print(f"空闲退出         : {_idle_seconds()} 秒没命令就自己退出")
    print(f"配色 palette     : {palette} -> 实际用 {actual}")
    if on and not alive:
        _say("下一条 gitx 命令会自动召唤它 (也可以 gitx daemon start 立刻召唤)", "info")
    elif not on:
        _say("开启后: 第一条命令顺手召唤预热进程, 之后的命令由它 fork 执行, 省掉重复导入",
             "info")
    return 0


# ---------------------------------------------------------------- 启停

COOLDOWN = 60.0  # 召唤失败后的冷却秒数 (免得每条命令都白等一次)


def spawn(*, wait: float = 1.5, force: bool = False) -> bool:
    """拉起守护进程 (已在跑返回 True); 起不来返回 False, 调用方照常本地执行.

    用 `python -m gitx daemon serve` 起, 保证与命令行同一套解释器与依赖;
    双重 fork + setsid, 因此不会跟着终端一起被 Ctrl+C 带走。
    起不来时留一个冷却标记 (60 秒内不再试), 于是后续命令不会每条都白等一次;
    `gitx daemon start/restart` 用 force=True 绕过冷却, 手动再试。
    """
    path = socket_path()
    if _probe(path):
        return True
    if not hasattr(os, "fork") or sys.platform == "win32":  # 非 POSIX: 不支持
        return False
    mark = _fail_path()
    if not force and mark.exists():
        with contextlib.suppress(OSError):
            if time.time() - mark.stat().st_mtime < COOLDOWN:
                return False  # 刚失败过: 别再等
    with contextlib.suppress(OSError):
        mark.unlink()
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
    try:
        pid = os.fork()
    except OSError:
        return False
    if pid > 0:
        deadline = time.time() + wait
        while time.time() < deadline:
            if _probe(path):
                return True
            time.sleep(0.05)
        with contextlib.suppress(OSError):
            mark.touch()  # 冷却: 这段时间内别再召唤
        return False
    try:  # 第一层子进程: 脱离会话与终端, 然后 exec 成守护进程
        os.setsid()
        if os.fork() > 0:
            os._exit(0)
        devnull = os.open(os.devnull, os.O_RDWR)
        os.dup2(devnull, 0)
        # stdout/stderr 落到日志文件: 守护进程起不来时, 这里能看出原因
        log = os.open(str(_log_path()), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        os.dup2(log, 1)
        os.dup2(log, 2)
        os.environ[IN_DAEMON] = "1"
        os.execv(sys.executable, [sys.executable, "-m", "gitx", "daemon", "serve"])
    except BaseException:
        os._exit(1)


def stop(*, wait: float = 2.0) -> bool:
    """让守护进程退出 (没在跑返回 False); wait 秒内等它把套接字交出来."""
    path = socket_path()
    if not _probe(path):
        return False
    with contextlib.suppress(OSError):
        _roundtrip(path, {"cmd": "quit"}, None)
    with contextlib.suppress(OSError):
        _fail_path().unlink()  # 手动停过之后, 允许立刻重新召唤
    deadline = time.time() + wait
    while time.time() < deadline and _probe(path):
        time.sleep(0.05)  # 等它真的走 (否则 restart 会以为"已经有一个在跑")
    return True


# ---------------------------------------------------------------- 客户端

def _roundtrip(path: Path, payload: dict, fds: list[int] | None) -> dict:
    """发一条请求并等回复 (可选地带上要传过去的 fd)."""
    body = json.dumps(payload).encode("utf-8")
    frame = struct.pack("!I", len(body)) + body
    sock = socket.socket(socket.AF_UNIX, _SOCK)
    try:
        sock.settimeout(30)  # 兜底: 绝不允许"等三分钟还没退出"
        sock.connect(str(path))
        if fds:
            right = array.array("i", fds)
            sock.sendmsg([frame], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, right)])
        else:
            sock.sendall(frame)
        size = struct.unpack("!I", _recv(sock, 4))[0]
        return json.loads(_recv(sock, size).decode("utf-8"))
    finally:
        sock.close()


def run(argv: list[str], *, cwd: str | None = None) -> int | None:
    """把这条命令交给守护进程执行; 返回退出码, 任何异常都返回 None (调用方自己跑).

    协议: 发请求 -> 守护进程先回一个 {"pid"}(它 fork 出来的子进程) -> 再回 {"code"}。
    中间这段是为了 Ctrl+C: 子进程在守护进程的会话里, 收不到终端的 SIGINT, 因此客户端
    收到信号时自己把它转发给那个 pid, 交互式命令的中断行为与本地执行一致。
    环境变量也一并送过去 (守护进程可能是别的命令启的, 其环境未必和本次一样)。
    """
    path = socket_path()
    if not _probe(path):
        return None
    fds: list[int] | None = None
    with contextlib.suppress(AttributeError, ValueError, OSError):
        fds = [sys.stdin.fileno(), sys.stdout.fileno(), sys.stderr.fileno()]
    payload = {"cmd": "run", "argv": list(argv), "cwd": cwd or os.getcwd(),
               "env": dict(os.environ), "version": _own_version()}
    sock = socket.socket(socket.AF_UNIX, _SOCK)
    try:
        sock.connect(str(path))
        frame = json.dumps(payload).encode("utf-8")
        body = struct.pack("!I", len(frame)) + frame
        if fds:
            right = array.array("i", fds)
            sock.sendmsg([body], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, right)])
        else:
            sock.sendall(body)
        first = _read_reply(sock)
        if first.get("cmd") == "fallback":
            return None
        child = first.get("pid")
        restore = _forward_signals(child if isinstance(child, int) else None)
        try:
            second = _read_reply(sock)
        finally:
            restore()
        code = second.get("code")
        return int(code) if isinstance(code, int) else None
    except (OSError, ValueError):
        return None
    finally:
        sock.close()


def _read_reply(sock: socket.socket) -> dict:
    size = struct.unpack("!I", _recv(sock, 4))[0]
    return json.loads(_recv(sock, size).decode("utf-8"))


def _forward_signals(child: int | None) -> Any:
    """把 SIGINT / SIGTERM 转发给守护进程里的那个子进程; 返回"恢复现场"的函数."""
    import signal

    if child is None:
        return lambda: None
    previous: dict[int, Any] = {}

    def forward(signum: int, _frame: Any) -> None:
        with contextlib.suppress(OSError):
            os.kill(child, signum)

    for name in ("SIGINT", "SIGTERM", "SIGHUP"):
        sig = getattr(signal, name, None)
        if sig is not None:
            with contextlib.suppress(OSError, ValueError):
                previous[sig] = signal.signal(sig, forward)

    def restore() -> None:
        for sig, handler in previous.items():
            with contextlib.suppress(OSError, ValueError):
                signal.signal(sig, handler)

    return restore


def _recv(sock: socket.socket, size: int) -> bytes:
    buf = b""
    while len(buf) < size:
        chunk = sock.recv(size - len(buf))
        if not chunk:
            raise OSError("连接被对端关闭")
        buf += chunk
    return buf


# ---------------------------------------------------------------- 服务端

def _warmup() -> None:
    """把重模块先导入一遍 (这正是每条命令原本要重付的开销)."""
    for name in WARMUP:
        with contextlib.suppress(Exception):
            importlib.import_module(name)


def _run_child(argv: list[str], cwd: str, fds: list[int], env: dict, on_start: Any) -> int:
    """fork 一个预热好的子进程执行命令, 并把退出码带回来.

    on_start(pid) 在 fork 之后立刻调用 —— 让客户端知道这个 pid, 以便把 Ctrl+C 转发过来。
    """
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:  # 子进程: 继承已导入的模块, 因此省掉重复导入
        os.close(read_fd)
        code = 1
        try:
            for target, fd in enumerate(fds[:3]):
                with contextlib.suppress(OSError):
                    os.dup2(fd, target)
            if env:  # 用本次命令自己的环境 (守护进程可能是别的命令启的)
                os.environ.clear()
                os.environ.update({str(k): str(v) for k, v in env.items()})
            with contextlib.suppress(OSError):
                if cwd and os.path.isdir(cwd):
                    os.chdir(cwd)
            # fd 已经是客户端的终端了, 但 rich 的控制台还记着守护进程自己的"没有终端":
            # 重建一次, 颜色与终端宽度才会对 (否则表现为掉色 + 按 80 列折行)
            from . import console as console_module

            console_module.rebind()
            sys.argv = ["gitx", *argv]
            _run_inprocess(argv)
            code = 0
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        except KeyboardInterrupt:
            code = 130
        except BaseException:
            import traceback

            traceback.print_exc()
            code = 1
        with contextlib.suppress(OSError):
            os.write(write_fd, struct.pack("!i", code))
        os._exit(code)
    os.close(write_fd)
    on_start(pid)
    raw = _read_pipe(read_fd)
    os.close(read_fd)
    os.waitpid(pid, 0)
    return struct.unpack("!i", raw)[0] if len(raw) == 4 else 0


def _run_inprocess(argv: list[str]) -> None:
    """在守护进程的子进程里跑一条命令 (typer 应用入口)."""
    from .cli import main as run_cli

    run_cli(argv)


def _read_pipe(fd: int) -> bytes:
    buf = b""
    while len(buf) < 4:
        chunk = os.read(fd, 4 - len(buf))
        if not chunk:
            break
        buf += chunk
    return buf


def _reply(payload: dict) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    return struct.pack("!I", len(body)) + body


def _handle(conn: socket.socket, payload: dict, fds: list[int]) -> bool:
    """处理一条请求; 返回 False 表示守护进程该退出了."""
    cmd = str(payload.get("cmd") or "")
    if cmd == "quit":
        conn.sendall(_reply({"cmd": "bye"}))
        return False
    if cmd == "ping":
        conn.sendall(_reply({"cmd": "pong", "version": _own_version()}))
        return True
    if (cmd != "run" or payload.get("version") != _own_version()
            or not hasattr(os, "fork")):
        # 版本不同 (刚升级过) 就让客户端自己跑, 别用旧模块执行新命令
        conn.sendall(_reply({"cmd": "fallback"}))
        return True
    argv = [str(a) for a in payload.get("argv") or []]
    env = payload.get("env") if isinstance(payload.get("env"), dict) else {}
    code = _run_child(argv, str(payload.get("cwd") or ""), fds, env,
                      lambda pid: conn.sendall(_reply({"pid": pid})))
    conn.sendall(_reply({"code": code}))
    return True


def _lock_path() -> Path:
    from . import config

    return config.cache_dir() / "daemon.lock"


def _note(message: str) -> None:
    """写一行带时间戳的日志 (守护进程起不来时, 这是唯一的线索)."""
    import datetime

    with contextlib.suppress(OSError):
        _log_path().parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%m-%d %H:%M:%S")
        with open(_log_path(), "a", encoding="utf-8") as handle:
            handle.write(f"[{stamp}] {message}\n")


def _sock_inode(path: Path) -> int:
    with contextlib.suppress(OSError):
        return path.stat().st_ino
    return -1


def _take_lock() -> Any:
    """拿独占锁: 同一时刻只允许一个守护进程 (拿不到 = 已经有一个在跑)."""
    import fcntl

    path = _lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "w", encoding="utf-8")  # noqa: SIM115 - 故意持有到进程结束
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def serve() -> None:
    """守护进程主循环: 预热 -> 建套接字 -> 收请求 -> 空闲超时退出."""
    _note("serve 启动")
    lock = _take_lock()
    if lock is None:  # 已经有一个守护进程在跑: 安静退出, 不抢套接字
        _note("已有守护进程, 本次退出")
        return
    path = socket_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        path.unlink()
    _warmup()
    server = socket.socket(socket.AF_UNIX, _SOCK)
    try:
        server.bind(str(path))
    except OSError as exc:
        _note(f"绑定套接字失败: {exc}")
        return
    inode = _sock_inode(path)
    server.listen(8)
    _note(f"就绪: {path}")
    idle = _idle_seconds()
    server.settimeout(min(5, idle))
    last = time.time()
    try:
        while True:
            try:
                conn, _ = server.accept()
            except TimeoutError:
                if time.time() - last >= idle:
                    break  # 长时间没人用: 自己退出, 不留常驻进程
                continue
            except OSError:
                break
            keep = _serve_conn(conn)
            last = time.time()
            if not keep:
                break
    finally:
        with contextlib.suppress(OSError):
            server.close()
        # 只删自己绑的那个套接字: 万一已经有后继者接管了这个路径, 别把它删掉
        if _sock_inode(path) == inode:
            with contextlib.suppress(OSError):
                path.unlink()


def _serve_conn(conn: socket.socket) -> bool:
    fds: list[int] = []
    with conn:
        try:
            head, ancdata, _, _ = conn.recvmsg(4, socket.CMSG_LEN(3 * _INT))
        except OSError:
            return True
        for level, kind, data in ancdata:
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                usable = len(data) - len(data) % _INT
                fds = list(array.array("i", data[:usable]))
        try:
            size = struct.unpack("!I", head)[0]
            payload = json.loads(_recv(conn, size).decode("utf-8"))
        except (OSError, struct.error, ValueError):
            _close_all(fds)
            return True
        try:
            return _handle(conn, payload, fds)
        finally:
            _close_all(fds)


def _close_all(fds: list[int]) -> None:
    for fd in fds:
        with contextlib.suppress(OSError):
            os.close(fd)