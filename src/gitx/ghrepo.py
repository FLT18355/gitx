"""我的 GitHub 仓库管理 (交给已安装并登录的 gh): 挑一个仓库 -> 进仓库编辑界面.

  gitx repos                       上下键挑仓库 -> 进编辑界面, 一项一项地改
  gitx repos -q <关键词>            按关键词搜仓库 (搜得到全部, 不受 -n 限制)
  gitx repos list                  列出我的仓库 (表格; 给 -q 就是搜索结果)
  gitx repos edit [仓库]            改描述 / 主页 / 话题 / 可见性 / 默认分支 / 功能开关 / 模板
  gitx repos view [仓库]            看详情 (--web 打开网页)
  gitx repos clone [仓库]           克隆到本地 (公开走加速; 私有交给 gh)
  gitx repos create <名字>          新建仓库
  gitx repos fork [仓库]            复刻
  gitx repos rename [仓库] <新名>    改名
  gitx repos archive/unarchive [仓库]  归档 / 取消归档
  gitx repos sync [仓库]            与上游 (或 --source) 同步
  gitx repos star/unstar [仓库]     收藏 / 取消收藏
  gitx repos set-default [仓库]     设为当前目录的默认仓库
  gitx repos delete [仓库]          删除 (会确认)

挑选器与表格只读 `gh repo list` / `gh repo view`; 写操作一律交给 `gh repo ...`,
本工具只拼参数、不接触令牌, 权限由 gh 自己的登录态决定。
仓库参数留空时用 questionary 上下键挑 (最多渲染 5 行, 超出可滚动, 打字即筛选),
`--limit/-n` 决定一次取几个仓库 ("只看前几个" 就给个小数字)。
"""

from __future__ import annotations

import os

from . import cache, config, console, download, ghcli

# gh repo list / view 的 JSON 字段: 够画表格, 也够渲染编辑界面的"当前设置"
LIST_FIELDS = ("nameWithOwner,description,visibility,isPrivate,isFork,isArchived,isTemplate,"
               "viewerHasStarred,viewerCanAdminister,stargazerCount,forkCount,primaryLanguage,"
               "homepageUrl,repositoryTopics,defaultBranchRef,hasIssuesEnabled,hasWikiEnabled,"
               "hasProjectsEnabled,hasDiscussionsEnabled,updatedAt,pushedAt,url")
VIEW_FIELDS = f"{LIST_FIELDS},isInOrganization"

DEFAULT_LIMIT = 30  # 一次取几个仓库 (gh 默认 30); --limit 可改

# 编辑界面里能开关的功能: (JSON 字段, gh 开关, 显示名)
_FEATURES: tuple[tuple[str, str, str], ...] = (
    ("hasIssuesEnabled", "--enable-issues", "议题 Issue"),
    ("hasWikiEnabled", "--enable-wiki", "Wiki"),
    ("hasProjectsEnabled", "--enable-projects", "项目 Projects"),
    ("hasDiscussionsEnabled", "--enable-discussions", "讨论 Discussions"),
)

_VISIBILITY = (("public", "公开 public"), ("private", "私有 private"), ("internal", "内部 internal"))
_VISIBILITY_ZH = {"public": "公开", "private": "私有", "internal": "内部"}


# ---------------------------------------------------------------- 读

# 仓库数据都是"读一次要好几秒"的网络结果 (gh 自己会先做一次 GraphQL 往返), 因此统一
# 记进 ~/.cache/gitx: 缓存键以 ghrepo: 开头, 写操作后整批作废 (见 _forget)。
# 命中时一条 `gitx repos -n 5` 从 7 秒掉到 1 秒内, 而 --fresh 可绕过缓存。
_PREFIX = "ghrepo:"
_VIEW_PREFIX = f"{_PREFIX}view:"
_VISIBILITY_PREFIX = f"{_PREFIX}visibility:"
_BRANCHES_PREFIX = f"{_PREFIX}branches:"


def _gh() -> str:
    """已安装且已登录的 gh 路径 (管理仓库是写操作, 一定要登录态)."""
    return ghcli.require("管理仓库", hint="只读的仓库查询用 gitx stat / gitx search, 不需要 gh")


def _nwo(target: str) -> str:
    """目标仓库的 owner/repo (接受链接); 空串 = 当前仓库, 交给 gh 自己判定."""
    args = ghcli.repo_args(target)  # 顺带做中文校验与报错
    return args[1] if args else ""


def _need(target: str, what: str) -> str:
    """必须指明仓库的子命令: 空目标就中文提示并退出."""
    nwo = _nwo(target)
    if not nwo:
        console.error(f"请给出仓库: gitx repos {what} <owner/repo>\n"
                      "提示: 直接 gitx repos 可以上下键挑一个")
    return nwo


def _forget() -> None:
    """写操作之后作废全部仓库缓存 (列表 / 搜索 / 详情 / 分支都源于同一份远端状态)."""
    cache.drop_prefix(_PREFIX)


def _remember(key: str, value: object) -> None:
    """回源的结果一律写回缓存 —— --fresh 只跳过"读", 不跳过"写", 否则下一条命令又看到旧值."""
    cache.put(key, value)


