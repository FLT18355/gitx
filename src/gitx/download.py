"""下载 GitHub 仓库 / 文件夹 / 文件 / 源码包 (默认走加速).

四条路径, 按"要多少拿多少"选最省的一条:
  整仓库   git clone --depth N                      (默认浅克隆)
  文件夹   git clone --filter=blob:none --sparse    (只取该目录的 blob, 实测快 8 倍)
  单个文件 raw 直取 (可断点续传)
  源码包   API /tarball/<ref> 单个 HTTP 流          (不要 git 历史时最快)
"""

from __future__ import annotations

import os
import subprocess

from . import accel, console, gitcmd, github, net


def download(url: str, dest: str, prefix: str | None, depth: int = 1, branch: str = "",
             *, archive: bool = False, extract: bool = False, submodules: bool = False,
             resume: bool = True) -> None:
    """入口: 解析链接后分发 (链接已在调用方解析过时, 直接用 run)."""
    run(github.parse_url(url), dest, prefix, depth, branch,
        archive=archive, extract=extract, submodules=submodules, resume=resume)


def run(info: dict, dest: str, prefix: str | None, depth: int = 1, branch: str = "",
        *, archive: bool = False, extract: bool = False, submodules: bool = False,
        resume: bool = True) -> None:
    """按已解析的 info 分发 (info 见 github.parse_url)."""
    tag = f" | 分支: {info['branch']}" if info["branch"] else ""
    console.info(f"模式: {info['mode']} | 仓库: {info['owner']}/{info['repo']}{tag}")
    if info["mode"] in ("release", "asset"):
        console.error(f"这是发布页链接, 请用: gitx release {info['owner']}/{info['repo']}")
    if info["mode"] == "folder":
        _download_folder(info, dest, prefix, depth, branch)
        return
    if info["mode"] == "file":
        _download_file(info, dest, prefix, resume)
        return
    if archive:
        _download_archive(info, dest, prefix, branch, extract, resume)
        return
    _download_repo(info, dest, prefix, depth, branch, submodules)


# ---------------------------------------------------------------- 整仓库

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


def _git_clone(url: str, dest: str, depth: int, branch: str, *, extra: list[str] | None = None,
               prefix: str | None = None) -> int:
    args = ["git"]
    if prefix:
        # 子模组等二次拉取也走加速 (insteadOf 只对本次命令生效, 不落盘)
        for target in accel.TARGETS:
            args += ["-c", f"url.{prefix}/{target}.insteadOf={target}"]
    args.append("clone")
    if depth > 0:
        args += ["--depth", str(depth)]
    if branch:
        args += ["--branch", branch]
    args += [*(extra or []), url, dest]
    return subprocess.run(args).returncode


def _download_repo(info: dict, dest: str, prefix: str | None, depth: int, branch_override: str,
                   submodules: bool = False) -> None:
    clone_url, direct_url = _wrapped_clone_url(info, prefix)
    branch = _pick_branch(info, clone_url, branch_override)
    extra = ["--recurse-submodules", "--shallow-submodules", "-j", "4"] if submodules else []
    console.step(f"正在克隆 {info['owner']}/{info['repo']}"
                 + (f" (分支 {branch})" if branch else "")
                 + (" [加速]" if prefix else ""))
    if _git_clone(clone_url, dest, depth, branch, extra=extra, prefix=prefix) != 0:
        console.error("克隆失败, 请检查网络或加速源 (gitx proxy test)")
    if submodules:
        console.info("子模组已一并拉取 (同样走加速)")
    if prefix:
        # 镜像不支持推送: 推送地址走 SSH(有全局加速规则时)或直连 https
        push_url = gitcmd.github_push_url(direct_url, dest)
        subprocess.run(
            ["git", "-C", dest, "remote", "set-url", "--push", "origin", push_url],
            check=False,
            capture_output=True,
        )
    console.done(f"完成! 已保存到: {os.path.abspath(dest)}")


# ---------------------------------------------------------------- 文件夹 (稀疏检出)

