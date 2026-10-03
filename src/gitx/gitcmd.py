"""git 命令封装: 统一调用与解析."""

from __future__ import annotations

import re
import subprocess
from typing import Sequence

from . import accel, console

# 中文用户常踩的坑: 默认 core.quotepath=true 会把中文文件名显示成 \344\270\255 转义码
ZH_CONFIG: dict[str, str] = {
    "core.quotepath": "false",
    "i18n.commitEncoding": "utf-8",
    "i18n.logOutputEncoding": "utf-8",
    "gui.encoding": "utf-8",
}


def apply_zh_config(scope: str = "--local", path: str = ".") -> list[str]:
    """写入中文友好配置, 返回本次实际改动的键名."""
    rc, out = capture(["git", "-C", path, "config", scope, "--list"])
    current: dict[str, str] = {}
    if rc == 0:
        for line in out.splitlines():
            key, sep, value = line.partition("=")
            if sep:
                current[key.strip().lower()] = value
    changed: list[str] = []
    for key, value in ZH_CONFIG.items():
        if current.get(key.lower()) == value:
            continue
        subprocess.run(["git", "-C", path, "config", scope, key, value],
                       check=False, capture_output=True)
        changed.append(key)
    return changed


def run(args: Sequence[str]) -> subprocess.CompletedProcess:
    return subprocess.run([str(a) for a in args])


def capture(args: Sequence[str]) -> tuple[int, str]:
    try:
        r = subprocess.run([str(a) for a in args], capture_output=True, text=True)
    except FileNotFoundError:
        return 127, ""
    return r.returncode, (r.stdout or "").strip()


def ok(args: Sequence[str]) -> bool:
    """跑一条命令, 只关心成败 (输出丢弃); 命令不存在时视为失败."""
    try:
        return subprocess.run([str(a) for a in args], capture_output=True).returncode == 0
    except FileNotFoundError:
        return False


def run_capture(args: Sequence[str]) -> tuple[int, str]:
    """跑命令并返回 (退出码, 输出); stderr 优先 —— git 的说明都写在 stderr."""
    try:
        r = subprocess.run([str(a) for a in args], capture_output=True, text=True)
    except FileNotFoundError:
        return 127, "未找到命令"
    return r.returncode, (r.stderr or "").strip() or (r.stdout or "").strip()


def is_repo(path: str = ".") -> bool:
    return capture(["git", "-C", path, "rev-parse", "--is-inside-work-tree"])[0] == 0


def require_repo(path: str = ".") -> None:
    """不在仓库里就直接报错退出 (各命令的统一前置检查)."""
    if not is_repo(path):
        console.error(f"{path} 不是 git 仓库")


def require_commits(path: str = ".") -> None:
    require_repo(path)
    if not has_commits(path):
        console.error("仓库还没有提交 (gitx push 一次就有历史了)")


def current_branch(path: str = ".") -> str:
    _, out = capture(["git", "-C", path, "branch", "--show-current"])
    return out


def has_commits(path: str = ".") -> bool:
    return capture(["git", "-C", path, "rev-parse", "--verify", "HEAD"])[0] == 0


def remote_url(name: str = "origin", path: str = ".") -> str:
    _, out = capture(["git", "-C", path, "remote", "get-url", name])
    return out


def remote_push_url(name: str = "origin", path: str = ".") -> str:
    rc, out = capture(["git", "-C", path, "remote", "get-url", "--push", name])
    return out if rc == 0 else ""


def ensure_remote(name: str, fetch_url: str, push_url: str | None, path: str = ".") -> bool:
    """确保远程存在且 fetch/push URL 正确; 返回是否发生修改."""
    cur_fetch = remote_url(name, path)
    cur_push = remote_push_url(name, path)
    want_push = push_url or fetch_url
    if cur_fetch == fetch_url and cur_push == want_push:
        return False
    if cur_fetch:
        subprocess.run(["git", "-C", path, "remote", "remove", name], check=True)
    subprocess.run(["git", "-C", path, "remote", "add", name, fetch_url], check=True)
    if want_push and want_push != fetch_url:
        subprocess.run(["git", "-C", path, "remote", "set-url", "--push", name, want_push], check=True)
    return True


def ensure_identity(path: str = ".") -> None:
    for key in ("user.name", "user.email"):
        rc, out = capture(["git", "-C", path, "config", key])
        if rc != 0 or not out:
            console.error(f'git 缺少 {key}, 请先配置: git config --global {key} "..."')