def _recall(key: str, *, fresh: bool) -> object | None:
    """取缓存; fresh=True (= --fresh) 时当作没命中, 强制回源."""
    return None if fresh else cache.get(key)


def _filters(visibility: str = "", *, source: bool = False, forks: bool = False,
             archived: bool = False, no_archived: bool = False, language: str = "",
             topic: str = "") -> list[str]:
    """gh repo list 的过滤参数."""
    args: list[str] = []
    if visibility:
        args += ["--visibility", visibility]
    if source:
        args.append("--source")
    if forks:
        args.append("--fork")
    if archived:
        args.append("--archived")
    if no_archived:
        args.append("--no-archived")
    if language:
        args += ["--language", language]
    if topic:
        args += ["--topic", topic]
    return args


def _filter_key(filters: dict) -> str:
    """过滤项 -> 稳定的缓存键片段 (只保留真正生效的项, 顺序固定)."""
    active = sorted((name, value) for name, value in filters.items()
                    if value not in ("", None, False))
    return ",".join(f"{name}={value}" for name, value in active)


def fetch_repos(owner: str = "", *, limit: int = DEFAULT_LIMIT, fresh: bool = False,
                **filters: object) -> list[dict]:
    """我的 (或某个 owner 的) 仓库列表, 按最近推送从新到旧; limit 决定只取前几个."""
    count = max(1, int(limit))
    key = f"{_PREFIX}list:{owner or '@me'}:{count}:{_filter_key(filters)}"
    hit = _recall(key, fresh=fresh)
    if isinstance(hit, list):
        return hit
    gh = _gh()
    args = ["repo", "list", *([owner] if owner else []), "-L", str(count),
            "--json", LIST_FIELDS, *_filters(**filters)]  # type: ignore[arg-type]
    console.step(f"正在取{owner or '我的'}仓库 (前 {count} 个) ...")
    data = ghcli.json_out(gh, args, "列出仓库")
    if not isinstance(data, list):
        console.error("仓库数据异常, 请稍后重试")
    _remember(key, data)
    return data


# gh search repos 的字段与 gh repo list 不同 (fullName / stargazersCount; language 是字符串),
# 且给不了 模板 / 收藏 / 话题 / 议题开关 —— 这里统一成编辑界面认的那套, 缺的项由 fetch_repo 补齐。
SEARCH_FIELDS = ("fullName,description,visibility,isPrivate,isFork,isArchived,stargazersCount,"
                 "language,defaultBranch,homepage,updatedAt,pushedAt,url")
_PARTIAL = "_partial"  # 标记: 这条结果来自搜索, 进编辑界面前要用 fetch_repo 补全


def _normalize(item: dict) -> dict:
    """把 gh search repos 的一条结果翻成 gh repo list 的形状."""
    lang = str(item.get("language") or "")
    branch = str(item.get("defaultBranch") or "")
    return {
        _PARTIAL: True,
        "nameWithOwner": str(item.get("fullName") or ""),
        "description": item.get("description") or "",
        "visibility": str(item.get("visibility") or "").lower(),
        "isPrivate": bool(item.get("isPrivate")),
        "isFork": bool(item.get("isFork")),
        "isArchived": bool(item.get("isArchived")),
        "isTemplate": False,
        "viewerHasStarred": False,
        "stargazerCount": int(item.get("stargazersCount") or 0),
        "primaryLanguage": {"name": lang} if lang else None,
        "homepageUrl": item.get("homepage") or "",
        "defaultBranchRef": {"name": branch} if branch else None,
        "repositoryTopics": [],
        "updatedAt": item.get("updatedAt") or "",
        "pushedAt": item.get("pushedAt") or "",
        "url": item.get("url") or "",
    }


def _search_args(keyword: str, owner: str, limit: int, *, visibility: str = "",
                 source: bool = False, forks: bool = False, archived: bool = False,
                 no_archived: bool = False, language: str = "", topic: str = "") -> list[str]:
    """gh search repos 的参数 (过滤项名字与 gh repo list 略有不同, 转发到对应开关).

    gh 的布尔开关只认 `--archived=true` 这种等号形式, `--archived true` 会把它当成
    查询词的一部分而静默返回空结果, 因此这里一律用等号。
    """
    args = ["search", "repos", keyword, "--owner", owner or "@me",
            "-L", str(max(1, int(limit))), "--json", SEARCH_FIELDS]
    if visibility:
        args += ["--visibility", visibility]
    if language:
        args += ["--language", language]
    if topic:
        args += ["--topic", topic]
    if archived:
        args.append("--archived=true")
    elif no_archived:
        args.append("--archived=false")
    if source:
        args.append("--include-forks=false")
    elif forks:
        args.append("--include-forks=only")
    return args


