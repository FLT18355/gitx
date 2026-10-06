"""自更新: 查最新 Release -> 加速下载 wheel -> uv / pip 重装.

gitx 的更新也走加速: 先经加速镜像查 GitHub API 的最新发布, 再把 .whl 附件
下到临时目录 (带进度条与断点续传), 最后交给 `uv tool install --force` 装回。
没有 uv 时退回 `python -m pip install --force-reinstall`。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile

from . import __version__, config, console, net, release

# 本项目的 GitHub 仓库 (升级来源)
OWNER = "FLT18355"
REPO = "gitx"


def _version_tuple(text: str) -> tuple[int, ...]:
    """把 v1.2.3 / 1.2 之类的版本串变成可比较的数字元组."""
    return tuple(int(part) for part in re.findall(r"\d+", text)) or (0,)


def _pick_asset(rel: dict) -> dict | None:
    """优先 wheel (装得最快), 没有附件时返回 None (改用源码包)."""
    assets = [a for a in (rel.get("assets") or []) if a.get("name") and a.get("browser_download_url")]
    wheels = [a for a in assets if str(a["name"]).endswith(".whl")]
    return (wheels or assets or [None])[0]


def _install(path: str) -> None:
    """用 uv 优先安装本地包; 没有 uv 时退回 pip."""
    if shutil.which("uv"):
        cmd = ["uv", "tool", "install", "--force", path]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "--force-reinstall", path]
    console.step("安装中: " + " ".join(cmd))
    if subprocess.run(cmd).returncode != 0:
        console.error("安装失败\n提示: 手动重装用 uv tool install --force <wheel> (或 pip install --force-reinstall <wheel>)")


def run(*, check_only: bool = False, force: bool = False, no_proxy: bool = False) -> None:
    """检查并安装最新版本.

    check_only 时只报告是否有新版本; force 时即使是同版本 / 更旧也重装。
    Release 附件与 API 都走加速 (与 `gitx release` 同一条链路)。
    """
    prefix = config.active_proxy(no_proxy=no_proxy, release=True)
    console.step(f"查询最新版本: {OWNER}/{REPO}" + (" [加速]" if prefix else ""))
    rel = release.fetch_release(OWNER, REPO, "", prefix)
    tag = str(rel.get("tag_name") or "").strip().lstrip("v")
    if not tag:
        console.error("无法确定最新版本 (最新发布没有 tag)")
    newest, current = _version_tuple(tag), _version_tuple(__version__)

    if check_only:
        if newest > current:
            console.info(f"有新版本可用: {__version__} -> {tag}   (运行 gitx upgrade 更新)")
        else:
            console.done(f"已是最新版本 {__version__}")
        return
    if newest < current and not force:
        console.info(f"当前 {__version__} 比最新的 {tag} 还新, 已跳过 (要覆盖重装加 --force)")
        return
    if newest == current and not force:
        console.done(f"已是最新版本 {__version__} (要强制重装加 --force)")
        return

    asset = _pick_asset(rel)
    if asset:
        url = str(asset["browser_download_url"])
        name = str(asset["name"])
        size = int(asset.get("size") or 0)
    else:
        url = str(rel.get("tarball_url") or "")
        name = f"{REPO}-{tag}.tar.gz"
        size = 0
    if not url:
        console.error("最新发布没有可下载的附件 (wheel / 源码包)")

    tmpdir = tempfile.mkdtemp(prefix="gitx-upgrade-")
    try:
        dest = os.path.join(tmpdir, name)
        console.step(f"下载 {name} ({console.human_size(size)})" if size else f"下载 {name}")
        net.fetch(url, dest, prefix=prefix, size=size, label=name)
        _install(dest)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    console.done(f"已更新到 {tag}")
