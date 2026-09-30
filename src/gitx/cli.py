"""gitx 命令行入口: 分发、配置、加速、透传."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import urllib.request

from . import __version__, accel, config, console, download, gitcmd, github, release, repo, sync

USAGE = f"""{'=' * 58}
{console.CYAN}gitx{console.NC} —— 给中国人用的 GitHub 加速与同步工具 v{__version__}
{'=' * 58}

{console.GREEN}下载 (默认走加速, 加速源: v6.gh-proxy.org){console.NC}
  gitx <github-url> [目标路径] [选项]
    仓库:     https://github.com/owner/repo
    文件夹:   https://github.com/owner/repo/tree/分支/路径
    文件:     https://github.com/owner/repo/blob/分支/路径/文件
    发布页:   https://github.com/owner/repo/releases[/tag/标签]
    发布附件: https://github.com/owner/repo/releases/download/标签/文件名
  gitx clone <github-url> [目标路径] [选项]
  gitx release <owner/repo|发布页链接> [--tag 标签] [--asset 名字] [--list] [--source] [-o 目录]

{console.GREEN}同步{console.NC}
  gitx push [备注] [to <仓库地址>] [-f] [-m 信息] [-b 分支] [-C 路径]
  gitx pull [路径] [--rebase]
  gitx sync [备注] [--merge] [-f] [-C 路径]        先拉后推, 一步到位 (默认变基)

{console.GREEN}仓库{console.NC}
  gitx init [目录] [git init 参数] [--no-zh]       初始化: 分支 main + 中文友好配置
  gitx info [路径]                                 仓库概览 (状态/领先落后/最近提交/加速)
  gitx undo [次数] [--soft|--mixed|--hard] [-y]    撤销最近 N 次提交