def search_repos(keyword: str, owner: str = "", *, limit: int = DEFAULT_LIMIT,
                 fresh: bool = False, **filters: object) -> list[dict]:
    """按关键词搜仓库 (仓库名 / 描述命中), 不受"只取前 -n 个"的限制."""
    text = keyword.strip()
    if not text:
        console.error("请给搜索词: gitx repos -q <关键词>")
    count = max(1, int(limit))
    key = f"{_PREFIX}search:{text}:{owner or '@me'}:{count}:{_filter_key(filters)}"
    hit = _recall(key, fresh=fresh)
    if isinstance(hit, list):
        return hit
    gh = _gh()
    console.step(f"搜索{owner or '我的'}仓库: {text}")
    args = _search_args(text, owner, count, **filters)  # type: ignore[arg-type]
    data = ghcli.json_out(gh, args, "搜索仓库")
    if not isinstance(data, list):
        console.error("仓库数据异常, 请稍后重试")
    repos = [_normalize(item) for item in data if isinstance(item, dict)]
    _remember(key, repos)
    return repos


def fetch(keyword: str = "", owner: str = "", *, limit: int = DEFAULT_LIMIT,
          fresh: bool = False, **filters: object) -> list[dict]:
    """有搜索词就搜 (搜得到全部), 没有就按最近推送列前 limit 个; 两者字段已统一."""
    if keyword.strip():
        return search_repos(keyword, owner, limit=limit, fresh=fresh, **filters)
    return fetch_repos(owner, limit=limit, fresh=fresh, **filters)


def fetch_repo(target: str, *, fresh: bool = False) -> dict:
    """单个仓库的当前设置 (编辑界面的数据源)."""
    nwo = _need(target, "edit")
    key = f"{_VIEW_PREFIX}{nwo}"
    hit = _recall(key, fresh=fresh)
    if isinstance(hit, dict):
        return hit
    gh = _gh()
    repo = ghcli.json_out(gh, ["repo", "view", nwo, "--json", VIEW_FIELDS], f"查看仓库 {nwo}")
    if not isinstance(repo, dict):
        console.error("仓库数据异常, 请稍后重试")
    _remember(key, repo)
    return repo


# ---------------------------------------------------------------- 挑选 / 表格

def _topics(repo: dict) -> list[str]:
    """话题列表 (gh 给的是 [{name: ...}], 也兼容纯字符串)."""
    out = []
    for item in repo.get("repositoryTopics") or []:
        name = item.get("name") if isinstance(item, dict) else item
        if name:
            out.append(str(name))
    return out


def _branch_of(repo: dict) -> str:
    ref = repo.get("defaultBranchRef") or {}
    return str(ref.get("name") or "") if isinstance(ref, dict) else ""


def _state(repo: dict) -> str:
    """一行摘要: 可见性 / 归档 / 复刻 / 模板 / star / 语言 / 更新 / 已收藏."""
    parts = [_VISIBILITY_ZH.get(str(repo.get("visibility") or "").lower(),
                                str(repo.get("visibility") or "").lower() or "-")]
    if repo.get("isArchived"):
        parts.append("已归档")
    if repo.get("isFork"):
        parts.append("复刻")
    if repo.get("isTemplate"):
        parts.append("模板")
    parts.append(f"★{int(repo.get('stargazerCount') or 0)}")
    lang = (repo.get("primaryLanguage") or {}).get("name")
    if lang:
        parts.append(str(lang))
    updated = str(repo.get("updatedAt") or "")[:10]
    if updated:
        parts.append(f"更新 {updated}")
    if repo.get("viewerHasStarred"):
        parts.append("已收藏")
    return ", ".join(parts)


def _label(index: int, repo: dict) -> str:
    return f"{index}. {repo.get('nameWithOwner') or ''}  ({_state(repo)})"


_SEARCH_CHOICE = "⌕ 用关键词搜全部仓库 (不受 -n 限制)"


def _ask_keyword(current: str = "") -> str:
    """问一次搜索词; 留空 = 回到原列表, Ctrl+C 也一样 (都不算错)."""
    answer = console.text("搜什么? (仓库名 / 描述 / 语言里的词)", default=current,
                          instruction="[回车] 开始搜索  [清空] 回到列表  [Ctrl+C] 返回")
    return "" if answer is None else answer.strip()


