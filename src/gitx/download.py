"""下载 GitHub 仓库 / 文件夹 / 文件(支持加速)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request

from . import accel, console, gitcmd, github

_UA = {"User-Agent": "gitx/0.2"}


def download(url: str, dest: str, prefix: str | None, depth: int = 1, branch: str = "") -> None:
    """入口: 按 URL 模式分发."""
    info = github.parse_url(url)
    tag = f" | 分支: {info['branch']}" if info["branch"] else ""
    console.info(f"模式: {info['mode']} | 仓库: {info['owner']}/{info['repo']}{tag}")
    if info["mode"] == "repo":
        _download_repo(info, dest, prefix, depth, branch)
    elif info["mode"] == "folder":
        _download_folder(info, dest, prefix, depth, branch)
    else:
        _download_file(info, dest, prefix)


def _wrapped_clone_url(info: dict, prefix: str | None) -> tuple[str, str]:
    """返回 (带加速的克隆地址, 直连克隆地址)."""
    direct = github.repo_clone_url(info["owner"], info["repo"])
    return accel.wrap(direct, prefix), direct


def _pick_branch(info: dict, clone_url: str, override: str) -> str:
    """确定分支: 命令行 --branch > URL 内分支 > 远端默认分支."""
    if override:
        return override
    if info["branch"]:
        return info["branch"]
    return gitcmd.default_branch(clone_url)


def _download_repo(info: dict, dest: str, prefix: str | None, depth: int, branch_override: str) -> None:
    clone_url, direct_url = _wrapped_clone_url(info, prefix)
    branch = _pick_branch(info, clone_url, branch_override)
    console.step(f"正在克隆 {info['owner']}/{info['repo']}"
                 + (f" (分支 {branch})" if branch else "")
                 + (" [加速]" if prefix else ""))
    if _git_clone(clone_url, dest, depth, branch) != 0:
        console.error("克隆失败, 请检查网络或加速源 (gitx proxy test)")
    if prefix:
        # 镜像不支持推送: 推送地址强制直连
        subprocess.run(
            ["git", "-C", dest, "remote", "set-url", "--push", "origin", direct_url],
            check=False,
            capture_output=True,
        )


def _download_folder(info: dict, dest: str, prefix: str | None, depth: int, branch_override: str) -> None:
    path_in_repo = info["path"]
    clone_url, _ = _wrapped_clone_url(info, prefix)
    branch = _pick_branch(info, clone_url, branch_override)
    if not branch:
        console.error("无法确定分支, 请用 --branch 指定")
    tmp = tempfile.mkdtemp(prefix="gitx-sparse-")
    try:
        args = ["git", "clone", "--no-checkout"]
        if depth > 0:
            args += ["--depth", str(depth)]
        args += ["--branch", branch, clone_url, tmp]
        console.step(f"正在下载文件夹 {path_in_repo} (稀疏检出, 分支 {branch})"
                     + (" [加速]" if prefix else ""))
        if subprocess.run(args).returncode != 0:
            console.error("克隆失败, 请检查网络或加速源 (gitx proxy test)")
        subprocess.run(["git", "-C", tmp, "sparse-checkout", "init", "--no-cone"], check=True)
        subprocess.run(["git", "-C", tmp, "sparse-checkout", "set", path_in_repo], check=True)
        subprocess.run(["git", "-C", tmp, "checkout", branch], check=True)
        src = os.path.join(tmp, path_in_repo)
        if not os.path.lexists(src):
            console.error(f"路径不存在: {path_in_repo} (检查分支名与路径)")
        parent = os.path.dirname(os.path.abspath(dest))
        os.makedirs(parent, exist_ok=True)
        if os.path.isdir(src) and not os.path.islink(src):
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _download_file(info: dict, dest: str, prefix: str | None) -> None:
    raw = github.raw_url(info["owner"], info["repo"], info["branch"], info["path"])
    if prefix:
        raw = accel.wrap(raw, prefix)
    console.step(f"正在下载文件 {info['path']}" + (" [加速]" if prefix else ""))
    _fetch(raw, dest)


def _fetch(url: str, dest: str) -> None:
    parent = os.path.dirname(os.path.abspath(dest))
    os.makedirs(parent, exist_ok=True)
    req = urllib.request.Request(url, headers=_UA)
    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
    except urllib.error.HTTPError as exc:
        console.error(f"下载失败 HTTP {exc.code} ({url})\n提示: 检查分支名与路径是否正确")
    except (urllib.error.URLError, OSError) as exc:
        console.error(f"下载失败: {exc}\n提示: 可尝试 gitx proxy test / gitx proxy on 开启加速")


def _git_clone(url: str, dest: str, depth: int, branch: str) -> int:
    args = ["git", "clone"]
    if depth > 0:
        args += ["--depth", str(depth)]
    if branch:
        args += ["--branch", branch]
    args += [url, dest]
    return subprocess.run(args).returncode
