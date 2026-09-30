"""git 命令封装: 统一调用与解析."""

from __future__ import annotations

import re
import subprocess
from typing import Sequence

from . import accel, console


def run(args: Sequence[str]) -> subprocess.CompletedProcess:
    return subprocess.run([str(a) for a in args])


def capture(args: Sequence[str]) -> tuple[int, str]:
    r = subprocess.run([str(a) for a in args], capture_output=True, text=True)
    return r.returncode, (r.stdout or "").strip()


def is_repo(path: str = ".") -> bool:
    return capture(["git", "-C", path, "rev-parse", "--is-inside-work-tree"])[0] == 0


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


def pull(path: str = ".", rebase: bool = False, prefix: str | None = None) -> bool:
    """拉取; prefix 非空时用 -c 临时覆盖 insteadOf 走加速(不改远程 URL)."""
    args = ["git", "-C", path]
    if prefix:
        for target in accel.TARGETS:
            args += ["-c", f"url.{prefix}/{target}.insteadOf={target}"]
    args.append("pull")
    if rebase:
        args.append("--rebase")
    return subprocess.run(args).returncode == 0