def pick_repo(owner: str = "", *, limit: int = DEFAULT_LIMIT, message: str = "",
              keyword: str = "", fresh: bool = False, **filters: object) -> dict | None:
    """上下键挑一个仓库 (最多渲染 5 行, 打字即筛选); Ctrl+C 返回 None.

    列表底部有一条"用关键词搜全部仓库": 选它就能输入关键词去 GitHub 搜 (搜得到全部,
    不受 -n 的"只取前几个"限制), 搜完接着在这里挑, 因此仓库多也不用把 -n 调大。
    搜索结果缺几个字段 (模板 / 收藏 / 话题), 挑中后会再 fetch_repo 一次补齐。

    非交互环境直接报错 (脚本里请显式给仓库名, 别依赖这个兜底)。
    """
    if not console.is_terminal():
        console.error("挑仓库需要交互终端\n提示: 非交互请直接给出仓库名, 如 gitx repos view owner/repo")
    while True:
        repos = fetch(keyword, owner, limit=limit, fresh=fresh, **filters)
        fresh = False  # 只让第一轮回源; 之后在列表里换关键词时照常吃缓存
        if not repos:
            if keyword:
                console.warn(f"没有匹配 {keyword!r} 的仓库, 回到列表")
                keyword = ""
                continue
            console.error("没有找到仓库\n提示: 换个过滤条件, 或 gitx repos create <名字> 新建一个")
        where = f"{owner} 的" if owner else "我的"
        if message:
            head = message
        elif keyword:
            head = f"搜索 {keyword!r} 的结果 ({len(repos)} 个)"
        else:
            head = f"选择仓库 ({where}前 {len(repos)} 个, 输入名字 / 语言 即筛选)"
        labels = [_label(i, repo) for i, repo in enumerate(repos, 1)]
        # 列表被 -n 截断 (可能还有更多), 或已经在搜索: 都给一个"换关键词再搜"的入口
        if keyword or len(repos) >= limit:
            labels.append(_SEARCH_CHOICE)
        index = console.select(head, labels, instruction="[↑↓] 选择  [输入] 筛选  [回车] 确认")
        if index is None:
            return None
        if index == len(repos):  # 选了"用关键词搜全部仓库"
            keyword = _ask_keyword(keyword)
            continue
        picked = repos[index]
        nwo = str(picked.get("nameWithOwner") or "")
        return fetch_repo(nwo) if picked.get(_PARTIAL) else picked


def resolve(target: str = "", *, owner: str = "", limit: int = DEFAULT_LIMIT, what: str = "",
            keyword: str = "", fresh: bool = False, **filters: object) -> str:
    """子命令的仓库参数: 给了就用它, 没给且终端里就上下键挑一个 (最多渲染 5 行).

    挑不到 (取消 / 非交互) 就中文提示并退出, 因此各子命令都能写成
    `ghrepo.view(ghrepo.resolve(target, what="查看"))`。
    """
    if target:
        return target
    if not console.is_terminal():
        console.error(f"请给出仓库: gitx repos {what or 'edit'} <owner/repo>\n"
                      "提示: 直接 gitx repos 可以上下键挑一个, 再进编辑界面")
    picked = pick_repo(owner, limit=limit, keyword=keyword, fresh=fresh,
                       message=f"选择要{what}的仓库" if what else "", **filters)
    if picked is None:  # 挑选器里 Ctrl+C: 与其它交互命令一致, 算取消而不是出错
        console.warn("已取消")
        raise SystemExit(0)
    return str(picked.get("nameWithOwner") or "")


def _repo_table(repos: list[dict], title: str) -> None:
    table = console.table("仓库", "描述", "可见性", "★", "语言", "更新", "标记", title=title)
    for repo in repos:
        lang = (repo.get("primaryLanguage") or {}).get("name")
        marks = [m for m in ("已归档" if repo.get("isArchived") else "",
                             "复刻" if repo.get("isFork") else "",
                             "模板" if repo.get("isTemplate") else "",
                             "已收藏" if repo.get("viewerHasStarred") else "") if m]
        table.add_row(
            console.txt(repo.get("nameWithOwner") or ""),
            console.txt(str(repo.get("description") or "")[:48]),
            console.txt(_VISIBILITY_ZH.get(str(repo.get("visibility") or "").lower(),
                                           str(repo.get("visibility") or "").lower() or "-")),
            console.txt(int(repo.get("stargazerCount") or 0)),
            console.txt(lang or "-"),
            console.txt(str(repo.get("updatedAt") or "")[:10]),
            console.txt("/".join(marks) or "-"),
        )
    console.print(table)


def list_repos(owner: str = "", *, limit: int = DEFAULT_LIMIT, keyword: str = "",
               fresh: bool = False, **filters: object) -> None:
    """列出仓库: 仓库 / 描述 / 可见性 / star / 语言 / 更新 / 标记 (给关键词 = 搜索结果)."""
    repos = fetch(keyword, owner, limit=limit, fresh=fresh, **filters)
    where = f"{owner} 的" if owner else "我的"
    if not repos:
        if keyword:
            console.info(f"没有匹配 {keyword!r} 的仓库 (换个词试试)\n"
                         "提示: 不带 -q 就是按最近推送列出前 -n 个")
            return
        console.info(f"{where}仓库 0 个 (换个过滤条件看看)\n"
                     "提示: gitx repos list --no-archived --source 只看未归档的非复刻仓库")
        return
    title = f"搜索 {keyword!r}: {len(repos)} 个" if keyword else f"{where}仓库 {len(repos)} 个"
    _repo_table(repos, title)
    console.info("进编辑界面改设置: gitx repos   |   看某一个: gitx repos view <owner/repo>")


def view(target: str = "", *, web: bool = False, fresh: bool = False) -> None:
    """查看单个仓库的设置 (--web 交给 gh 打开网页)."""
    gh = _gh()
    nwo = _nwo(target)
    args = ["repo", "view", *([nwo] if nwo else [])]
    if web:
        ghcli.run(gh, [*args, "--web"], "打开仓库网页")
        return
    repo = fetch_repo(nwo, fresh=fresh) if nwo else ghcli.json_out(
        gh, [*args, "--json", VIEW_FIELDS], "查看仓库")
    if not isinstance(repo, dict):
        console.error("仓库数据异常, 请稍后重试")
    _show_settings(repo)
    console.info(f"改设置: gitx repos edit {repo.get('nameWithOwner')}"
                 "   |   进交互式编辑界面: gitx repos")


