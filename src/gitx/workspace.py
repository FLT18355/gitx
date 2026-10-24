"""工作区: 把一个 GitHub 项目克隆到指定目录, 并用同一条命令管理所有已克隆的仓库.

  gitx ws owner/repo               克隆到工作区根目录/<repo>
  gitx ws owner/repo 我的目录       克隆到指定目录
  gitx ws                          列出工作区里的全部仓库 (状态 / 分支 / 领先落后)
  gitx ws list|ls                  同上
  gitx ws sync [名字...]            逐个 fetch + 变基拉取 (拉取走加速)
  gitx ws fetch [名字...]           只更新远端跟踪引用
  gitx ws status [名字...]          逐个仓库的改动明细
  gitx ws info <名字>               单个仓库概览 (复用 gitx info)
  gitx ws path <名字>               打印绝对路径 (可 cd "$(gitx ws path x)")
  gitx ws cd <名字>                 同上, 附带一句提示
  gitx ws each <命令...>            在每个仓库里执行一条命令
  gitx ws add <目录...>             把已有的本地克隆登记进来
  gitx ws rm <名字...> [--delete]   从清单移除 (--delete 连目录一起删)
  gitx ws prune                    清理目录已经不存在的清单项
  gitx ws find <关键词>             按名字 / owner/repo / 路径找
  gitx ws root [路径]               查看或设置工作区根目录
  gitx ws use <名字> [--root 目录]   切换默认工作区 (不存在就新建, 之后的命令都作用在它上面)
  gitx ws spaces                    列出所有工作区 (默认的标出来)
  gitx ws drop <名字> [--delete]     删除工作区 (--delete 连仓库目录一起删)

清单存放在 ~/.config/gitx/workspaces.json (纯本地状态, 删掉只会丢清单, 不影响仓库本身),
结构是 {default, spaces: {名字: {root, repos}}}; 旧版单工作区清单读取时自动升级.
默认工作区优先级: 命令行 -s/--space > GITX_WS_SPACE > 清单里的 default.
根目录优先级: --root (单次) > 工作区自己的 root (gitx ws root / use) > 配置 workspace > ~/gitx-workspaces.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from . import config, console, download, gitcmd, github

DEFAULT_ROOT = "~/gitx-workspaces"
DEFAULT_SPACE = "default"   # 默认工作区的名字
_REGISTRY = "workspaces.json"


# ---------------------------------------------------------------- 清单 (JSON)

def registry_path() -> Path:
    return config.config_dir() / _REGISTRY


def _default_root() -> str:
    """新工作区的默认根目录: default 用 ~/gitx-workspaces, 具名用其下的同名目录."""
    configured = str(config.load().get("workspace") or "").strip()
    return os.path.abspath(os.path.expanduser(configured or DEFAULT_ROOT))


def _space_root(name: str, configured: str = "") -> str:
    if configured:
        return os.path.abspath(os.path.expanduser(configured))
    if name == DEFAULT_SPACE:
        return _default_root()
    return os.path.join(_default_root(), name)


def normalize(data: object) -> dict:
    """把 v1 (单一 repos) / v2 (spaces + default) 清单统一成 v2 结构."""
    if not isinstance(data, dict):
        return {"version": 2, "default": DEFAULT_SPACE,
                "spaces": {DEFAULT_SPACE: {"root": _default_root(), "repos": {}}}}
    if isinstance(data.get("spaces"), dict):
        spaces: dict[str, dict] = {}
        for name, item in data["spaces"].items():
            if not isinstance(item, dict):
                continue
            repos = item.get("repos")
            spaces[str(name)] = {
                "root": _space_root(str(name), str(item.get("root") or "")),
                "repos": {str(k): v for k, v in repos.items() if isinstance(v, dict)}
                if isinstance(repos, dict) else {},
            }
        chosen = str(data.get("default") or "")
        if chosen not in spaces:
            chosen = next(iter(spaces), DEFAULT_SPACE)
        spaces.setdefault(DEFAULT_SPACE, {"root": _default_root(), "repos": {}})
        # 配置项 workspace 是"默认工作区根目录"的镜像: 手改配置文件也能生效
        configured = str(config.load().get("workspace") or "").strip()
        if configured and chosen in spaces:
            spaces[chosen]["root"] = os.path.abspath(os.path.expanduser(configured))
        return {"version": 2, "default": chosen, "spaces": spaces}
    repos = data.get("repos")
    old = {str(k): v for k, v in repos.items() if isinstance(v, dict)} if isinstance(repos, dict) else {}
    return {"version": 2, "default": DEFAULT_SPACE,
            "spaces": {DEFAULT_SPACE: {"root": _default_root(), "repos": old}}}


def load_registry() -> dict:
    """读清单 (自动兼容并迁移旧格式); 坏文件当空清单 (不阻断使用)."""
    path = registry_path()
    try:
        raw = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        raw = None
    data = normalize(raw)
    if not isinstance(raw, dict) or raw.get("version") != 2 or "spaces" not in raw:
        save_registry(data)  # 旧版 / 坏文件: 顺手升级成新结构
    return data


def save_registry(data: dict) -> None:
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(normalize(data), ensure_ascii=False, indent=2), "utf-8")
    tmp.replace(path)


def space_name(flag: str = "") -> str:
    """生效的工作区名: 命令行 -s > 环境变量 GITX_WS_SPACE > 清单里的默认工作区."""
    if flag:
        return flag
    env = os.environ.get("GITX_WS_SPACE", "").strip()
    if env:
        return env
    return str(load_registry().get("default") or DEFAULT_SPACE)


def _ensure(data: dict, chosen: str) -> dict:
    """确保 data 里有这个工作区 (没有就按默认根目录登记一份)."""
    spaces = data["spaces"]
    spaces.setdefault(chosen, {"root": _space_root(chosen), "repos": {}})
    return spaces[chosen]


def get_space(name: str = "", *, required: bool = False) -> tuple[str, dict]:
    """取 (工作区名, 工作区数据); 不存在时 required 报错, 否则按默认根目录创建."""
    chosen = space_name(name)
    data = load_registry()
    if required and chosen not in data["spaces"]:
        console.error(f"没有工作区 {chosen!r} (现有: {', '.join(data['spaces'])})\n"
                      f"提示: 新建并切换: gitx ws use {chosen} [--root 目录]")
    return chosen, _ensure(data, chosen)


def root(name: str = "") -> str:
    """工作区根目录 (展开 ~); 未设置用默认值."""
    return str(get_space(name)[1]["root"])


def set_root(path: str, name: str = "") -> None:
    """设置某个工作区 (缺省 = 默认工作区) 的根目录."""
    chosen = get_space(name)[0]
    value = os.path.abspath(os.path.expanduser(path))
    os.makedirs(value, exist_ok=True)
    data = load_registry()
    data["spaces"][chosen]["root"] = value
    save_registry(data)
    if chosen == data["default"]:
        config.save({**config.load(), "workspace": value})  # 同步到配置文件, 便于查看
    console.done(f"工作区 {chosen} 的根目录: {value}")


def create(name: str, dir_: str = "", *, use_: bool = False) -> None:
    """新建工作区 (已存在则更新根目录); use_ 时顺带设为默认."""
    data = load_registry()
    spaces = data["spaces"]
    existed = name in spaces
    if existed and not dir_:
        console.error(f"工作区 {name!r} 已存在 ({spaces[name]['root']})")
    root_path = os.path.abspath(os.path.expanduser(dir_)) if dir_ else _space_root(name)
    os.makedirs(root_path, exist_ok=True)
    spaces.setdefault(name, {"root": root_path, "repos": {}})
    spaces[name]["root"] = root_path
    if use_:
        data["default"] = name
    save_registry(data)
    label = "已存在, 根目录已更新" if existed else "已新建"
    console.done(f"工作区 {name} {label}: {root_path}")
    if use_:
        console.done(f"默认工作区: {name}")


def use(name: str, dir_: str = "") -> None:
    """切换默认工作区; 不存在就新建 (根目录缺省 = ~/gitx-workspaces/<名字>)."""
    data = load_registry()
    spaces = data["spaces"]
    if name not in spaces:
        root_path = _space_root(name, dir_)
        os.makedirs(root_path, exist_ok=True)
        spaces[name] = {"root": root_path, "repos": {}}
        console.info(f"已新建工作区 {name}: {root_path}")
    elif dir_:
        spaces[name]["root"] = os.path.abspath(os.path.expanduser(dir_))
    data["default"] = name
    save_registry(data)
    info = spaces[name]
    # 默认工作区的根目录同步进配置, `gitx config` 里能直接看到
    if str(config.load().get("workspace") or "") != info["root"]:
        config.save({**config.load(), "workspace": info["root"]})
    console.done(f"默认工作区: {name} ({info['root']}, {len(info['repos'])} 个仓库)")


def list_spaces() -> None:
    """列出所有工作区 (默认的标出来)."""
    data = load_registry()
    table = console.table("工作区", "仓库", "根目录")
    for name, item in data["spaces"].items():
        label = f"{name}  (默认)" if name == data["default"] else name
        table.add_row(console.txt(label), console.txt(len(item["repos"])),
                      console.txt(str(item["root"])))
    console.print(table)
    console.info("切换/新建默认工作区: gitx ws use <名字> [--root 目录]   |   删除: gitx ws drop <名字>")


def drop_space(name: str, *, delete: bool = False, yes: bool = False) -> None:
    data = load_registry()
    if name not in data["spaces"]:
        console.error(f"没有工作区 {name!r}")
    if len(data["spaces"]) == 1:
        console.error("只剩一个工作区, 不能删除 (可用 gitx ws rm 移除仓库)")
    repositories = data["spaces"][name]["repos"]
    if repositories and delete:
        if not yes and not console.ask(f"确认删除 {name} 里的 {len(repositories)} 个目录?", default=False):
            console.error("已取消")
        for item in repositories.values():
            path = str(item.get("path") or "")
            if path and os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
    data["spaces"].pop(name, None)
    if data["default"] == name:
        data["default"] = next(iter(data["spaces"]))
        fallback = data["spaces"][data["default"]]["root"]
        config.save({**config.load(), "workspace": fallback})
    save_registry(data)
    console.done(f"已删除工作区 {name}" + (" (目录已删除)" if delete else " (目录保留)"))
    console.info(f"默认工作区: {data['default']}")


def _unique_name(repos: dict, name: str) -> str:
    if name not in repos:
        return name
    i = 2
    while f"{name}-{i}" in repos:
        i += 1
    return f"{name}-{i}"


def _register(path: str, *, owner: str = "", repo: str = "", url: str = "",
              name: str = "", space_name_: str = "") -> str:
    """登记一个仓库目录 (默认工作区); 已登记 (同路径) 则原样返回名字."""
    data = load_registry()
    chosen = space_name(space_name_)
    repos = _ensure(data, chosen)["repos"]
    absolute = os.path.abspath(path)
    for key, item in repos.items():
        if os.path.abspath(str(item.get("path") or "")) == absolute:
            item.update({"path": absolute, "owner": owner or item.get("owner", ""),
                         "repo": repo or item.get("repo", ""), "url": url or item.get("url", "")})
            save_registry(data)
            return key
    key = _unique_name(repos, name or os.path.basename(absolute) or "repo")
    repos[key] = {
        "path": absolute, "owner": owner, "repo": repo, "url": url,
        "added": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_registry(data)
    return key


def _describe(item: dict) -> str:
    owner, repo = str(item.get("owner") or ""), str(item.get("repo") or "")
    return f"{owner}/{repo}" if owner and repo else os.path.basename(str(item.get("path") or ""))


# ---------------------------------------------------------------- 挑选

def _select(names: list[str], *, all_: bool = False, space_name_: str = "") -> list[tuple[str, dict]]:
    """按名字 / owner/repo / 路径子串挑选; 没给名字且 all_ = 全部; 否则报错退出."""
    chosen, item = get_space(space_name_, required=True)
    repos = item["repos"]
    if not repos:
        console.error(f"工作区 {chosen} 还是空的, 先克隆一个: gitx ws owner/repo")
    if not names and all_:
        return list(repos.items())
    if not names:
        console.error("请指定仓库名 (gitx ws list 看清单; 或用 --all)")
    picked: list[tuple[str, dict]] = []
    for query in names:
        q = query.strip().rstrip("/")
        hit = [(k, v) for k, v in repos.items()
               if q in (k, _describe(v), os.path.basename(str(v.get("path") or "")))
               or q in str(v.get("path") or "")]
        if not hit:
            console.error(f"清单里没有匹配 {query!r} 的仓库 (gitx ws list)")
        for item in hit:
            if item not in picked:
                picked.append(item)
    return picked


# ---------------------------------------------------------------- 克隆

def clone(target: str, dest: str = "", *, depth: int | None = None, branch: str = "",
          proxy: str | None = None, no_proxy: bool = False, submodules: bool = False,
          name: str = "", root_override: str = "", space: str = "") -> str:
    """克隆一个 GitHub 仓库 (走加速) 并登记到工作区; 返回本地绝对路径."""
    chosen = space_name(space)
    if os.path.isdir(target) and not dest:  # 已在本地且没指定目标: 等价 add
        return register_path(target, space=space)
    try:
        info = github.parse_url(target)
    except ValueError as exc:
        # 本地目录 / file:// / 任意 git 地址也支持 (镜像源、内网仓库都能登记管理)
        if target.startswith(("file://", "git://", "ssh://", "/", "./", "~")) or os.path.isdir(target):
            return _clone_local(target, dest, depth=depth, branch=branch, name=name,
                                root_override=root_override, submodules=submodules, space=space)
        console.error(f"{exc}\n提示: 也支持 owner/repo 简写, 如 gitx ws cli/cli")
    if info["mode"] != "repo":
        console.error(f"只支持整仓库链接 ({info['mode']} 链接请用 gitx download)")
    if dest:
        path = os.path.abspath(os.path.expanduser(dest))
        if os.path.isdir(path) and not path.endswith(info["repo"]):
            path = os.path.join(path, info["repo"])  # 目录已存在 -> 视为父目录
    else:
        base = root_override or root(space)
        path = os.path.join(base, name or info["repo"])
    if os.path.isdir(path):
        if gitcmd.is_repo(path):
            key = _register(path, owner=info["owner"], repo=info["repo"],
                            url=f"https://github.com/{info['owner']}/{info['repo']}",
                            name=name or info["repo"], space_name_=chosen)
            console.info(f"目录已存在, 已登记为 {key}: {path}")
            return path
        console.error(f"目标已存在且不是 git 仓库: {path}")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    cfg = config.load()
    prefix = config.active_proxy(proxy, no_proxy, cfg=cfg)
    if depth is None:
        depth = int(cfg.get("depth", 1) or 1)
    try:
        download.run(info, path, prefix, depth, branch, submodules=submodules)
    except SystemExit:
        shutil.rmtree(path, ignore_errors=True)  # 失败不留半截目录
        raise
    key = _register(path, owner=info["owner"], repo=info["repo"],
                    url=f"https://github.com/{info['owner']}/{info['repo']}",
                    name=name or info["repo"], space_name_=chosen)
    console.info(f"已登记为 {key}  |  进入: cd \"$(gitx ws path {key})\"")
    return path


def _clone_local(source: str, dest: str = "", *, depth: int | None = None, branch: str = "",
                 name: str = "", root_override: str = "", submodules: bool = False,
                 space: str = "") -> str:
    """克隆任意本地 / 非 GitHub git 地址 (走普通 git, 仍登记进工作区)."""
    src = source if source.startswith(("file://", "git://", "ssh://")) else \
        os.path.abspath(os.path.expanduser(source))
    repo_name = os.path.basename(src.rstrip("/")).removesuffix(".git")
    path = os.path.abspath(os.path.expanduser(dest)) if dest else os.path.join(
        root_override or root(space), name or repo_name)
    if os.path.isdir(path) and gitcmd.is_repo(path):
        console.info(f"目录已存在, 已登记: {path}")
        return register_path(path, name=name or repo_name, space=space)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    args = ["git", "clone"]
    if depth:
        args += ["--depth", str(depth)]
    if branch:
        args += ["--branch", branch]
    if submodules:
        args.append("--recurse-submodules")
    console.step(f"正在克隆 {src}")
    if subprocess.run([*args, src, path]).returncode != 0:
        shutil.rmtree(path, ignore_errors=True)
        console.error("克隆失败 (检查地址 / 权限)")
    key = _register(path, name=name or repo_name, space_name_=space_name(space))
    console.done(f"完成! 已登记为 {key}: {path}")
    return path


def register_path(path: str, *, name: str = "", space: str = "") -> str:
    """把已有本地克隆登记进工作区 (必须是 git 仓库)."""
    absolute = os.path.abspath(os.path.expanduser(path))
    if gitcmd.capture(["git", "-C", absolute, "rev-parse", "--is-bare-repository"])[1] == "true":
        console.error(f"{absolute} 是裸仓库 (bare), 不能作为工作区仓库")
    gitcmd.require_repo(absolute)
    parsed = github.owner_repo(gitcmd.remote_url(config.default_remote(), absolute))
    owner, repo_name = parsed if parsed else ("", "")
    key = _register(absolute, owner=owner, repo=repo_name, name=name, space_name_=space_name(space))
    console.done(f"已登记 {key}: {absolute}")
    return absolute


# ---------------------------------------------------------------- 查看

def list_repos(space: str = "") -> None:
    """工作区总览: 名称 / 仓库 / 分支 / 改动 / 领先落后 / 最近提交."""
    chosen, current = get_space(space, required=True)
    repos = current["repos"]
    if not repos:
        console.info(f"工作区 {chosen} 是空的 (根目录 {current['root']})")
        console.info("克隆: gitx ws owner/repo   |   登记已有目录: gitx ws add <目录>")
        return
    table = console.table("名称", "仓库", "分支", "改动", "领先/落后", "最近提交", "路径",
                          title=f"工作区 {chosen} (共 {len(repos)} 个)")
    missing = 0
    for key, item in repos.items():
        path = str(item.get("path") or "")
        if not os.path.isdir(path) or not gitcmd.is_repo(path):
            missing += 1
            table.add_row(console.txt(key), console.txt(_describe(item)), console.txt("-"),
                          console.txt("缺失"), console.txt("-"), console.txt("-"),
                          console.txt(path + " (可 gitx ws prune)"))
            continue
        staged, modified, untracked, conflicts = gitcmd.status_counts(path)
        changes = []
        if staged:
            changes.append(f"+{staged}")
        if modified:
            changes.append(f"~{modified}")
        if untracked:
            changes.append(f"?{untracked}")
        if conflicts:
            changes.append(f"!{conflicts}")
        behind, ahead = gitcmd.behind_ahead(path)
        track = f"{ahead}/{behind}" if behind >= 0 else "-"
        table.add_row(console.txt(key), console.txt(_describe(item)),
                      console.txt(gitcmd.current_branch(path) or "-"),
                      console.txt(" ".join(changes) or "干净"), console.txt(track),
                      console.txt(_brief(item)), console.txt(path))
    console.print(table)
    console.info(f"根目录 {current['root']}  |  清单 {registry_path()}  |  克隆: gitx ws owner/repo")
    if missing:
        console.warn(f"{missing} 个目录已不存在, 可: gitx ws prune")


def _brief(item: dict) -> str:
    path = str(item.get("path") or "")
    line = gitcmd.commit_brief("HEAD", path)
    if not line:
        return "-"
    parts = [*line.split("|", 3), "", "", "", ""]
    return f"{parts[0]} {parts[1]} {parts[3][:32]}"


def status(names: list[str], *, all_: bool = False, space: str = "") -> None:
    picked = _select(names, all_=all_ or not names, space_name_=space)
    for key, item in picked:
        path = str(item.get("path") or "")
        console.print(f"[key]{key}[/key] [dim]{_describe(item)}[/dim]")
        if not os.path.isdir(path) or not gitcmd.is_repo(path):
            console.warn(f"目录不存在 / 不是仓库: {path}")
            continue
        staged, modified, untracked, conflicts = gitcmd.status_counts(path)
        behind, ahead = gitcmd.behind_ahead(path)
        upstream = gitcmd.upstream_of("HEAD", path) or "(无上游)"
        console.print(f"  分支 {gitcmd.current_branch(path) or '-'}  ->  {upstream}"
                      f"   领先 {ahead if ahead >= 0 else '-'} / 落后 {behind if behind >= 0 else '-'}")
        console.print(f"  暂存 {staged}  已修改 {modified}  未跟踪 {untracked}  冲突 {conflicts}")
        console.print(f"  {path}")


def info(name: str, *, space: str = "") -> None:
    from . import repo as repo_module

    picked = _select([name], space_name_=space)
    _, item = picked[0]
    repo_module.info(str(item.get("path") or "."))


def resolve_path(name: str, *, space: str = "") -> str:
    """按名字 / owner/repo / 路径取仓库的绝对路径 (命令: gitx ws path / cd)."""
    picked = _select([name], space_name_=space)
    return str(picked[0][1].get("path") or "")


def find(keyword: str, *, space: str = "") -> None:
    repos = get_space(space, required=True)[1]["repos"]
    q = keyword.lower()
    hits = [(k, v) for k, v in repos.items()
            if q in k.lower() or q in _describe(v).lower() or q in str(v.get("path") or "").lower()]
    if not hits:
        console.warn(f"没有匹配 {keyword!r} 的仓库")
        return
    table = console.table("名称", "仓库", "路径", title=f"匹配 {keyword!r}")
    for key, item in hits:
        table.add_row(console.txt(key), console.txt(_describe(item)),
                      console.txt(str(item.get("path") or "")))
    console.print(table)


# ---------------------------------------------------------------- 同步

def _fetch_or_pull(item: dict, prefix: str | None, *, pull: bool) -> tuple[str, str]:
    """返回 (状态, 说明); 不抛异常, 单个失败不影响其余."""
    path = str(item.get("path") or "")
    if not os.path.isdir(path) or not gitcmd.is_repo(path):
        return "缺失", path
    if not gitcmd.remote_url(config.default_remote(), path):
        return "无远程", path
    if not gitcmd.fetch_remote(path, prefix=prefix):
        return "失败", "fetch 失败 (可 --no-proxy 直连)"
    if not pull:
        return "已更新", path
    if not gitcmd.has_upstream(path):
        return "仅 fetch", "分支没有上游, 跳过合并"
    staged, modified, untracked, _ = gitcmd.status_counts(path)
    if staged or modified or untracked:
        return "仅 fetch", "工作区有改动, 跳过合并 (先提交 / 暂存)"
    if not gitcmd.pull(path, rebase=bool(config.load().get("sync_rebase", True)), prefix=prefix):
        return "失败", "拉取失败 (可能有冲突, 用 gitx status 查看)"
    return "已同步", path


def sync(names: list[str], *, pull: bool = True, all_: bool = False,
         proxy: str | None = None, no_proxy: bool = False, jobs: int = 1,
         space: str = "") -> None:
    picked = _select(names, all_=all_ or not names, space_name_=space)
    prefix = config.active_proxy(proxy, no_proxy)
    console.step(f"{'同步' if pull else '更新'} {len(picked)} 个仓库"
                 + (" [加速]" if prefix else ""))
    results: list[tuple[str, str, str]] = []
    if jobs > 1 and len(picked) > 1 and hasattr(os, "fork"):
        results = _parallel(picked, prefix, pull, jobs)
    else:
        for key, item in picked:
            results.append((key, *_fetch_or_pull(item, prefix, pull=pull)))
    table = console.table("名称", "结果", "说明")
    bad = 0
    for key, state, detail in results:
        if state not in ("已同步", "已更新", "仅 fetch"):
            bad += 1
        table.add_row(console.txt(key), console.txt(state), console.txt(detail))
    console.print(table)
    if bad:
        console.warn(f"{bad} 个仓库未能同步, 见上表")
    else:
        console.done("全部完成")


def _parallel(picked: list[tuple[str, dict]], prefix: str | None, pull: bool,
              jobs: int) -> list[tuple[str, str, str]]:
    """fork 并行同步 (每个子进程只写自己的结果文件, 父进程汇总)."""
    import tempfile

    results: list[tuple[str, str, str]] = []
    pending = list(picked)
    running: list[tuple[int, int, str, str]] = []
    tmpdir = tempfile.mkdtemp(prefix="gitx-ws-")
    index = 0
    try:
        while pending or running:
            while pending and len(running) < max(1, jobs):
                key, item = pending.pop(0)
                out = os.path.join(tmpdir, str(index))
                pid = os.fork()
                if pid == 0:  # 子进程
                    try:
                        state, detail = _fetch_or_pull(item, prefix, pull=pull)
                    except BaseException as exc:  # noqa: BLE001
                        state, detail = "失败", str(exc)
                    try:
                        with open(out, "w", encoding="utf-8") as handle:
                            handle.write(f"{state}\t{detail}")
                    finally:
                        os._exit(0)
                running.append((pid, index, key, out))
                index += 1
            pid, _, key, out = running.pop(0)
            os.waitpid(pid, 0)
            try:
                state, detail = Path(out).read_text("utf-8").split("\t", 1)
            except (OSError, ValueError):
                state, detail = "失败", "子进程没有返回结果"
            results.append((key, state, detail))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return results


# ---------------------------------------------------------------- 每个仓库执行

def each(command: list[str], names: list[str], *, all_: bool = False, space: str = "") -> None:
    """在选中的每个仓库目录里执行一条命令 (按清单顺序)."""
    if not command:
        console.error("用法: gitx ws each <命令...>  例: gitx ws each git status -s")
    picked = _select(names, all_=all_ or not names, space_name_=space)
    failed: list[str] = []
    for key, item in picked:
        path = str(item.get("path") or "")
        console.print(f"[key]==> {key}[/key] [dim]{path}[/dim]")
        if not os.path.isdir(path):
            console.warn("目录不存在, 跳过")
            failed.append(key)
            continue
        if subprocess.run(command, cwd=path).returncode != 0:
            failed.append(key)
    if failed:
        console.error("执行失败的仓库: " + ", ".join(failed))
    console.done(f"已在 {len(picked) - len(failed)} 个仓库执行完成")


# ---------------------------------------------------------------- 清理

def remove(names: list[str], *, delete: bool = False, yes: bool = False,
           space: str = "") -> None:
    chosen = space_name(space)
    picked = _select(names, space_name_=chosen)
    data = load_registry()
    repos = _ensure(data, chosen)["repos"]
    for key, item in picked:
        path = str(item.get("path") or "")
        if delete and os.path.isdir(path):
            console.warn(f"将删除目录: {path}")
            if not yes and not console.ask(f"确认删除 {key} 的整个目录?", default=False):
                console.info(f"跳过 {key}")
                continue
            shutil.rmtree(path)
        repos.pop(key, None)
        save_registry(data)
        console.done(f"已从清单移除 {key}" + (" (目录已删除)" if delete else ""))


def prune(space: str = "") -> None:
    """清掉目录已经不存在的清单项."""
    chosen = space_name(space)
    data = load_registry()
    repos = _ensure(data, chosen)["repos"]
    gone = [k for k, item in repos.items() if not os.path.isdir(str(item.get("path") or ""))]
    if not gone:
        console.info("清单干净, 没有失效项")
        return
    for key in gone:
        console.print(f"  [dim]移除 {key}[/dim]")
        repos.pop(key, None)
    save_registry(data)
    console.done(f"工作区 {chosen}: 已清理 {len(gone)} 个失效项")
