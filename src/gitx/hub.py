"""GitHub 网页与 API 的轻量功能: 搜索仓库 / 打开网页 / 拉取 .gitignore 模板.

都依赖 API 或 raw 通道, 因此默认走加速 —— 这正是国内能顺畅用 GitHub 的前提。
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse

from . import config, console, github, gitcmd

# ---------------------------------------------------------------- 搜索

SEARCH_SORTS = ("stars", "forks", "updated")


def search(keyword: str, prefix: str | None, *, limit: int = 10, sort: str = "stars",
           language: str = "") -> list[dict]:
    """GitHub 仓库搜索 (走 API); 返回结果列表, 供 --download 继续下载."""
    query = keyword.strip()
    if language:
        query += f" language:{language}"
    params = [f"q={urllib.parse.quote(query)}", f"per_page={max(1, min(int(limit), 50))}"]
    if sort in SEARCH_SORTS:
        params.append(f"sort={sort}")
    console.step(f"搜索 GitHub 仓库: {keyword}" + (" [加速]" if prefix else ""))
    data = github.api("https://api.github.com/search/repositories?" + "&".join(params), prefix)
    if not isinstance(data, dict):
        return []
    items = list(data.get("items") or [])[:limit]
    if not items:
        console.warn(f"没有匹配 {keyword!r} 的仓库")
        return []

    table = console.table("#", "仓库", "★ star", "语言", "最近更新", "简介",
                          title=f"共 {int(data.get('total_count') or 0):,} 个结果, 显示前 {len(items)} 个")
    for i, repo in enumerate(items, 1):
        full = str(repo.get("full_name") or "")
        url = str(repo.get("html_url") or "")
        table.add_row(
            console.txt(i),
            console.link(full, url) if url else console.txt(full),
            console.txt(f"{int(repo.get('stargazers_count') or 0):,}"),
            console.txt(repo.get("language") or "-"),
            console.txt(str(repo.get("pushed_at") or "")[:10]),
            console.txt(str(repo.get("description") or "")[:60]),
        )
    console.print(table)
    console.info("下载: gitx <仓库链接>   |   看发布: gitx release owner/repo --tags")
    return items


# ---------------------------------------------------------------- 打开网页

_WEB_PATHS = {
    "issues": "/issues",
    "pulls": "/pulls",
    "releases": "/releases",
    "actions": "/actions",
    "wiki": "/wiki",
    "settings": "/settings",
}


def web(path: str = ".", what: str = "", *, browse: bool = True) -> str:
    """拼出当前仓库的 GitHub 页面并打开浏览器; 返回 URL."""
    if not gitcmd.is_repo(path):
        console.error(f"{path} 不是 git 仓库")
    parsed = github.owner_repo(gitcmd.remote_url("origin", path))
    if not parsed:
        console.error("origin 不是 GitHub 地址 (可先: gitx push to <仓库地址>)")
    owner, repo = parsed
    base = f"https://github.com/{owner}/{repo}"
    if what in _WEB_PATHS:
        url = base + _WEB_PATHS[what]
    elif what == "branch":
        url = f"{base}/tree/{gitcmd.current_branch(path) or 'main'}"
    elif what == "commit":
        url = f"{base}/commit/{gitcmd.resolve_sha('HEAD', path)}"
    else:
        url = base
    console.print(console.link(url, url))
    if browse:
        import webbrowser  # noqa: PLC0415  导入较重 (连带 shutil), 只打开浏览器时需要

        if not webbrowser.open(url):
            console.info("未能自动打开浏览器, 请手动访问上面的链接")
    return url


# ---------------------------------------------------------------- .gitignore 模板

_INDEX_URL = "https://api.github.com/repos/github/gitignore/git/trees/main?recursive=1"
_RAW_URL = "https://raw.githubusercontent.com/github/gitignore/main/{path}"
_INDEX_TTL = 7 * 24 * 3600  # 模板索引缓存一周


def templates(prefix: str | None = None, *, refresh: bool = False) -> dict[str, str]:
    """github/gitignore 的模板索引: 小写名 -> 仓库内路径 (带磁盘缓存)."""
    cache = config.cache_dir() / "gitignore.json"
    if not refresh and cache.exists():
        try:
            blob = json.loads(cache.read_text("utf-8"))
            if time.time() - float(blob.get("fetched") or 0) < _INDEX_TTL and blob.get("items"):
                return dict(blob["items"])
        except (ValueError, OSError, TypeError):
            pass

    data = github.api(_INDEX_URL, prefix)
    items: dict[str, str] = {}
    if isinstance(data, dict):
        for entry in data.get("tree") or []:
            path = str(entry.get("path") or "")
            if not path.endswith(".gitignore") or entry.get("type") != "blob":
                continue
            stem = path[: -len(".gitignore")]
            items.setdefault(stem.lower(), path)
            if "/" in stem:  # Global/macOS.gitignore 也认 "macos"
                items.setdefault(stem.rsplit("/", 1)[1].lower(), path)
    if not items:
        console.error("模板索引为空, 请检查网络 (gitx proxy test)")
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"fetched": time.time(), "items": items},
                                    ensure_ascii=False), "utf-8")
    except OSError:
        pass  # 缓存写不进去不影响功能
    return items


def list_templates(keyword: str = "", prefix: str | None = None) -> None:
    """列出可用模板名 (--list)."""
    index = templates(prefix)
    names = sorted({path[: -len(".gitignore")] for path in index.values()})
    if keyword:
        names = [name for name in names if keyword.lower() in name.lower()]
    if not names:
        console.warn(f"没有匹配 {keyword!r} 的模板")
        return
    console.columns(names, title=f"github/gitignore 模板 {len(names)} 个 (gitx ignore <名字> 写入)")
    console.info("提示: 多个一起写, 如 gitx ignore python node macos")


def ignore(names: list[str], dest: str = ".", *, force: bool = False,
           prefix: str | None = None) -> None:
    """把 github/gitignore 模板合并写入 .gitignore."""
    if not names:
        console.error("用法: gitx ignore python node  |  查看可用模板: gitx ignore --list")
    index = templates(prefix)
    resolved: list[tuple[str, str]] = []
    missing: list[str] = []
    for name in names:
        path = index.get(name.strip().lower().removesuffix(".gitignore"))
        if path:
            resolved.append((name, path))
        else:
            missing.append(name)
    if missing:
        console.error(f"没有这些模板: {', '.join(missing)}\n"
                      "提示: gitx ignore --list 查看全部可用模板")

    chunks: list[str] = []
    for _name, path in resolved:
        text = github.get_text(_RAW_URL.format(path=path), prefix).strip("\n")
        chunks.append(f"# --- {path[: -len('.gitignore')]} (github/gitignore) ---\n{text}\n")
    body = "\n".join(chunks)

    target = os.path.join(dest, ".gitignore")
    if force or not os.path.exists(target):
        with open(target, "w", encoding="utf-8") as f:
            f.write(body)
        action = "已写入"
    else:
        with open(target, "a", encoding="utf-8") as f:
            f.write(("\n" if os.path.getsize(target) else "") + body)
        action = "已追加到"
    console.done(f"{action} {os.path.abspath(target)}: "
                 + ", ".join(path[: -len('.gitignore')] for _n, path in resolved))