def _show_settings(repo: dict) -> None:
    """把仓库当前设置摊成一张表 (编辑界面每轮都重画一次)."""
    nwo = str(repo.get("nameWithOwner") or "")
    head = f"[key]{nwo}[/key]"
    if repo.get("isArchived"):
        head += "  [warn]已归档[/warn]"
    if repo.get("url"):
        head += f"  [dim]{repo['url']}[/dim]"
    console.print(head)
    table = console.table("项", "当前值", title="仓库设置")
    table.add_row(console.txt("描述"), console.txt(repo.get("description") or "(空)"))
    table.add_row(console.txt("主页"), console.txt(repo.get("homepageUrl") or "(空)"))
    table.add_row(console.txt("话题"), console.txt(", ".join(_topics(repo)) or "(无)"))
    table.add_row(console.txt("可见性"), console.txt(
        _VISIBILITY_ZH.get(str(repo.get("visibility") or "").lower(),
                           str(repo.get("visibility") or "") or "-")))
    table.add_row(console.txt("默认分支"), console.txt(_branch_of(repo) or "-"))
    table.add_row(console.txt("功能"), console.txt(" / ".join(
        f"{zh}{'开' if repo.get(field) else '关'}" for field, _, zh in _FEATURES)))
    table.add_row(console.txt("模板仓库"), console.txt("是" if repo.get("isTemplate") else "否"))
    table.add_row(console.txt("其它"), console.txt(_state(repo)))
    if not repo.get("viewerCanAdminister"):
        table.add_row(console.txt("权限"), console.txt("没有管理权限 (写操作会被 GitHub 拒绝)"))
    console.print(table)


# ---------------------------------------------------------------- 写

def _edit_args(*, description: str | None = None, homepage: str | None = None,
               add_topics: tuple[str, ...] = (), remove_topics: tuple[str, ...] = (),
               visibility: str = "", default_branch: str = "", template: bool | None = None,
               features: dict[str, bool] | None = None) -> list[str]:
    """把"要改的项"翻成 gh repo edit 参数 (没给的项一个参数都不带)."""
    args: list[str] = []
    if description is not None:
        args += ["--description", description]
    if homepage is not None:
        args += ["--homepage", homepage]
    for topic in add_topics:
        args += ["--add-topic", topic]
    for topic in remove_topics:
        args += ["--remove-topic", topic]
    if visibility:
        # 改可见性有副作用 (掉 star / 断开复刻关系), gh 要求显式接受
        args += ["--visibility", visibility, "--accept-visibility-change-consequences"]
    if default_branch:
        args += ["--default-branch", default_branch]
    if template is not None:
        args.append(f"--template={str(bool(template)).lower()}")
    for field, flag, _ in _FEATURES:
        if features and field in features:
            args.append(f"{flag}={str(bool(features[field])).lower()}")
    return args


def edit(target: str, *, description: str | None = None, homepage: str | None = None,
         add_topics: tuple[str, ...] = (), remove_topics: tuple[str, ...] = (),
         visibility: str = "", default_branch: str = "", template: bool | None = None,
         features: dict[str, bool] | None = None) -> bool:
    """改仓库设置 (只把变了的项交给 gh); 没有要改的项则返回 False."""
    gh = _gh()
    nwo = _need(target, "edit")
    args = _edit_args(description=description, homepage=homepage, add_topics=add_topics,
                      remove_topics=remove_topics, visibility=visibility,
                      default_branch=default_branch, template=template, features=features)
    if not args:
        console.warn("没有要改的项")
        return False
    console.step(f"更新 {nwo} 的设置 ({len(args)} 个参数) ...")
    ghcli.run(gh, ["repo", "edit", nwo, *args], "修改仓库设置")
    _forget()
    console.done(f"{nwo} 已更新")
    return True


def star(target: str, *, on: bool = True) -> None:
    """收藏 / 取消收藏 (gh 没有 star 子命令, 走它自己的 api 通道)."""
    gh = _gh()
    nwo = _need(target, "star")
    ghcli.run(gh, ["api", "-X", "PUT" if on else "DELETE", f"/user/starred/{nwo}"],
              "收藏仓库" if on else "取消收藏")
    _forget()
    console.done(f"{nwo} 已{'收藏' if on else '取消收藏'}")


def rename(target: str, new_name: str) -> str:
    """改名 (返回新的 owner/repo); 新名字由调用方给或问出来."""
    gh = _gh()
    nwo = _need(target, "rename")
    if not new_name:
        console.error("请给出新名字: gitx repos rename <owner/repo> <新名字>")
    name = new_name.split("/")[-1]
    console.step(f"{nwo} 改名为 {name} ...")
    ghcli.run(gh, ["repo", "rename", name, "--repo", nwo, "--yes"], "改名")
    _forget()
    owner = nwo.split("/")[0]
    console.done(f"{nwo} 已改名为 {owner}/{name}")
    return f"{owner}/{name}"