def _download_folder(info: dict, dest: str, prefix: str | None, depth: int, branch_override: str) -> None:
    import shutil  # noqa: PLC0415
    import tempfile

    path_in_repo = info["path"]
    clone_url, _ = _wrapped_clone_url(info, prefix)
    branch = _pick_branch(info, clone_url, branch_override)
    if not branch:
        console.error("无法确定分支, 请用 --branch 指定")
    tmp = tempfile.mkdtemp(prefix="gitx-sparse-")
    try:
        args = ["git", "clone", "--no-checkout", "--sparse", "--filter=blob:none"]
        if depth > 0:
            args += ["--depth", str(depth)]
        args += ["--branch", branch, clone_url, tmp]
        console.step(f"正在下载文件夹 {path_in_repo} (部分克隆 + 稀疏检出, 分支 {branch})"
                     + (" [加速]" if prefix else ""))
        if subprocess.run(args).returncode != 0:
            console.error("克隆失败, 请检查网络或加速源 (gitx proxy test)")
        for step_args, what in (
            (["sparse-checkout", "set", "--no-cone", path_in_repo], "设置稀疏检出路径"),
            (["checkout", branch], "检出文件"),
        ):
            if subprocess.run(["git", "-C", tmp, *step_args], capture_output=True).returncode != 0:
                console.error(f"{what}失败: {path_in_repo} (检查分支名与路径)")
        src = os.path.join(tmp, path_in_repo)
        if not os.path.lexists(src):
            console.error(f"路径不存在: {path_in_repo} (检查分支名与路径)")
        parent = os.path.dirname(os.path.abspath(dest))
        os.makedirs(parent, exist_ok=True)
        if os.path.isdir(src) and not os.path.islink(src):
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)
        console.done(f"完成! 已保存到: {os.path.abspath(dest)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- 单个文件

def _download_file(info: dict, dest: str, prefix: str | None, resume: bool = True) -> None:
    raw = github.raw_url(info["owner"], info["repo"], info["branch"], info["path"])
    console.step(f"正在下载文件 {info['path']}" + (" [加速]" if prefix else ""))
    net.fetch(raw, dest, prefix=prefix, resume=resume)
    console.done(f"{os.path.basename(dest)} {console.human_size(os.path.getsize(dest))}")


# ---------------------------------------------------------------- 源码包 (无 git 历史)

def _download_archive(info: dict, dest: str, prefix: str | None, branch_override: str,
                      extract: bool, resume: bool = True) -> None:
    """走 API 的 /tarball/<ref>: 单个 HTTP 流, 不用 git, 不要历史时最省."""
    import shutil  # noqa: PLC0415
    import tempfile

    owner, repo = info["owner"], info["repo"]
    ref = branch_override or info["branch"]
    if not ref:
        ref = gitcmd.default_branch(accel.wrap(github.repo_clone_url(owner, repo), prefix))
    if not ref:
        console.error("无法确定分支, 请用 --branch 指定")
    url = github.api_url(owner, repo, f"/tarball/{ref}")
    name = f"{repo}-{ref}.tar.gz"
    console.step(f"正在下载源码包 {owner}/{repo}@{ref} (tar.gz)" + (" [加速]" if prefix else ""))
    if not extract:
        target = dest if dest.endswith((".tar.gz", ".tgz")) else os.path.join(dest, name)
        net.fetch(url, target, prefix=prefix, timeout=600, resume=resume)
        console.done(f"完成! 已保存到: {os.path.abspath(target)}")
        return
    tmp = tempfile.mkdtemp(prefix="gitx-archive-")
    try:
        archive = os.path.join(tmp, name)
        net.fetch(url, archive, prefix=prefix, timeout=600, resume=resume)
        target_dir = dest if dest not in (".", "") else repo
        _unpack(archive, target_dir)
        console.done(f"完成! 已解压到: {os.path.abspath(target_dir)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _unpack(archive: str, dest_dir: str) -> None:
    """解开 GitHub 源码包, 去掉最外层的 <repo>-<sha>/ 目录."""
    import tarfile  # noqa: PLC0415  只 --extract 时需要

    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        if not members:
            console.error("源码包是空的")
        tops = {m.name.split("/", 1)[0] for m in members}
        if len(tops) == 1:
            top = tops.pop()
            stripped = []
            for m in members:
                if m.name == top:
                    continue
                m.name = m.name[len(top) + 1:]
                stripped.append(m)
            members = stripped
        os.makedirs(dest_dir, exist_ok=True)
        try:
            tar.extractall(dest_dir, members=members, filter="data")
        except TypeError:  # Python < 3.12 无 filter 参数
            tar.extractall(dest_dir, members=members)