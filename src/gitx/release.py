"""GitHub Release 下载: 通过 REST API 列出附件并直接下载 (默认走加速).

链接形式:
  https://github.com/owner/repo/releases                最新发布
  https://github.com/owner/repo/releases/tag/v1.0.0     指定标签
  https://github.com/owner/repo/releases/download/v1.0.0/文件名   单个附件

命令形式:
  gitx release owner/repo [--tag 标签] [--tags] [--asset 名字]... [--pick]
                          [--list] [--source] [-o 目录]
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import urllib.error
import urllib.request

from rich.markup import escape

from . import accel, console, gitcmd, github

_HEADERS = {"User-Agent": "gitx", "Accept": "application/vnd.github+json"}
_TARGET_RE = re.compile(r"^([\w.-]+)/([\w.-]+)$")
DEFAULT_LIMIT = 10  # 发布列表默认条数 (--limit 可改, GitHub 上限 100)
MAX_LIMIT = 100


# ---------------------------------------------------------------- 解析

def parse_target(arg: str) -> dict:
    """owner/repo 或发布页/附件链接 -> info 字典 (mode: release | asset)."""
    if arg.startswith(("http://", "https://")):
        info = github.parse_url(arg)
        if info["mode"] not in ("release", "asset"):
            console.error("这不是发布页链接 (示例: https://github.com/owner/repo/releases)")
        return info
    m = _TARGET_RE.match(arg)
    if not m:
        console.error(f"无法识别: {arg}\n用法: gitx release <owner/repo|发布页链接> [选项]")
    return {"mode": "release", "owner": m.group(1), "repo": m.group(2),
            "branch": "", "path": "", "tag": ""}


# ---------------------------------------------------------------- 入口

def run(info: dict, dest: str, prefix: str | None, *, tag: str = "",
        assets: tuple[str, ...] = (), list_only: bool = False, tags: bool = False,
        pick: bool = False, source: bool = False, limit: int = DEFAULT_LIMIT) -> None:
    """列出或下载 Release 附件; dest 为目录, 不存在则创建.

    给出 --tag / --asset 时完全非交互; 什么都不给且处于终端时, 依次挑选发布与附件
    (直接回车 = 最新发布 + 全部附件)。
    """
    owner, repo = info["owner"], info["repo"]
    tag = tag or info.get("tag", "")

    if tags:
        list_releases(owner, repo, prefix, limit)
        return

    if info["mode"] == "asset":
        if not tag:
            console.error("附件链接缺少标签, 请用 --tag 指定")
        name = os.path.basename(info["path"])
        url = github.github_url(owner, repo, f"/releases/download/{tag}/{info['path']}")
        saved = fetch_asset(url, os.path.join(dest, name), prefix)
        if saved:
            console.done(f"完成! 已保存到: {os.path.abspath(saved)}")
        return

    # 交互式挑选: 显式 --pick, 或终端里没给任何筛选条件
    choose = pick or (console.is_terminal() and not (tag or assets or list_only or source))
    if tag and tag != "latest":
        rel = fetch_release(owner, repo, tag, prefix)
    elif choose:
        rel = choose_release(fetch_releases(owner, repo, prefix, limit))
    else:
        rel = fetch_release(owner, repo, "", prefix)

    rel_tag = str(rel.get("tag_name") or tag)
    all_assets = list(rel.get("assets") or [])
    _show_release(owner, repo, rel, rel_tag)

    if list_only:
        _print_assets(all_assets, rel)
        return

    picked = _filter(all_assets, assets)
    if choose and picked:
        picked = choose_assets(picked)
        if not picked:
            console.warn("已取消下载")
            return

    total = 0
    for asset in picked:
        name = str(asset.get("name", ""))
        saved = fetch_asset(str(asset.get("browser_download_url", "")),
                            os.path.join(dest, name), prefix, int(asset.get("size") or 0))
        total += 1 if saved else 0
    if source or not picked:
        if not picked:
            console.warn("该 Release 没有匹配的附件, 改为下载源码包")
        url = str(rel.get("tarball_url") or github.api_url(owner, repo, f"/tarball/{rel_tag}"))
        saved = fetch_asset(url, os.path.join(dest, f"{repo}-{rel_tag}.tar.gz"), prefix)
        total += 1 if saved else 0
    console.done(f"完成: 共 {total} 个文件 -> {os.path.abspath(dest)}")


# ---------------------------------------------------------------- API

def fetch_release(owner: str, repo: str, tag: str, prefix: str | None) -> dict:
    """按标签取单个 Release; tag 为空时取最新."""
    if tag and tag != "latest":
        path = f"/releases/tags/{tag}"
    else:
        path = "/releases/latest"
    data = api(github.api_url(owner, repo, path), prefix)
    if not isinstance(data, dict):
        console.error("Release 数据异常, 请稍后重试")
    return data


def fetch_releases(owner: str, repo: str, prefix: str | None, limit: int = DEFAULT_LIMIT) -> list[dict]:
    """最近的发布列表 (含预发布), 按发布时间从新到旧."""
    limit = max(1, min(int(limit), MAX_LIMIT))
    data = api(github.api_url(owner, repo, f"/releases?per_page={limit}"), prefix)
    if not isinstance(data, list) or not data:
        console.error(f"{owner}/{repo} 还没有已发布的 Release")
    return data


def print_releases_table(releases: list, title: str) -> None:
    """发布列表表格: 编号 / 标签 / 名称 / 发布日期 / 附件数 / 状态."""
    table = console.table("#", "标签", "名称", "发布", "附件", "状态", title=title)
    for i, rel in enumerate(releases, 1):
        state = "草稿" if rel.get("draft") else ("预发布" if rel.get("prerelease") else "")
        table.add_row(
            console.txt(i),
            console.txt(rel.get("tag_name") or ""),
            console.txt(rel.get("name") or ""),
            console.txt(str(rel.get("published_at") or "")[:10]),
            console.txt(len(rel.get("assets") or [])),
            console.txt(state),
        )
    console.print(table)


def list_releases(owner: str, repo: str, prefix: str | None, limit: int = DEFAULT_LIMIT) -> None:
    """列出最近的发布, 不下载 (--tags)."""
    print_releases_table(fetch_releases(owner, repo, prefix, limit), f"{owner}/{repo} 的 Release")
    console.info(f"下载指定标签: gitx release {owner}/{repo} --tag <标签>"
                 f"  |  多看几个: --limit {min(limit * 2, MAX_LIMIT)}")


def choose_release(releases: list) -> dict:
    """交互式挑选发布 (含预发布); 非交互环境用最新发布."""
    if not console.is_terminal():
        console.warn("非交互环境, 使用最新发布")
        return releases[0]
    if len(releases) == 1:
        return releases[0]
    print_releases_table(releases, f"选择要下载的发布 (共 {len(releases)} 个, 用 --limit 调整)")
    answer = console.prompt("编号或标签名 (回车 = 1)").strip()
    if not answer:
        return releases[0]
    if answer.isdigit():
        index = int(answer)
        if 1 <= index <= len(releases):
            return releases[index - 1]
        console.warn(f"编号超出范围: {answer}, 使用最新发布")
        return releases[0]
    for rel in releases:
        if str(rel.get("tag_name") or "") == answer:
            return rel
    console.warn(f"没有该标签: {answer}, 使用最新发布")
    return releases[0]


def api(url: str, prefix: str | None) -> object:
    """请求 GitHub API (走加速); 已登录 gh 时复用其 token 提高限额."""
    req = urllib.request.Request(accel.wrap(url, prefix), headers=dict(_HEADERS))
    token = gh_token()
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            console.error("未找到该 Release\n提示: 仓库可能没有发布, 或用 --tags 查看可用标签")
        if exc.code in (403, 429):
            console.error(f"GitHub API 受限 HTTP {exc.code}: 匿名请求每小时 60 次\n"
                          "提示: 已登录 gh 时自动复用其 token (5000 次/小时)")
        console.error(f"API 请求失败 HTTP {exc.code}: {url}")
    except (urllib.error.URLError, OSError) as exc:
        console.error(f"API 请求失败: {exc}\n提示: gitx proxy test 检查加速源, 或 --no-proxy 直连")
    return None


def gh_token() -> str:
    rc, out = gitcmd.capture(["gh", "auth", "token"])
    return out if rc == 0 else ""


# ---------------------------------------------------------------- 展示

def _show_release(owner: str, repo: str, rel: dict, tag: str) -> None:
    head = f"[key]{escape(owner)}/{escape(repo)}[/key]  [num]{escape(tag)}[/num]"
    published = str(rel.get("published_at") or "")[:10]
    if published:
        head += f"  [dim]发布 {published}[/dim]"
    if rel.get("prerelease"):
        head += "  [warn]预发布[/warn]"
    console.print(head)
    body = str(rel.get("body") or "").strip()
    if body:
        console.print(f"[dim]{escape(body.splitlines()[0][:100])}[/dim]")


def _print_assets(assets: list, rel: dict) -> None:
    if assets:
        table = console.table("#", "附件", "大小", title=f"附件 {len(assets)} 个")
        for i, asset in enumerate(assets, 1):
            table.add_row(console.txt(i), console.txt(asset.get("name") or ""),
                          console.txt(console.human_size(int(asset.get("size") or 0))))
        console.print(table)
    else:
        console.warn("附件 0 个 (该 Release 只有源码包, 用 --source 下载)")
    if rel.get("tarball_url"):
        console.info(f"源码包: {rel['tarball_url']}")


def _filter(assets: list, patterns: tuple[str, ...]) -> list:
    """按通配/子串筛选附件; patterns 为空表示全选."""
    if not patterns:
        return list(assets)
    picked = [a for a in assets
              if any(fnmatch.fnmatch(str(a.get("name", "")), p)
                     or p.lower() in str(a.get("name", "")).lower() for p in patterns)]
    if not picked:
        names = ", ".join(str(a.get("name", "")) for a in assets[:10]) or "(无附件)"
        console.error(f"没有匹配的附件: {', '.join(patterns)}\n可用附件: {names}")
    return picked


def choose_assets(assets: list) -> list:
    """交互式挑选附件; 非交互环境取全部."""
    if not assets:
        return []
    if not console.is_terminal():
        console.warn("非交互环境, 已选择全部附件")
        return list(assets)
    if len(assets) == 1:
        return list(assets)
    table = console.table("#", "附件", "大小", title="选择要下载的附件")
    for i, asset in enumerate(assets, 1):
        table.add_row(console.txt(i), console.txt(asset.get("name") or ""),
                      console.txt(console.human_size(int(asset.get("size") or 0))))
    console.print(table)
    answer = console.prompt("编号 (如 1,3-4; a = 全部; 回车 = 全部)").strip().lower()
    if not answer or answer in ("a", "all", "全部"):
        return list(assets)
    indexes = _parse_indexes(answer, len(assets))
    picked = [assets[i - 1] for i in indexes]
    if not picked:
        console.warn("没有选中任何附件, 已取消")
    return picked


def _parse_indexes(answer: str, count: int) -> list[int]:
    """解析 '1,3-4' 形式的编号输入, 去重并保持顺序."""
    indexes: list[int] = []
    for part in answer.replace(" ", ",").split(","):
        if not part:
            continue
        lo, _, hi = part.partition("-")
        try:
            start = int(lo)
            end = int(hi) if hi else start
        except ValueError:
            console.warn(f"忽略无法识别的输入: {part}")
            continue
        indexes += [i for i in range(start, end + 1) if 1 <= i <= count]
    return list(dict.fromkeys(indexes))


# ---------------------------------------------------------------- 下载

def fetch_asset(url: str, dest_path: str, prefix: str | None, size: int = 0) -> str:
    """下载单个附件到 dest_path; 已存在时询问, 跳过则返回空串."""
    if not url:
        console.error("附件地址为空, 无法下载")
    if os.path.lexists(dest_path) and not console.ask(f"文件已存在: {dest_path}, 覆盖吗?", default=False):
        console.warn(f"跳过: {os.path.basename(dest_path)}")
        return ""
    parent = os.path.dirname(os.path.abspath(dest_path))
    os.makedirs(parent, exist_ok=True)
    req = urllib.request.Request(accel.wrap(url, prefix), headers=dict(_HEADERS))
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            console.save_stream(resp, dest_path, os.path.basename(dest_path), size)
    except urllib.error.HTTPError as exc:
        console.error(f"下载失败 HTTP {exc.code}: {url}")
    except (urllib.error.URLError, OSError) as exc:
        console.error(f"下载失败: {exc}")
    console.done(f"{os.path.basename(dest_path)} {console.human_size(os.path.getsize(dest_path))}"
                 + (" [加速]" if prefix else ""))
    return dest_path