def delete(target: str, *, yes: bool = False) -> None:
    """删除仓库 (会确认; gh 的 delete 需要 delete_repo 权限)."""
    gh = _gh()
    nwo = _need(target, "delete")
    if not yes and not console.ask(f"永久删除仓库 {nwo}? 此操作不可恢复", default=False):
        console.warn("已取消")
        return
    ghcli.run(gh, ["repo", "delete", nwo, "--yes"], "删除仓库")
    _forget()
    console.done(f"{nwo} 已删除")


def archive(target: str, *, archived: bool = True) -> None:
    """归档 / 取消归档 (归档后仓库变只读)."""
    gh = _gh()
    nwo = _need(target, "archive")
    ghcli.run(gh, ["repo", "archive" if archived else "unarchive", nwo],
              "归档仓库" if archived else "取消归档")
    _forget()
    console.done(f"{nwo} 已{'归档' if archived else '取消归档'}")


def sync(target: str, *, source: str = "", branch: str = "", force: bool = False) -> None:
    """把仓库与源仓库的默认分支对齐 (复刻与上游同步最常用)."""
    gh = _gh()
    nwo = _need(target, "sync")
    args = ["repo", "sync", nwo]
    if source:
        args += ["--source", _nwo(source)]
    if branch:
        args += ["--branch", branch]
    if force:
        args.append("--force")
    console.step(f"同步 {nwo}" + (f" (源 {source})" if source else " (源 = 它的上游)") + " ...")
    ghcli.run(gh, args, "同步仓库")
    _forget()
    console.done(f"{nwo} 已同步")


def set_default(target: str) -> None:
    """把仓库设为当前目录的默认仓库 (gitx 自己的命令之后就不必反复 -R)."""
    gh = _gh()
    nwo = _need(target, "set-default")
    ghcli.run(gh, ["repo", "set-default", nwo], "设置默认仓库")
    console.done(f"当前目录的默认仓库已设为 {nwo}")


def create(name: str, *, visibility: str = "", description: str = "", homepage: str = "",
           readme: bool = False, gitignore: str = "", license_: str = "", template: str = "",
           source: str = "", push: bool = False, clone_: bool = False,
           disable_issues: bool = False, disable_wiki: bool = False, team: str = "") -> None:
    """新建仓库 (owner/名字 或 名字 + --org 交给 gh 自己判定归属)."""
    gh = _gh()
    if visibility and visibility not in ("public", "private", "internal"):
        console.error("可见性只能是 public / private / internal")
    args = ["repo", "create", name]
    if visibility:
        args.append(f"--{visibility}")
    if description:
        args += ["--description", description]
    if homepage:
        args += ["--homepage", homepage]
    if readme:
        args.append("--add-readme")
    if gitignore:
        args += ["--gitignore", gitignore]
    if license_:
        args += ["--license", license_]
    if template:
        args += ["--template", _nwo(template)]
    if team:
        args += ["--team", team]
    if source:
        args += ["--source", source]
    if push:
        args.append("--push")
    if clone_:
        args.append("--clone")
    if disable_issues:
        args.append("--disable-issues")
    if disable_wiki:
        args.append("--disable-wiki")
    console.step(f"新建仓库 {name}" + (" (私有)" if visibility == "private" else "") + " ...")
    ghcli.run(gh, args, "新建仓库")
    _forget()
    console.done(f"{name} 已创建")


def fork(target: str, *, clone_: bool = False, remote: bool = False, org: str = "",
         fork_name: str = "", default_branch_only: bool = False) -> None:
    """复刻仓库到自己的账号 (--clone 顺手克隆到本地, 走 gh 自己的克隆)."""
    gh = _gh()
    nwo = _need(target, "fork")
    args = ["repo", "fork", nwo]
    if clone_:
        args.append("--clone")
    if remote:
        args.append("--remote")
    if org:
        args += ["--org", org]
    if fork_name:
        args += ["--fork-name", fork_name]
    if default_branch_only:
        args.append("--default-branch-only")
    console.step(f"复刻 {nwo} ...")
    ghcli.run(gh, args, "复刻仓库")
    _forget()
    console.done(f"{nwo} 已复刻")


def clone(target: str, dest: str = "", *, depth: int = 1) -> None:
    """克隆到本地: 公开仓库[info]和 gitx download 一样走加速[/info], 私有仓库交给 gh (它自带凭据, 加速镜像拉私有仓库会失败)."""
    gh = _gh()
    nwo = _need(target, "clone")
    name = nwo.split("/")[-1]
    base = os.path.expanduser(dest) if dest else config.default_dest() or "."
    path = os.path.join(base, name)
    if os.path.exists(path):
        console.error(f"目标已存在: {path}\n提示: 换个目录 (--dir) 或先删掉它")
    if _private(nwo):
        console.step(f"私有仓库 {nwo}: 交给 gh 克隆 (自带登录凭据, 不走加速镜像) ...")
        ghcli.run(gh, ["repo", "clone", nwo, path], "克隆仓库")
        console.done(f"完成! 已保存到: {os.path.abspath(path)}")
        return
    download.download(f"https://github.com/{nwo}", path, config.active_proxy(), depth)