{console.GREEN}加速管理 (拉取走加速, 推送直连){console.NC}
  gitx proxy               查看加速状态
  gitx proxy auto          自动测速, 选用最快的加速源
  gitx proxy on [加速源]   开启加速 (默认 v6)
  gitx proxy off           关闭加速 (直连)
  gitx proxy default       恢复默认加速源 v6
  gitx proxy set <url>     使用自定义加速源 (如 https://gh-proxy.com)
  gitx proxy http [地址|off]  设置 git 的 HTTP(S) 代理 (本地代理/公司网络)
  gitx proxy install [--local]  写 git insteadOf 规则, 普通 git 命令也走加速
  gitx proxy uninstall     移除 insteadOf 规则
  gitx proxy test          测试当前加速源连通性

{console.GREEN}配置{console.NC}
  gitx config                查看配置
  gitx config set <键> <值>    键: proxy / depth / branch / message
  gitx config zh [--global]  一键中文友好配置 (文件名不转义, 日志 UTF-8)
  gitx config reset          恢复默认
  gitx doctor                环境自检 (git/gh/仓库/加速源/编码)

{console.GREEN}其它 git 子命令直接透传{console.NC}
  gitx status / gitx log --oneline / gitx diff / gitx commit -m ...
  (原生 git init 用: gitx git init)

{console.GREEN}常用选项{console.NC}
  --proxy <加速源>   本次使用指定加速源 (v6 / gh-proxy / https://...)
  --no-proxy         本次直连
  --branch <分支>    指定分支
  --depth <N>        克隆深度 (0 = 完整克隆, 默认 1)

{console.DIM}环境变量: GITX_PROXY=off|v6|gh-proxy|https://...  全局默认加速源{console.NC}
"""


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(USAGE)
        return
    first = argv[0]
    if first in ("-h", "--help", "help"):
        print(USAGE)
        return
    if first in ("-V", "--version", "version"):
        print(f"gitx {__version__}")
        return
    if first == "git":
        _passthrough(argv[1:])
        return
    if first == "proxy":
        cmd_proxy(argv[1:])
        return
    if first == "config":
        cmd_config(argv[1:])
        return
    if first == "doctor":
        cmd_doctor(argv[1:])
        return
    if first == "clone":
        cmd_download(argv[1:])
        return
    if first == "release":
        release.cmd(argv[1:])
        return
    if first == "init":
        repo.init_cmd(argv[1:])
        return
    if first == "info":
        repo.info_cmd(argv[1:])
        return
    if first == "undo":
        repo.undo_cmd(argv[1:])
        return
    if first == "sync":
        sync.sync(argv[1:])
        return
    if first == "push":
        sync.push(argv[1:])
        return
    if first == "pull":
        sync.pull(argv[1:])
        return
    if _is_git_command(first):
        _passthrough(argv)
        return
    cmd_download(argv)


# ---------------------------------------------------------------- download

def cmd_download(argv: list[str]) -> None:
    no_proxy = False
    proxy_flag = None
    depth = None
    branch = ""
    list_only = False
    source = False
    asset = ""
    rest: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--no-proxy":
            no_proxy = True
        elif a == "--proxy" and i + 1 < len(argv):
            i += 1
            proxy_flag = argv[i]
        elif a in ("--depth",) and i + 1 < len(argv):
            i += 1
            try:
                depth = int(argv[i])
            except ValueError:
                console.error("--depth 必须是整数 (0 = 完整克隆)")
        elif a in ("-b", "--branch") and i + 1 < len(argv):
            i += 1
            branch = argv[i]
        elif a == "--list":
            list_only = True
        elif a == "--source":
            source = True
        elif a in ("-a", "--asset") and i + 1 < len(argv):
            i += 1
            asset = argv[i]
        elif a in ("-h", "--help"):
            console.info("用法: gitx <github-url> [目标路径] [--proxy 加速源] [--no-proxy] "
                         "[--branch 分支] [--depth N]\n"
                         "  发布页链接另支持: --list / --asset <名字> / --source")
            return
        else:
            rest.append(a)
        i += 1
    if not rest:
        console.error("缺少 GitHub 链接, 用法: gitx <github-url> [目标路径]")
    if len(rest) > 2:
        console.error(f"多余参数: {rest[2:]}")
    url, dest = rest[0], (rest[1] if len(rest) == 2 else "")
    try:
        info = github.parse_url(url)
    except ValueError as exc:
        console.error(f"{exc}\n提示: 其它 git 子命令可直接透传, 如 gitx status")
    prefix = config.active_proxy(proxy_flag, no_proxy)
    if info["mode"] in ("release", "asset"):
        release.run(info, dest or ".", prefix,
                    list_only=list_only, asset=asset, source=source)
        return
    item_name = os.path.basename(info["path"]) if info["path"] else info["repo"]
    target = dest or item_name
    _clear_dest(target)
    if depth is None:
        depth = int(config.load().get("depth", 1))
    download.download(url, target, prefix, depth, branch)
    console.done(f"完成! 已保存到: {target}")


def _clear_dest(dest: str) -> None:
    if os.path.lexists(dest):
        if not console.ask(f"目标已存在: {dest}, 要覆盖吗?", default=False):
            console.error("已取消")
        if os.path.isdir(dest) and not os.path.islink(dest):
            shutil.rmtree(dest)
        else:
            os.remove(dest)


# ---------------------------------------------------------------- proxy

def cmd_proxy(argv: list[str]) -> None:
    sub = argv[0] if argv else "status"
    cfg = config.load()
    if sub == "status":
        name = str(cfg.get("proxy", "v6"))
        try:
            prefix = accel.resolve(name)
        except ValueError:
            prefix = None
        if prefix:
            console.info(f"当前加速源: {name} ({prefix})")
        else:
            console.info("当前: 直连 (未加速)")
        installed = accel.installed_prefix()
        if installed:
            console.info(f"git 全局 insteadOf 规则: {installed} (普通 git 命令也走加速)")
        else:
            console.info("git insteadOf 规则: 未安装 (gitx 自身加速不受影响)")
        console.info(f"配置文件: {config.config_path()}")
        return
    if sub == "on":
        name = argv[1] if len(argv) > 1 else "v6"
        accel.resolve(name)  # 校验合法性
        config.save({**cfg, "proxy": name})
        console.done(f"已开启加速: {name}")
        return
    if sub == "off":
        config.save({**cfg, "proxy": "off"})
        console.done("已关闭加速 (直连)")
        return
    if sub == "default":
        config.save({**cfg, "proxy": "v6"})
        console.done("已恢复默认加速源: v6 (https://v6.gh-proxy.org)")
        return
    if sub == "set":
        if len(argv) < 2:
            console.error("用法: gitx proxy set <加速源|URL>")
        name = argv[1]
        accel.resolve(name)
        config.save({**cfg, "proxy": name})
        console.done(f"加速源已设为: {name}")
        return
    if sub == "install":
        scope = "--local" if "--local" in argv else "--global"
        name = str(cfg.get("proxy", "v6"))
        prefix = accel.resolve(name)
        if not prefix:
            console.error("当前是直连模式, 先: gitx proxy on")
        accel.install_rewrite(prefix, scope)
        config.save({**cfg, "installed_prefix": prefix, "installed_scope": scope})
        console.done(f"已写入 git {scope} insteadOf 规则: 普通 git 命令也走加速 {prefix}")
        return
    if sub == "uninstall":
        scope = "--local" if "--local" in argv else str(cfg.get("installed_scope", "--global"))
        prefix = str(cfg.get("installed_prefix", "")) or accel.resolve(cfg.get("proxy", "v6")) or ""
        if prefix:
            accel.uninstall_rewrite(prefix, scope)
        cfg.pop("installed_prefix", None)
        cfg.pop("installed_scope", None)
        config.save(cfg)
        console.done("已移除 insteadOf 规则")
        return
    if sub == "test":
        _proxy_test()
        return
    if sub == "auto":
        _proxy_auto()
        return
    if sub == "http":
        _proxy_http(argv[1:])
        return
    console.error(f"未知子命令: {sub} (可用: on / off / default / set / auto / http / install / uninstall / test / status)")


def _proxy_auto() -> None:
    """逐个测速并选用最快的加速源 (含直连)."""
    cfg = config.load()
    console.step("正在测速 (git 克隆端点, 越小越快)...")
    results: list[tuple[str, float]] = []
    for name, prefix in list(accel.PROVIDERS.items()) + [("off", None)]:
        ms, ok = accel.probe(prefix)
        label = f"{name} ({prefix})" if prefix else "直连 (off)"
        if ok:
            console.info(f"  {label:<44} {ms:7.0f} ms")
            results.append((name, ms))
        else:
            console.warn(f"  {label:<44} 不可达")
    if not results:
        console.error("所有加速源都不可达, 请检查网络 (gitx proxy test)")
    best = min(results, key=lambda item: item[1])[0]
    config.save({**cfg, "proxy": best})
    console.done(f"已选择最快: {best}" + (f" ({accel.PROVIDERS[best]})" if best in accel.PROVIDERS else " 直连"))


def _proxy_http(argv: list[str]) -> None:
    """设置/查看 git 的 HTTP(S) 代理 (本地代理软件或公司网络)."""
    scope = "--local" if "--local" in argv else "--global"
    args = [a for a in argv if not a.startswith("--local")]
    if not args or argv[0] in ("-h", "--help"):
        cur_http = gitcmd.capture(["git", "config", scope, "--get", "http.proxy"])[1]
        cur_https = gitcmd.capture(["git", "config", scope, "--get", "https.proxy"])[1]
        if cur_http or cur_https:
            console.info(f"git {scope} 代理: http.proxy={cur_http or '(未设置)'} | https.proxy={cur_https or '(未设置)'}")
        else:
            console.info(f"git {scope} 代理: 未设置")
        console.info("用法: gitx proxy http <地址>    如 gitx proxy http http://127.0.0.1:7890")
        console.info("      gitx proxy http off       取消代理")
        console.info("      gitx proxy http [--local] 查看当前仓库的代理")
        return
    addr = args[0]
    if addr in ("off", "none", "取消"):
        for key in ("http.proxy", "https.proxy"):
            subprocess.run(["git", "config", scope, "--unset-all", key], check=False, capture_output=True)
        console.done(f"已取消 git {scope} HTTP(S) 代理")
        return
    if not addr.startswith(("http://", "https://", "socks5://", "socks5h://")):
        console.error(f"代理地址应以 http:// 或 socks5:// 开头: {addr}")
    for key in ("http.proxy", "https.proxy"):
        subprocess.run(["git", "config", scope, key, addr], check=True)
    console.done(f"已设置 git {scope} 代理: {addr}")


def _proxy_test() -> None:
    name = str(config.load().get("proxy", "v6"))
    try:
        prefix = accel.resolve(name)
    except ValueError as exc:
        console.error(str(exc))
    if not prefix:
        console.info("当前为直连模式, 跳过测试 (gitx proxy on 开启加速)")
        return
    # git 克隆端点: 用 git ls-remote 真实探测
    rc, _ = gitcmd.capture(
        ["git", "ls-remote", "--symref", f"{prefix}/https://github.com/octocat/Hello-World.git", "HEAD"]
    )
    if rc == 0:
        console.done("git 克隆端点: 可达")
    else:
        console.warn("git 克隆端点: 失败 (git ls-remote)")
    for label, path in (
        ("raw", prefix + "/https://raw.githubusercontent.com/octocat/Hello-World/master/README"),
        ("api", prefix + "/https://api.github.com/repos/octocat/Hello-World"),
    ):
        try:
            with urllib.request.urlopen(path, timeout=10) as r:
                if r.status < 400:
                    console.done(f"{label}: HTTP {r.status} 可达")
                else:
                    console.warn(f"{label}: HTTP {r.status}")
        except Exception as exc:  # noqa: BLE001
            console.warn(f"{label}: 失败 ({exc})")


# ---------------------------------------------------------------- config

def cmd_config(argv: list[str]) -> None:
    cfg = config.load()
    sub = argv[0] if argv else "list"
    if sub == "list":
        for key, value in cfg.items():
            console.info(f"{key} = {value}")
        console.info(f"配置文件: {config.config_path()}")
        return
    if sub == "get":
        if len(argv) < 2:
            console.error("用法: gitx config get <键>")
        key = argv[1]
        console.info(f"{key} = {cfg.get(key, '')}")
        return
    if sub == "set":
        if len(argv) < 3:
            console.error("用法: gitx config set <键> <值>")
        key, value = argv[1], argv[2]
        if key not in ("proxy", "depth", "branch", "message"):
            console.error(f"未知配置键: {key} (可用: proxy / depth / branch / message)")
        if key == "proxy":
            accel.resolve(value)
        if key == "depth":
            try:
                int(value)
            except ValueError:
                console.error("depth 必须是整数")
        config.save({**cfg, key: value})
        console.done(f"{key} = {value}")
        return
    if sub == "reset":
        config.save(dict(config.DEFAULTS))
        console.done("配置已重置为默认")
        return
    if sub == "zh":
        scope = "--global" if "--global" in argv else "--local"
        if scope == "--local" and not gitcmd.is_repo("."):
            console.error("当前目录不是 git 仓库\n  全局设置请用: gitx config zh --global")
        changed = gitcmd.apply_zh_config(scope, ".")
        console.done(f"已写入 {scope} 中文友好配置: " + (", ".join(changed) if changed else "已是最新"))
        return
    console.error(f"未知子命令: {sub} (可用: list / get / set / zh / reset)")


# ---------------------------------------------------------------- doctor

def cmd_doctor(_argv: list[str] | None = None) -> None:
    console.info(f"gitx {__version__}")
    console.info(f"配置文件: {config.config_path()}")
    _, gitver = gitcmd.capture(["git", "--version"])
    console.info(f"git: {gitver or '未找到'}")
    gh = shutil.which("gh")
    gh_state = "未安装"
    if gh:
        gh_state = "已登录" if gitcmd.capture(["gh", "auth", "status"])[0] == 0 else "未登录"
    console.info(f"gh: {'已安装' if gh else '未安装'} | {gh_state}")
    if gitcmd.is_repo():
        origin = gitcmd.remote_url("origin")
        console.info(f"仓库: 是 | 分支: {gitcmd.current_branch() or '(无提交)'}" + (f" | origin: {origin}" if origin else ""))
    else:
        console.info("仓库: 否")
    console.step("测试加速源...")
    _proxy_test()
    quotepath = gitcmd.capture(["git", "config", "--global", "--get", "core.quotepath"])[1]
    if quotepath in ("false", "0", "off"):
        console.done("编码: core.quotepath=false (中文文件名正常显示)")
    else:
        console.warn("编码: 中文文件名会显示为 \\344\\270\\255 转义码, 建议: gitx config zh --global")


# ---------------------------------------------------------------- passthrough

_GIT_CMDS: set[str] | None = None


def _git_commands() -> set[str]:
    global _GIT_CMDS
    if _GIT_CMDS is None:
        cmds: set[str] = set()
        rc, out = gitcmd.capture(["git", "help", "-a"])
        if rc == 0:
            for line in out.splitlines():
                for tok in re.split(r"\s+", line.strip()):
                    if tok and not tok.startswith(("-", "(", "'")):
                        cmds.add(tok)
        _GIT_CMDS = cmds
    return _GIT_CMDS


def _is_git_command(name: str) -> bool:
    if not name or name.startswith("-"):
        return False
    return name in _git_commands()


def _passthrough(argv: list[str]) -> None:
    rc = subprocess.run(["git", *argv]).returncode
    sys.exit(rc)


if __name__ == "__main__":
    main()
