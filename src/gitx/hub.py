"""GitHub 网页与 API 的轻量功能: 搜索仓库 / 打开网页 / .gitignore 模板 / 仓库概览.

都依赖 API 或 raw 通道, 因此默认走加速 —— 这正是国内能顺畅用 GitHub 的前提。
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse

from rich.markup import escape

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


# ---------------------------------------------------------------- 仓库概览 (gitx stat)

def resolve_target(target: str) -> tuple[str, str]:
    """owner/repo / GitHub 链接 / 空 (取当前仓库 origin) -> (owner, repo)."""
    arg = (target or "").strip()
    if not arg:
        if not gitcmd.is_repo("."):
            console.error("当前目录不是 git 仓库\n用法: gitx stat <owner/repo|链接>")
        parsed = github.owner_repo(gitcmd.remote_url("origin"))
        if not parsed:
            console.error("origin 不是 GitHub 地址 (可先: gitx push to <仓库地址>)")
        return parsed
    if arg.startswith(("http://", "https://", "git@")):
        parsed = github.owner_repo(arg)
        if not parsed:
            console.error(f"无法识别 GitHub 地址: {arg}")
        return parsed
    try:
        return github.parse_repo(arg)
    except ValueError as exc:
        console.error(f"{exc}\n用法: gitx stat <owner/repo|链接>")


def _count(value: object) -> str:
    return f"{int(value or 0):,}"


def _date(value: object) -> str:
    text = str(value or "")
    return text[:10] if text else "-"


def _license_name(data: dict) -> str:
    lic = data.get("license") or {}
    name = lic.get("spdx_id") or lic.get("name") or ""
    return name if name and name != "NOASSERTION" else "无"


def _flags(data: dict) -> str:
    marks = [str(data.get("visibility") or ("private" if data.get("private") else "public"))]
    if data.get("archived"):
        marks.append("已归档")
    if data.get("disabled"):
        marks.append("已禁用")
    if data.get("is_template"):
        marks.append("模板")
    if data.get("fork"):
        parent = (data.get("parent") or {}).get("full_name")
        marks.append(f"复刻自 {parent}" if parent else "复刻")
    if data.get("mirror_url"):
        marks.append("镜像")
    return " | ".join(marks)


def _extras(owner: str, repo: str, prefix: str | None) -> dict:
    """可选信息: 语言构成 / 贡献者数 / 最新发布 (失败即缺省, 不影响主流程)."""
    langs = github.api_try(github.api_url(owner, repo, "/languages"), prefix)
    contributors = github.api_count(github.api_url(owner, repo, "/contributors") + "?anon=true", prefix)
    rel = github.api_try(github.api_url(owner, repo, "/releases/latest"), prefix)
    release: dict | None = None
    if isinstance(rel, dict) and rel.get("tag_name"):
        release = {
            "tag": str(rel.get("tag_name")),
            "name": str(rel.get("name") or ""),
            "published_at": _date(rel.get("published_at")),
            "assets": len(rel.get("assets") or []),
        }
    return {
        "languages": langs if isinstance(langs, dict) else {},
        "contributors": contributors,
        "release": release,
    }


def stat(target: str = "", prefix: str | None = None, *, json_out: bool = False) -> None:
    """仓库概览: star / fork / topics / 语言 / 许可证 / 时间线 / 贡献者 / 最新发布."""
    owner, repo = resolve_target(target)
    console.step(f"获取仓库信息: {owner}/{repo}" + (" [加速]" if prefix else ""))
    data = github.api(github.api_url(owner, repo, ""), prefix)
    if not isinstance(data, dict):
        console.error(f"无法获取 {owner}/{repo} 的信息")
    extra = _extras(owner, repo, prefix)
    if json_out:
        _print_json(data, owner, repo, extra)
        return
    _render(data, owner, repo, extra)


def _render(data: dict, owner: str, repo: str, extra: dict) -> None:
    full = str(data.get("full_name") or f"{owner}/{repo}")
    url = str(data.get("html_url") or f"https://github.com/{owner}/{repo}")
    console.print(console.link(full, url))
    desc = str(data.get("description") or "").strip()
    if desc:
        console.print(console.styled(f"[dim]{escape(desc)}[/dim]"))

    topics = [str(t) for t in (data.get("topics") or [])]
    table = console.table("项目", "值", title="仓库")
    table.add_row("描述", console.txt(desc or "-"))
    table.add_row("主页", console.txt(data.get("homepage") or "-"))
    table.add_row("标签", console.txt(f"{len(topics)} 个: {', '.join(topics)}" if topics else "无"))
    table.add_row("语言", console.txt(data.get("language") or "-"))
    table.add_row("许可证", console.txt(_license_name(data)))
    table.add_row("默认分支", console.txt(data.get("default_branch") or "-"))
    table.add_row("体积", console.txt(console.human_size(int(data.get("size") or 0) * 1024)))
    table.add_row("创建", console.txt(_date(data.get("created_at"))))
    table.add_row("最近更新", console.txt(_date(data.get("updated_at"))))
    table.add_row("最近推送", console.txt(_date(data.get("pushed_at"))))
    table.add_row("状态", console.txt(_flags(data)))
    console.print(table)

    stats = console.table("数据", "值", title="统计")
    stats.add_row("★ Star", console.styled(f"[num]{_count(data.get('stargazers_count'))}[/num]"))
    stats.add_row("Fork", console.txt(_count(data.get("forks_count"))))
    stats.add_row("关注 (watcher)", console.txt(_count(data.get("subscribers_count"))))
    stats.add_row("开放 issue/PR", console.txt(_count(data.get("open_issues_count"))))
    stats.add_row("贡献者", console.txt(_count(extra["contributors"]) if extra["contributors"] >= 0 else "-"))
    stats.add_row("网络仓库数", console.txt(_count(data.get("network_count"))))
    rel = extra["release"]
    stats.add_row("最新发布", console.txt(
        f"{rel['tag']} ({rel['published_at']}, 附件 {rel['assets']})" if rel else "无"))
    console.print(stats)

    langs = extra["languages"]
    if langs:
        total = sum(int(v or 0) for v in langs.values()) or 1
        table = console.table("语言", "占比", "代码量", title="语言构成")
        for name, size in sorted(langs.items(), key=lambda kv: -int(kv[1] or 0))[:8]:
            table.add_row(console.txt(name), console.txt(f"{int(size) / total * 100:.1f}%"),
                          console.txt(console.human_size(int(size))))
        console.print(table)

    console.info(f"下载: gitx {url}   |   看发布: gitx release {owner}/{repo} --tags"
                 f"   |   原始数据: gitx stat {owner}/{repo} --json")
    if not data.get("stargazers_count"):
        console.warn("Star: 0 (仓库还没有人标星)")


def _print_json(data: dict, owner: str, repo: str, extra: dict) -> None:
    """--json: 输出脚本友好的精简结构 (全部字段的原始响应可用 GitHub API 直接取)."""
    payload = {
        "full_name": data.get("full_name") or f"{owner}/{repo}",
        "html_url": data.get("html_url") or f"https://github.com/{owner}/{repo}",
        "description": data.get("description") or "",
        "homepage": data.get("homepage") or "",
        "stars": int(data.get("stargazers_count") or 0),
        "forks": int(data.get("forks_count") or 0),
        "watchers": int(data.get("subscribers_count") or 0),
        "open_issues": int(data.get("open_issues_count") or 0),
        "network_count": int(data.get("network_count") or 0),
        "language": data.get("language") or "",
        "languages": extra["languages"],
        "license": _license_name(data),
        "topics": data.get("topics") or [],
        "default_branch": data.get("default_branch") or "",
        "created_at": _date(data.get("created_at")),
        "updated_at": _date(data.get("updated_at")),
        "pushed_at": _date(data.get("pushed_at")),
        "size_kb": int(data.get("size") or 0),
        "archived": bool(data.get("archived")),
        "fork": bool(data.get("fork")),
        "visibility": data.get("visibility") or ("private" if data.get("private") else "public"),
        "contributors": extra["contributors"],
        "latest_release": extra["release"],
    }
    console.print(console.txt(json.dumps(payload, ensure_ascii=False, indent=2)))