def _private(nwo: str) -> bool:
    """仓库是不是私有 / 内部 (查不到就当公开, 继续走加速).

    复用 fetch_repo 的缓存: 克隆前必然要判断可见性, 而这一步单独查要好几秒。
    """
    try:
        repo = fetch_repo(nwo)
    except SystemExit:
        return False
    return str(repo.get("visibility") or "").lower() != "public"


# ---------------------------------------------------------------- 仓库编辑界面

def _branches(nwo: str) -> list[str]:
    """仓库的分支名 (拿不到就返回空表, 由调用方退化成手输)."""
    key = f"{_BRANCHES_PREFIX}{nwo}"
    hit = _recall(key, fresh=False)
    if isinstance(hit, list):
        return [str(name) for name in hit]
    gh = _gh()
    code, out, _ = ghcli.capture(gh, ["api", f"repos/{nwo}/branches", "--paginate",
                                      "--jq", ".[].name"])
    if code != 0:
        return []
    names = [line.strip() for line in out.splitlines() if line.strip()]
    _remember(key, names)
    return names


def _ask_text(prompt: str, current: str) -> str | None:
    """问一个文本项: 回车 = 用当前值 (即不改), 清空再回车 = 清掉, Ctrl+C = 放弃."""
    answer = console.text(prompt, default=current, instruction="[回车] 用当前值  [清空] 清掉这一项")
    return None if answer is None else answer.strip()


def _act_description(nwo: str, repo: dict) -> None:
    current = str(repo.get("description") or "")
    new = _ask_text("新描述 (一行)", current)
    if new is None or new == current:
        console.warn("没有改动")
        return
    edit(nwo, description=new)


def _act_homepage(nwo: str, repo: dict) -> None:
    current = str(repo.get("homepageUrl") or "")
    new = _ask_text("新主页地址", current)
    if new is None or new == current:
        console.warn("没有改动")
        return
    edit(nwo, homepage=new)


def _act_topics(nwo: str, repo: dict) -> None:
    old = _topics(repo)
    answer = console.text(f"话题 (逗号分隔, 当前 {len(old)} 个)",
                          default=", ".join(old),
                          instruction="[回车] 用当前值  [清空] 全删")
    if answer is None:
        return
    new = [t.strip() for t in answer.replace("，", ",").split(",") if t.strip()]
    add = tuple(t for t in new if t not in old)
    remove = tuple(t for t in old if t not in new)
    if not add and not remove:
        console.warn("没有改动")
        return
    edit(nwo, add_topics=add, remove_topics=remove)


def _act_visibility(nwo: str, repo: dict) -> None:
    current = str(repo.get("visibility") or "").lower()
    labels = [f"{zh}{'  · 当前' if value == current else ''}" for value, zh in _VISIBILITY]
    index = console.select("改成哪种可见性?", labels,
                           instruction="[↑↓] 选择  [回车] 确认")
    if index is None or _VISIBILITY[index][0] == current:
        console.warn("没有改动")
        return
    value, zh = _VISIBILITY[index]
    console.warn("改可见性有副作用: 会掉 star / 断掉复刻关系 / 关闭推送规则集")
    if not console.ask(f"确认把 {nwo} 改成 {zh}?", default=False):
        console.warn("已取消")
        return
    edit(nwo, visibility=value)


def _act_branch(nwo: str, repo: dict) -> None:
    current = _branch_of(repo)
    branches = _branches(nwo)
    if not branches:
        new = _ask_text("新的默认分支名", current)
        if new and new != current:
            edit(nwo, default_branch=new)
        else:
            console.warn("没有改动")
        return
    labels = [f"{name}{'  · 当前' if name == current else ''}" for name in branches]
    index = console.select(f"新的默认分支 (共 {len(branches)} 个, 输入即筛选)", labels,
                           instruction="[↑↓] 选择  [输入] 筛选  [回车] 确认")
    if index is None or branches[index] == current:
        console.warn("没有改动")
        return
    edit(nwo, default_branch=branches[index])


def _act_features(nwo: str, repo: dict) -> None:
    labels = [f"{zh} ({'开' if repo.get(field) else '关'})" for field, _, zh in _FEATURES]
    picked = console.check("要打开哪些功能? (空格勾选 / 取消)", labels,
                           instruction="[↑↓] 选择  [空格] 勾选  [输入] 筛选  [回车] 确认",
                           checked=[bool(repo.get(field)) for field, _, _ in _FEATURES])
    if picked is None:
        return
    want = {field: i in picked for i, (field, _, _) in enumerate(_FEATURES)}
    changes = {field: value for field, value in want.items() if value != bool(repo.get(field))}
    if not changes:
        console.warn("没有改动")
        return
    names = " / ".join(f"{zh}{'开' if changes[field] else '关'}"
                       for field, _, zh in _FEATURES if field in changes)
    edit(nwo, features=changes)
    console.info(f"功能已改为: {names}")


