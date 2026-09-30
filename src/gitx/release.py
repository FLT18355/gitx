"""GitHub Release 下载: 列附件 / 下附件 / 下源码包(全部支持加速).

链接形式:
  https://github.com/owner/repo/releases                       最新发布
  https://github.com/owner/repo/releases/tag/v1.0.0            指定标签
  https://github.com/owner/repo/releases/download/v1.0.0/文件名 单个附件
命令形式:
  gitx release owner/repo [--tag 标签] [--asset 名字或通配] [--list] [--source] [-o 目录]
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import urllib.error
import urllib.request

from . import accel, config, console, gitcmd, github

_HEADERS = {"User-Agent": "gitx", "Accept": "application/vnd.github+json"}

HELP = (
    "用法: gitx release <owner/repo|发布页链接> [选项]\n"
    "  --tag, -t <标签>      指定 Release 标签 (默认最新)\n"
    "  --asset, -a <名字>    只下载匹配的附件 (支持通配, 如 '*linux_amd64*')\n"
    "  --list                只列出附件, 不下载\n"
    "  --source              额外下载源码包 (tarball)\n"
    "  -o, --output <目录>   保存目录 (默认当前目录)\n"
    "  --proxy <加速源> / --no-proxy\n"
    "示例:\n"
    "  gitx release cli/cli --list\n"
    "  gitx release cli/cli --asset '*linux_amd64.tar.gz'\n"
    "  gitx https://github.com/cli/cli/releases/tag/v2.102.0 --list"
)


def cmd(argv: list[str]) -> None:
    """解析命令行并执行 (owner/repo 或发布页链接)."""
    dest = "."
    tag = ""
    asset = ""
    list_only = False
    source = False
    no_proxy = False
    proxy_flag: str | None = None
    repo_arg = ""

    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--tag", "-t") and i + 1 < len(argv):
            i += 1
            tag = argv[i]
        elif a in ("--asset", "-a") and i + 1 < len(argv):
            i += 1
            asset = argv[i]
        elif a in ("-o", "--output") and i + 1 < len(argv):
            i += 1
            dest = argv[i]
        elif a == "--list":
            list_only = True
        elif a == "--source":
            source = True
        elif a == "--no-proxy":
            no_proxy = True
        elif a == "--proxy" and i + 1 < len(argv):
            i += 1
            proxy_flag = argv[i]
        elif a in ("-h", "--help"):
            console.info(HELP)
            return
        elif a.startswith("-"):
            console.error(f"未知参数: {a}")
        else:
            repo_arg = a
        i += 1

    if not repo_arg:
        console.error(HELP)
    if repo_arg.startswith(("http://", "https://")):
        try:
            info = github.parse_url(repo_arg)
        except ValueError as exc:
            console.error(str(exc))
        if info["mode"] not in ("release", "asset"):
            console.error("这不是发布页链接 (示例: https://github.com/owner/repo/releases)")
        if not tag:
            tag = info.get("tag", "")
    else:
        m = re.match(r"^([\w.-]+)/([\w.-]+)$", repo_arg)
        if not m:
            console.error(f"无法识别: {repo_arg} (用 owner/repo 或发布页链接)")
        info = {"mode": "release", "owner": m.group(1), "repo": m.group(2),
                "branch": "", "path": "", "tag": ""}

    prefix = config.active_proxy(proxy_flag, no_proxy)
    run(info, dest, prefix, list_only=list_only, asset=asset, source=source, force_tag=tag)


def run(info: dict, dest: str, prefix: str | None, *, list_only: bool = False,
        asset: str = "", source: bool = False, force_tag: str = "") -> None:
    """列出或下载 Release 附件; dest 为目录, 不存在则创建."""
    owner, repo = info["owner"], info["repo"]
    tag = force_tag or info.get("tag", "")

    if info["mode"] == "asset":
        name = os.path.basename(info["path"])
        url = github.github_url(owner, repo, f"/releases/download/{tag}/{info['path']}")
        _fetch_asset(url, os.path.join(dest, name), prefix)
        console.done(f"完成! 已保存到: {os.path.abspath(os.path.join(dest, name))}")
        return

    api_path = "/releases/latest" if not tag else f"/releases/tags/{tag}"
    rel = _api(github.api_url(owner, repo, api_path), prefix)
    if not isinstance(rel, dict):
        console.error("API 返回异常, 请稍后重试")
    tag = rel.get("tag_name") or tag
    assets = rel.get("assets") or []
    published = str(rel.get("published_at") or "")[:10]
    console.info(f"仓库: {owner}/{repo} | 标签: {tag}" + (f" | 发布: {published}" if published else ""))
    body = str(rel.get("body") or "").strip()
    if body:
        console.info("说明: " + body.splitlines()[0][:78])

    if list_only:
        _print_assets(assets, rel)
        return

    picked = [a for a in assets if _match(str(a.get("name", "")), asset)] if asset else list(assets)
    if asset and not picked:
        names = ", ".join(str(a.get("name", "")) for a in assets[:10]) or "(无附件)"
        console.error(f"没有匹配的附件: {asset}\n可用附件: {names}")

    total = 0
    for a in picked:
        name = str(a.get("name", ""))
        _fetch_asset(str(a.get("browser_download_url", "")), os.path.join(dest, name),
                     prefix, int(a.get("size") or 0))
        total += 1
    if source or (not picked and not asset):
        if not picked:
            console.warn("该 Release 没有附件, 改为下载源码包")
        url = str(rel.get("tarball_url") or github.api_url(owner, repo, f"/tarball/{tag}"))
        _fetch_asset(url, os.path.join(dest, f"{repo}-{tag}.tar.gz"), prefix)
        total += 1
    console.done(f"完成: 共 {total} 个文件 -> {os.path.abspath(dest)}")


def _api(url: str, prefix: str | None) -> object:
    """请求 GitHub API (走加速); gh 已登录时用其 token 提高限额."""
    token = _token()
    req = urllib.request.Request(accel.wrap(url, prefix), headers=dict(_HEADERS))
    if token:
        req.add_header("Authorization", f"token {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            console.error("未找到该 Release\n提示: 仓库可能没有发布, 或标签名不正确 (gitx release owner/repo --list)")
        if exc.code in (403, 429):
            console.error(f"GitHub API 受限 HTTP {exc.code}: 匿名请求每小时 60 次\n"
                          "提示: 已登录 gh 时自动使用其 token (5000 次/小时)")
        console.error(f"API 请求失败 HTTP {exc.code}: {url}")
    except (urllib.error.URLError, OSError) as exc:
        console.error(f"API 请求失败: {exc}\n提示: gitx proxy test 检查加速源, 或 --no-proxy 直连")
    return None


def _token() -> str:
    rc, out = gitcmd.capture(["gh", "auth", "token"])
    return out if rc == 0 else ""


def _match(name: str, pattern: str) -> bool:
    return fnmatch.fnmatch(name, pattern) or pattern.lower() in name.lower()


def _print_assets(assets: list, rel: dict) -> None:
    if assets:
        console.info(f"附件 {len(assets)} 个:")
        for a in assets:
            name = str(a.get("name", ""))
            size = console.human_size(int(a.get("size") or 0))
            console.info(f"  {name:<44} {size:>10}")
    else:
        console.warn("附件 0 个 (该 Release 只有源码包, 用 --source 下载)")
    if rel.get("tarball_url"):
        console.info(f"源码包: {rel['tarball_url']}")


def _fetch_asset(url: str, dest_path: str, prefix: str | None, size: int = 0) -> None:
    if os.path.lexists(dest_path):
        if not console.ask(f"文件已存在: {dest_path}, 覆盖吗?", default=False):
            console.warn(f"跳过: {os.path.basename(dest_path)}")
            return
    parent = os.path.dirname(os.path.abspath(dest_path))
    os.makedirs(parent, exist_ok=True)
    req = urllib.request.Request(accel.wrap(url, prefix), headers=dict(_HEADERS))
    label = os.path.basename(dest_path) + (f" ({console.human_size(size)})" if size else "")
    console.step(f"下载 {label}" + (" [加速]" if prefix else ""))
    try:
        with urllib.request.urlopen(req, timeout=300) as r, open(dest_path, "wb") as f:
            shutil.copyfileobj(r, f)
    except urllib.error.HTTPError as exc:
        console.error(f"下载失败 HTTP {exc.code}: {url}")
    except (urllib.error.URLError, OSError) as exc:
        console.error(f"下载失败: {exc}")
    console.done(f"{os.path.basename(dest_path)}  {console.human_size(os.path.getsize(dest_path))}")