def default_branch(url: str) -> str:
    """通过 ls-remote --symref 探测远端默认分支(main/master)."""
    rc, out = capture(["git", "ls-remote", "--symref", url, "HEAD"])
    if rc != 0:
        return ""
    for line in out.splitlines():
        if line.startswith("ref:"):
            # 输出形如: ref: refs/heads/main\tHEAD, 先按 tab 切掉 HEAD
            ref = line[len("ref:"):].strip().split("\t")[0].strip()
            return ref.split("/")[-1]
    return ""


def commit_count(path: str = ".") -> int:
    rc, out = capture(["git", "-C", path, "rev-list", "--count", "HEAD"])
    try:
        return int(out) if rc == 0 else 0
    except ValueError:
        return 0


def resolve_sha(ref: str = "HEAD", path: str = ".") -> str:
    rc, out = capture(["git", "-C", path, "rev-parse", ref])
    return out if rc == 0 else ""


def commit_brief(ref: str = "HEAD", path: str = ".") -> str:
    """形如 '短哈希|相对时间|作者|说明'."""
    rc, out = capture(["git", "-C", path, "log", "-1", "--pretty=format:%h|%ar|%an|%s", ref])
    return out if rc == 0 else ""


def status_counts(path: str = ".") -> tuple[int, int, int, int]:
    """返回 (已暂存, 已修改, 未跟踪, 冲突)."""
    rc, out = capture(["git", "-C", path, "status", "--porcelain"])
    if rc != 0:
        return 0, 0, 0, 0
    staged = modified = untracked = conflicts = 0
    for line in out.splitlines():
        if len(line) < 2:
            continue
        x, y = line[0], line[1]
        if "?" in (x, y):
            untracked += 1
            continue
        if "U" in (x, y) or (x, y) in (("A", "A"), ("D", "D")):
            conflicts += 1
            continue
        if x not in (" ", "!"):
            staged += 1
        if y not in (" ", "!"):
            modified += 1
    return staged, modified, untracked, conflicts


def fetch(path: str = ".", remote: str = "origin") -> bool:
    """更新远端跟踪引用 (用于判断领先/落后, 直连)."""
    return fetch_remote(path, remote)


def has_upstream(path: str = ".") -> bool:
    return capture(["git", "-C", path, "rev-parse", "--abbrev-ref", "@{upstream}"])[0] == 0


def upstream_of(ref: str = "HEAD", path: str = ".") -> str:
    """分支的上游全名 (如 origin/main); 未关联返回空串."""
    rc, out = capture(["git", "-C", path, "rev-parse", "--abbrev-ref",
                       "--symbolic-full-name", f"{ref}@{{upstream}}"])
    return out if rc == 0 else ""


def local_branch_exists(name: str, path: str = ".") -> bool:
    return capture(["git", "-C", path, "show-ref", "--verify", "--quiet",
                    f"refs/heads/{name}"])[0] == 0


def remote_branch_exists(remote: str, branch: str, path: str = ".") -> bool:
    rc, out = capture(["git", "-C", path, "ls-remote", "--heads", remote, branch])
    return rc == 0 and bool(out)


def set_upstream(remote: str, branch: str, path: str = ".") -> bool:
    return subprocess.run(
        ["git", "-C", path, "branch", f"--set-upstream-to={remote}/{branch}", branch],
        capture_output=True,
    ).returncode == 0


def diverge(upstream: str, ref: str = "HEAD", path: str = ".") -> tuple[int, int]:
    """(落后 upstream, 领先 ref) 的提交数; 取不到时返回 (-1, -1)."""
    rc, out = capture(["git", "-C", path, "rev-list", "--left-right", "--count",
                       f"{upstream}...{ref}"])
    if rc != 0:
        return -1, -1
    parts = out.replace("\t", " ").split()
    if len(parts) != 2:
        return -1, -1
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return -1, -1


def behind_ahead(path: str = ".") -> tuple[int, int]:
    """相对上游的 (落后, 领先); 无上游返回 (-1, -1)."""
    return diverge("@{upstream}", "HEAD", path)


def reset(path: str, mode: str, target: str) -> bool:
    return subprocess.run(["git", "-C", path, "reset", f"--{mode}", target]).returncode == 0


def delete_head(path: str = ".") -> bool:
    """删除 HEAD 引用: 撤销仓库的首个(也是唯一)提交, 保留暂存区内容."""
    return subprocess.run(["git", "-C", path, "update-ref", "-d", "HEAD"]).returncode == 0


def unstage_all(path: str = ".") -> bool:
    """清空索引(文件保留在工作区, 变为未跟踪)."""
    return subprocess.run(["git", "-C", path, "rm", "-r", "--cached", "-q", "."],
                          capture_output=True).returncode == 0