def _act_template(nwo: str, repo: dict) -> None:
    current = bool(repo.get("isTemplate"))
    if not console.ask(f"把 {nwo} {'取消模板' if current else '设为模板仓库'}吗?", default=True):
        console.warn("已取消")
        return
    edit(nwo, template=not current)


def _act_archive(nwo: str, repo: dict) -> None:
    current = bool(repo.get("isArchived"))
    if not console.ask(f"{'取消归档' if current else '归档'} {nwo}?"
                       + ("" if current else " (归档后仓库变只读)"), default=True):
        console.warn("已取消")
        return
    archive(nwo, archived=not current)


def _act_delete(nwo: str) -> None:
    console.warn(f"删除 {nwo} 不可恢复 (星标 / 复刻关系 / Issue 一并消失)")
    if not console.ask(f"真的要永久删除 {nwo}?", default=False):
        console.warn("已取消")
        return
    delete(nwo, yes=True)


_ACTIONS: tuple[tuple[str, str], ...] = (
    ("description", "改描述"),
    ("homepage", "改主页"),
    ("topics", "改话题 (topics)"),
    ("visibility", "改可见性 (公开 / 私有 / 内部)"),
    ("branch", "改默认分支"),
    ("features", "功能开关 (议题 / Wiki / 项目 / 讨论)"),
    ("template", "模板仓库开关"),
    ("archive", "归档 / 取消归档"),
    ("star", "收藏 / 取消收藏"),
    ("rename", "改名"),
    ("clone", "克隆到本地 (走加速)"),
    ("web", "打开网页"),
    ("default", "设为当前目录的默认仓库"),
    ("delete", "删除仓库 (危险)"),
    ("switch", "换个仓库"),
    ("quit", "完成, 退出"),
)

def _act(action: str, repo: dict) -> dict | None:
    """执行一项编辑动作; 返回刷新后的仓库 (删了就返回 None, 表示回去重新挑)."""
    nwo = str(repo.get("nameWithOwner") or "")
    if action == "description":
        _act_description(nwo, repo)
    elif action == "homepage":
        _act_homepage(nwo, repo)
    elif action == "topics":
        _act_topics(nwo, repo)
    elif action == "visibility":
        _act_visibility(nwo, repo)
    elif action == "branch":
        _act_branch(nwo, repo)
    elif action == "features":
        _act_features(nwo, repo)
    elif action == "template":
        _act_template(nwo, repo)
    elif action == "archive":
        _act_archive(nwo, repo)
    elif action == "star":
        star(nwo, on=not repo.get("viewerHasStarred"))
    elif action == "rename":
        new = _ask_text("新仓库名 (不含 owner)", nwo.split("/")[-1])
        if new and new != nwo.split("/")[-1]:
            nwo = rename(nwo, new)
        else:
            console.warn("没有改动")
    elif action == "clone":
        clone(nwo)
    elif action == "web":
        view(nwo, web=True)
        return repo
    elif action == "default":
        set_default(nwo)
    elif action == "delete":
        _act_delete(nwo)
        return None if not _exists(nwo) else repo
    return fetch_repo(nwo)


def _exists(nwo: str) -> bool:
    """仓库还在不在 (删除后判断要不要继续编辑它)."""
    gh = _gh()
    return ghcli.capture(gh, ["repo", "view", nwo, "--json", "nameWithOwner"])[0] == 0


def shell(target: str = "", *, owner: str = "", limit: int = DEFAULT_LIMIT, keyword: str = "",
          fresh: bool = False, **filters: object) -> None:
    """交互式仓库管理: 上下键挑仓库 -> 进编辑界面, 一项一项地改到满意.

    界面每轮重画一次当前设置, 因此改完一眼就能看到结果; 选"完成"或 Ctrl+C 退出。
    """
    if not console.is_terminal():
        console.error("编辑界面需要交互终端\n"
                      "提示: 非交互请用 gitx repos edit <owner/repo> 直接给选项")
    repo = (fetch_repo(target, fresh=fresh) if target
            else pick_repo(owner, limit=limit, keyword=keyword, fresh=fresh, **filters))
    if repo is None:
        console.warn("已取消")
        return
    while True:
        _show_settings(repo)
        labels = [label for _, label in _ACTIONS]
        index = console.select("要改哪一项? (输入关键字即筛选)", labels,
                               instruction="[↑↓] 选择  [输入] 筛选  [回车] 确认")
        if index is None or _ACTIONS[index][0] == "quit":
            console.info("已退出仓库编辑界面")
            return
        action = _ACTIONS[index][0]
        if action == "switch":
            repo = pick_repo(owner, limit=limit, keyword=keyword,
                             message="换成哪个仓库?", **filters) or repo
            continue
        repo = _act(action, repo)
        if repo is None:
            console.warn("仓库已删除")
            repo = pick_repo(owner, limit=limit, keyword=keyword,
                             message="继续管理哪个仓库?", **filters)
            if repo is None:
                console.info("已退出仓库编辑界面")
                return
