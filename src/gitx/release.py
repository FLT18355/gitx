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
import os

from rich.markup import escape

from . import console, github, net

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
    try:
        owner, repo = github.parse_repo(arg)
    except ValueError as exc:
        console.error(f"{exc}\n用法: gitx release <owner/repo|发布页链接> [选项]")
    return {"mode": "release", "owner": owner, "repo": repo, "branch": "", "path": "", "tag": ""}


# ---------------------------------------------------------------- 入口

def run(info: dict, dest: str, prefix: str | None, *, tag: str = "",
        assets: tuple[str, ...] = (), list_only: bool = False, tags: bool = False,
        pick: bool = False, source: bool = False, limit: int = DEFAULT_LIMIT,
        resume: bool = True) -> None:
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
        saved = fetch_asset(url, os.path.join(dest, name), prefix, resume=resume)
        if saved:
            console.done(f"完成! 已保存到: {os.path.abspath(saved)}")
        return

    # 交互式挑选: 显式 --pick, 或终端里没给任何筛选条件
    choose = pick or (console.is_terminal() and not (tag or assets or list_only or source))
    if tag and tag != "latest":
        rel = fetch_release(owner, repo, tag, prefix)
    elif choose:
        rel = choose_release(fetch_releases(owner, repo, prefix, limit))
        if rel is None:
            console.warn("已取消下载")
            return
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
        if picked is None:
            console.warn("已取消下载")
            return

    total = 0
    for asset in picked:
        name = str(asset.get("name", ""))
        saved = fetch_asset(str(asset.get("browser_download_url", "")),
                            os.path.join(dest, name), prefix, int(asset.get("size") or 0),
                            resume=resume)
        total += 1 if saved else 0
    if source or not picked:
        if not picked:
            console.warn("该 Release 没有匹配的附件, 改为下载源码包")
        url = str(rel.get("tarball_url") or github.api_url(owner, repo, f"/tarball/{rel_tag}"))
        saved = fetch_asset(url, os.path.join(dest, f"{repo}-{rel_tag}.tar.gz"), prefix, resume=resume)
        total += 1 if saved else 0
    console.done(f"完成: 共 {total} 个文件 -> {os.path.abspath(dest)}")


# ---------------------------------------------------------------- API

def fetch_release(owner: str, repo: str, tag: str, prefix: str | None) -> dict:
    """按标签取单个 Release; tag 为空时取最新."""
    if tag and tag != "latest":
        path = f"/releases/tags/{tag}"
    else:
        path = "/releases/latest"
    data = github.api(github.api_url(owner, repo, path), prefix)
    if not isinstance(data, dict):
        console.error("Release 数据异常, 请稍后重试")
    return data


def fetch_releases(owner: str, repo: str, prefix: str | None, limit: int = DEFAULT_LIMIT) -> list[dict]:
    """最近的发布列表 (含预发布), 按发布时间从新到旧."""
    limit = max(1, min(int(limit), MAX_LIMIT))
    data = github.api(github.api_url(owner, repo, f"/releases?per_page={limit}"), prefix)
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


def _release_label(index: int, rel: dict) -> str:
    """发布列表一行: 编号 / 标签 / 名称 / 日期 / 附件数 / 预发布."""
    meta = [str(rel.get("published_at") or "")[:10],
            f"附件 {len(rel.get('assets') or [])}"]
    if rel.get("prerelease"):
        meta.append("预发布")
    head = "  ".join(str(rel.get(key) or "") for key in ("tag_name", "name")).strip()
    return f"{index}. {head}  ({', '.join(m for m in meta if m)})"


def choose_release(releases: list) -> dict | None:
    """上下键挑选发布 (输入标签/名称即筛选); 非交互环境用最新发布, Ctrl+C 返回 None."""
    if not console.is_terminal():
        console.warn("非交互环境, 使用最新发布")
        return releases[0]
    if len(releases) == 1:
        return releases[0]
    labels = [_release_label(i, rel) for i, rel in enumerate(releases, 1)]
    index = console.select(f"选择要下载的发布 (共 {len(releases)} 个, 输入标签或名称即筛选)",
                           labels, instruction="[↑↓] 选择  [输入] 筛选  [回车] 确认")
    return None if index is None else releases[index]


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


def choose_assets(assets: list) -> list | None:
    """上下键挑选附件 (空格勾选, 输入名称即筛选); 非交互环境取全部, Ctrl+C 返回 None."""
    if not assets:
        return []
    if not console.is_terminal():
        console.warn("非交互环境, 已选择全部附件")
        return list(assets)
    if len(assets) == 1:
        return list(assets)
    labels = [f"{asset.get('name') or ''}  ({console.human_size(int(asset.get('size') or 0))})"
              for asset in assets]
    picked = console.check(f"选择要下载的附件 (共 {len(assets)} 个, 输入名称即筛选)", labels,
                           instruction="[↑↓] 选择  [空格] 勾选  [输入] 筛选  [回车] 确认 (不勾选 = 全部)")
    if picked is None:
        return None
    if not picked:
        console.info("没有勾选任何附件, 下载全部")
        return list(assets)
    return [assets[i] for i in picked]


# ---------------------------------------------------------------- 下载

def fetch_asset(url: str, dest_path: str, prefix: str | None, size: int = 0,
                *, resume: bool = True) -> str:
    """下载单个附件到 dest_path; 已存在时询问, 跳过则返回空串."""
    if not url:
        console.error("附件地址为空, 无法下载")
    if os.path.lexists(dest_path) and not console.ask(f"文件已存在: {dest_path}, 覆盖吗?", default=False):
        console.warn(f"跳过: {os.path.basename(dest_path)}")
        return ""
    net.fetch(url, dest_path, prefix=prefix, headers=github.HEADERS, size=size, resume=resume)
    console.done(f"{os.path.basename(dest_path)} {console.human_size(os.path.getsize(dest_path))}"
                 + (" [加速]" if prefix else ""))
    return dest_path