def commit_all(message: str, path: str = ".") -> bool:
    """add -A 并提交; 无变更返回 False."""
    _, status = capture(["git", "-C", path, "status", "--porcelain"])
    if not status:
        return False
    subprocess.run(["git", "-C", path, "add", "-A"], check=True)
    return subprocess.run(["git", "-C", path, "commit", "-m", message]).returncode == 0


def _github_rewrite_prefix() -> str:
    """全局 insteadOf 规则里把 https://github.com/ 重写的加速前缀; 无则空串."""
    rc, out = capture(["git", "config", "--global", "--get-regexp", r"url\..*insteadOf"])
    if rc != 0:
        return ""
    for line in out.splitlines():
        parts = line.split(" ", 1)
        if len(parts) != 2:
            continue
        key, value = parts
        if value != "https://github.com/":
            continue
        inner = key[len("url."):].lower()
        suffix = "/https://github.com/.insteadof"
        if inner.endswith(suffix):
            return inner[: -len(suffix)]
    return ""


def github_push_url(url: str) -> str:
    """给定 GitHub 地址, 返回推送地址.

    存在全局加速规则时返回 SSH 地址: 规则会把 https 推送也重写到
    不支持推送的镜像(405), 而 SSH 不受影响(gh 已配置密钥).
    无规则时返回直连 https.
    """
    m = re.search(r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    if not m:
        return url
    owner, repo = m.group(1), m.group(2)
    if _github_rewrite_prefix():
        return f"git@github.com:{owner}/{repo}.git"
    return f"https://github.com/{owner}/{repo}.git"


def _push_override(path: str, remote: str) -> str | None:
    """全局加速规则会把推送也重写到镜像(镜像不支持推送, 405).

    检测到这种情况时, 为本次推送临时改用 SSH 地址直连, 返回 -c 参数.
    """
    fetch = remote_url(remote, path)
    # fetch 可能是带加速前缀的地址, 用 search 提取末尾的 github 仓库路径
    m = re.search(r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", fetch)
    if not m or not _github_rewrite_prefix():
        return None
    owner, repo = m.group(1), m.group(2)
    return f"remote.{remote}.pushurl=git@github.com:{owner}/{repo}.git"


def push(path: str = ".", remote: str = "origin", branch: str = "", force: bool = False, upstream: bool = True) -> bool:
    args = ["git", "-C", path]
    override = _push_override(path, remote)
    if override:
        args += ["-c", override]
    args.append("push")
    if force:
        args.append("--force")
    if branch:
        args += [remote, branch]
        if upstream:
            args += ["--set-upstream"]
    else:
        args += [remote]
    return subprocess.run(args).returncode == 0


def proxy_args(prefix: str | None) -> list[str]:
    """用 -c 临时覆盖 insteadOf, 让本条 git 命令走加速(不改远程 URL)."""
    if not prefix:
        return []
    args: list[str] = []
    for target in accel.TARGETS:
        args += ["-c", f"url.{prefix}/{target}.insteadOf={target}"]
    return args


def fetch_remote(path: str = ".", remote: str = "origin", *, prefix: str | None = None,
                 prune: bool = False, all_remotes: bool = False, tags: bool = False) -> bool:
    """更新远端跟踪引用; prefix 非空时走加速. all_remotes 时忽略 remote 参数."""
    args = ["git", "-C", path, *proxy_args(prefix), "fetch"]
    if all_remotes:
        args.append("--all")
    else:
        args.append(remote)
    if prune:
        args.append("--prune")
    if tags:
        args.append("--tags")
    return subprocess.run(args, capture_output=True).returncode == 0


def refspec_push(path: str, remote: str, refs: Sequence[str] = (), *,
                 delete_refs: Sequence[str] = (), tags_all: bool = False,
                 force: bool = False) -> tuple[int, str]:
    """推送任意引用 (标签 / 分支); 复用"推送直连"的 insteadOf 覆盖.

    delete_refs 里的名字会以 :refs/tags/<name> 形式删除远端标签。
    返回 (退出码, 输出), 由调用方决定如何提示。
    """
    args = ["git", "-C", path]
    override = _push_override(path, remote)
    if override:
        args += ["-c", override]
    args.append("push")
    if force:
        args.append("--force")
    if tags_all:
        args.append("--tags")
    args.append(remote)
    args += [str(ref) for ref in refs]
    args += [f":refs/tags/{ref}" for ref in delete_refs]
    return run_capture(args)


def pull(path: str = ".", rebase: bool = False, prefix: str | None = None) -> bool:
    """拉取; prefix 非空时用 -c 临时覆盖 insteadOf 走加速(不改远程 URL)."""
    args = ["git", "-C", path, *proxy_args(prefix), "pull"]
    if rebase:
        args.append("--rebase")
    return subprocess.run(args).returncode == 0


# ---------------------------------------------------------------- 分支概览

# 单次 for-each-ref 拿到全部分支信息 (逐个分支起进程会慢一个数量级)
_BRANCH_FMT = "%00".join((
    "%(refname:short)", "%(upstream:short)", "%(upstream:track)", "%(HEAD)",
    "%(committerdate:relative)", "%(objectname:short)", "%(subject)",
))


def branches_info(path: str = ".", include_remote: bool = False) -> list[dict]:
    """分支列表 (按最近提交排序); include_remote 时含 refs/remotes 下的跟踪分支."""
    refs = ["refs/heads", "refs/remotes"] if include_remote else ["refs/heads"]
    rc, out = capture(["git", "-C", path, "for-each-ref", f"--format={_BRANCH_FMT}",
                       "--sort=-committerdate", *refs])
    if rc != 0:
        return []
    rows: list[dict] = []
    for line in out.splitlines():
        parts = (line.split("\x00") + [""] * 7)[:7]
        ahead, behind = _parse_track(parts[2])
        rows.append({
            "name": parts[0], "upstream": parts[1], "track": parts[2],
            "head": parts[3].strip() == "*", "date": parts[4],
            "sha": parts[5], "subject": parts[6], "ahead": ahead, "behind": behind,
        })
    return rows


def _parse_track(track: str) -> tuple[int, int]:
    """'[ahead 1, behind 2]' -> (1, 2); git 的 track 输出是英文, 不受语言影响."""
    ahead = behind = 0
    for kind, num in re.findall(r"(ahead|behind) (\d+)", track):
        if kind == "ahead":
            ahead = int(num)
        else:
            behind = int(num)
    return ahead, behind


def graph_lines(limit: int = 15, all_refs: bool = False, path: str = ".") -> list[str]:
    """`git log --graph --oneline` 的原始行 (由调用方上色渲染)."""
    args = ["git", "-C", path, "log", "--graph", "--oneline", "--decorate=short",
            "--color=never", "-n", str(limit)]
    if all_refs:
        args.append("--all")
    rc, out = capture(args)
    return out.splitlines() if rc == 0 else []


def remote_names(path: str = ".") -> list[str]:
    _, out = capture(["git", "-C", path, "remote"])
    return out.splitlines()


def set_remote_urls(name: str, fetch: str, push: str = "", path: str = ".") -> bool:
    """原地改 remote 地址 (ensure_remote 会先删后加, 这里保留其它配置)."""
    ok = subprocess.run(["git", "-C", path, "remote", "set-url", name, fetch],
                        capture_output=True).returncode == 0
    if push and push != fetch:
        ok = subprocess.run(["git", "-C", path, "remote", "set-url", "--push", name, push],
                            capture_output=True).returncode == 0 and ok
    return ok


# ---------------------------------------------------------------- 维护

def repo_size(path: str = ".") -> dict[str, int]:
    """仓库体积 (字节): loose 松散对象 / pack 打包 / garbage 垃圾, 以及对象计数.

    用 `count-objects -v` 的数值字段 (KiB), 避开 -H 输出的本地化单位。
    """
    rc, out = capture(["git", "-C", path, "count-objects", "-v"])
    data: dict[str, int] = {}
    if rc == 0:
        for line in out.splitlines():
            key, _, value = line.partition(": ")
            try:
                data[key.strip()] = int(value.strip())
            except ValueError:
                continue
    return {
        "loose": data.get("size", 0) * 1024,
        "pack": data.get("size-pack", 0) * 1024,
        "garbage": data.get("size-garbage", 0) * 1024,
        "loose_objects": data.get("count", 0),
        "pack_objects": data.get("in-pack", 0),
        "packs": data.get("packs", 0),
    }


def merged_branches(path: str = ".", target: str = "HEAD") -> list[str]:
    """已合入 target 的本地分支名 (不含当前分支)."""
    rc, out = capture(["git", "-C", path, "branch", "--merged", target, "--format=%(refname:short)"])
    if rc != 0:
        return []
    current = current_branch(path)
    return [name for name in out.splitlines() if name and name != current]


def delete_branch(name: str, path: str = ".", force: bool = False) -> bool:
    return subprocess.run(["git", "-C", path, "branch", "-D" if force else "-d", name],
                          capture_output=True).returncode == 0


def gc(path: str = ".", aggressive: bool = False) -> bool:
    """打包与清理: `git gc --prune=now` (可选 --aggressive)."""
    args = ["git", "-C", path, "gc", "--prune=now"]
    if aggressive:
        args.append("--aggressive")
    return subprocess.run(args).returncode == 0
