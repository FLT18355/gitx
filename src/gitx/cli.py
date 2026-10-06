"""gitx 命令行入口: 用 Typer + Rich 构建的分组式 CLI.

命令分组:
  下载 (download / clone / release)   同步 (push / pull / sync / fetch)
  仓库 (init / info / commit / diff / discard / clean / undo / graph / tidy / url)
  分支 (branch / switch / merge / rebase)  暂存 (stash)  标签 (tag)
  探索 (search / stat / web / ignore)      加速 (proxy ...)  配置 (config ... / doctor)
非 gitx 自己的词一律透传 git (gitx status / gitx log --oneline), 这条快速通道
由 dispatch.py 在导入 typer 之前处理, 因此几乎瞬时完成。
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Annotated, Optional

import typer
from rich.markup import escape

from . import (__version__, accel, branch, config, console, download, gitcmd, github, hub,
               release, repo, stash, sync, tag)

PANEL_DL = "下载 (默认加速)"
PANEL_SYNC = "同步"
PANEL_REPO = "仓库 (提交 / 改动 / 历史)"
PANEL_BRANCH = "分支 (切换 / 合并 / 变基)"
PANEL_WIP = "暂存与标签"
PANEL_HUB = "探索 (搜索 / 网页 / 模板)"
PANEL_PROXY = "加速管理"
PANEL_CONF = "配置与自检"

_CFG_KEYS = "/".join(config.DEFAULTS)

_HELP = f"""[key]gitx[/key] -- 给中国人用的 GitHub 加速与同步工具 [dim]v{__version__}[/dim]

拉取 (克隆 / 文件 / Release 附件 / API) 默认走加速镜像 [num]{accel.PROVIDERS['v6']}[/num], 推送直连 GitHub。
直接给一个 GitHub 链接即可下载: [key]gitx https://github.com/owner/repo[/key]
其它词一律透传 git, 且不加载 typer, 因此几乎瞬时: [key]gitx status[/key] / [key]gitx log --oneline[/key]"""

_EPILOG = """[key]示例[/key]
  gitx https://github.com/owner/repo                下载仓库 -> ./repo
  gitx https://github.com/owner/repo/tree/main/src  只下载某个文件夹 (部分克隆, 实测快 8 倍)
  gitx https://github.com/owner/repo -x             下载并解压源码包 (不用 git, 只取一个流)
  gitx release cli/cli --list                       看最新发布的附件清单
  gitx release cli/cli --asset '*linux_amd64*'      只下匹配的附件
  gitx search "cli 工具" --language go -d           搜仓库并下载第 1 个
  gitx stat cli/cli                                 看仓库概览 (★ star / topics / 语言 / 贡献者)
  gitx graph -n 30                                  带图形的提交历史
  gitx switch -c 新功能                              新建分支并切换
  gitx branch                                       看分支表 (上游 / 领先落后)
  gitx merge main                                   把 main 合并进来
  gitx stash save "改到一半"                          暂存当前改动
  gitx tag new v1.0.0 "首个正式版" && gitx tag push   打标签并推送
  gitx diff --staged                                看上色后的暂存区改动
  gitx tidy --gc                                    仓库体检 + 打包瘦身
  gitx url accel                                    让 origin 拉取走加速
  gitx proxy auto                                   自动测速并选用最快加速源
  gitx proxy release on gh-proxy                    只给 Release 换加速源 (与其它功能分开)

环境变量 [num]GITX_PROXY[/num] = off | v6 | gh-proxy | https://... 可设置全局默认加速源,
[num]GITX_RELEASE_PROXY[/num] 单独覆盖 Release 功能的加速源。"""

app = typer.Typer(
    name="gitx",
    help=_HELP,
    epilog=_EPILOG,
    rich_markup_mode="rich",
    no_args_is_help=False,  # 空参数走 _welcome: 状态 + 常用命令速查, 而不是全量帮助
    invoke_without_command=True,  # 无子命令时也要进 callback (否则 click 直接报错)
    add_completion=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"[key]gitx[/key] {__version__}")
        raise typer.Exit()


# 只输入 gitx 时的速查表: (命令示例, 一句话说明)
_WELCOME_TIPS: tuple[tuple[str, str], ...] = (
    ("gitx <GitHub 链接>", "下载仓库 / 文件夹 / 文件 / 源码包 (默认加速)"),
    ("gitx release owner/repo", "交互式挑选并下载 Release 附件"),
    ("gitx sync", "先拉取再推送, 一步完成日常同步 (默认变基)"),
    ("gitx push / gitx pull", "提交并推送 / 拉取远端更新"),
    ("gitx info", "仓库概览: 状态 / 领先落后 / 最近提交"),
    ("gitx branch", "分支表; 切换 switch / 合并 merge / 变基 rebase"),
    ("gitx stash / gitx tag", "暂存与标签的保存 / 查看 / 恢复"),
    ("gitx commit -m / gitx diff", "提交改动 / 查看上色 diff"),
    ("gitx search <关键词>", "搜索 GitHub 仓库 (加 -d 直接下载)"),
    ("gitx stat owner/repo", "仓库信息: star / 语言 / 贡献者 / 最新发布"),
    ("gitx proxy auto", "实测测速, 自动选用最快的加速源"),
    ("gitx -h", "查看全部命令与选项"),
)


def _welcome() -> None:
    """只输入 `gitx` 时的输出: 版本 + 加速状态 + 常用命令速查 (全量帮助见 `gitx -h`)."""
    cfg = config.load()
    name = str(cfg.get("proxy", "v6"))
    prefix = _resolvable(name)
    pull = f"{name} ({prefix})" if prefix else f"{name} (直连, 未加速)"
    console.print(console.styled(
        f"[key]gitx[/key] [dim]v{__version__}[/dim]   "
        "[dim]给中国人用的 GitHub 加速与同步工具[/dim]"))
    console.print(console.styled(f"[dim]拉取[/dim] {escape(pull)} "
                                 "[dim]· 推送直连 GitHub[/dim]"))
    console.print()
    tips = console.table("常用命令", "说明", title="快速上手")
    for cmd, desc in _WELCOME_TIPS:
        tips.add_row(console.txt(cmd), console.txt(desc))
    console.print(tips)
    console.info("环境自检: gitx doctor   |   其它词透传 git: gitx status / gitx log --oneline")


@app.callback()
def _root(
    ctx: typer.Context,
    version: Annotated[bool, typer.Option("--version", "-V", callback=_version_callback,
                                          is_eager=True, help="显示版本并退出")] = False,
) -> None:
    # 无子命令 = 欢迎页 (no_args_is_help 关闭后由这里接管)
    if ctx.invoked_subcommand is None:
        _welcome()
        raise typer.Exit()
    del version


# ================================================================ 下载

@app.command("download", rich_help_panel=PANEL_DL)
def download_cmd(
    url: Annotated[str, typer.Argument(metavar="URL", help="GitHub 链接: 仓库 / tree / blob / releases")],
    dest: Annotated[Optional[str], typer.Argument(metavar="目标路径", help="保存位置, 默认用仓库名")] = None,
    branch: Annotated[str, typer.Option("--branch", "-b", help="指定分支")] = "",
    depth: Annotated[Optional[int], typer.Option("--depth", "-d", help="克隆深度, 0 = 完整克隆")] = None,
    archive: Annotated[bool, typer.Option("--archive", "-x", "--tarball",
                                          help="下载源码包 tar.gz, 不用 git (不要历史时最快)")] = False,
    extract: Annotated[bool, typer.Option("--extract", "-X", help="下载源码包并直接解压 (隐含 -x)")] = False,
    submodules: Annotated[bool, typer.Option("--submodules", help="连同子模组一起拉取 (同样走加速)")] = False,
    fresh: Annotated[bool, typer.Option("--fresh", help="忽略 .part 断点, 从零下载")] = False,
    list_only: Annotated[bool, typer.Option("--list", "-l", help="仅列出附件 (发布页链接)")] = False,
    limit: Annotated[int, typer.Option("--limit", "-n", help="发布列表条数 (发布页链接挑选发布用, 最多 100)")] = release.DEFAULT_LIMIT,
    assets: Annotated[Optional[list[str]], typer.Option("--asset", "-a", help="仅下载匹配的附件, 可重复")] = None,
    source: Annotated[bool, typer.Option("--source", help="额外下载源码包 (发布页链接)")] = False,
    proxy: Annotated[Optional[str], typer.Option("--proxy", help="本次使用的加速源: v6 / v4 / gh-proxy / https://...")] = None,
    no_proxy: Annotated[bool, typer.Option("--no-proxy", help="本次直连, 不走加速")] = False,
) -> None:
    """下载仓库 / 文件夹 / 单个文件 / 源码包 / Release 附件, [info]默认走加速[/info].

    要历史用 [key]git clone[/key] 路线 (浅克隆), 只要文件树用 [key]-x[/key] 源码包路线,
    只要某个目录用 [key]tree[/key] 链接 (部分克隆 + 稀疏检出), 单个文件用 [key]blob[/key] 链接。
    """
    _do_download(url, dest, depth, branch, proxy, no_proxy,
                 list_only=list_only, assets=assets, source=source, limit=limit,
                 archive=archive or extract, extract=extract, submodules=submodules, fresh=fresh)


app.command("clone", hidden=True, rich_help_panel=PANEL_DL,
            help="download 的别名")(download_cmd)


@app.command("release", rich_help_panel=PANEL_DL)
def release_cmd(
    target: Annotated[str, typer.Argument(metavar="仓库|链接", help="owner/repo 或发布页 / 附件链接")],
    tag: Annotated[str, typer.Option("--tag", "-t", help="Release 标签, 默认最新")] = "",
    tags: Annotated[bool, typer.Option("--tags", help="列出最近的 Release, 不下载")] = False,
    limit: Annotated[int, typer.Option("--limit", "-n", help="发布列表条数 (挑选发布与 --tags 用, 最多 100)")] = release.DEFAULT_LIMIT,
    assets: Annotated[Optional[list[str]], typer.Option("--asset", "-a", help="只下载匹配的附件 (支持通配, 可重复)")] = None,
    pick: Annotated[bool, typer.Option("--pick", "-i", "--choose", help="交互式挑选发布与附件 (含预发布)")] = False,
    list_only: Annotated[bool, typer.Option("--list", "-l", help="只列出附件清单, 不下载")] = False,
    source: Annotated[bool, typer.Option("--source", help="额外下载源码包 (tarball)")] = False,
    output: Annotated[str, typer.Option("--output", "-o", help="保存目录")] = ".",
    refresh: Annotated[bool, typer.Option("--fresh", help="忽略 .part 断点, 从零下载")] = False,
    proxy: Annotated[Optional[str], typer.Option("--proxy", help="本次使用的加速源: v6 / v4 / gh-proxy / https://...")] = None,
    no_proxy: Annotated[bool, typer.Option("--no-proxy", help="本次直连, 不走加速")] = False,
) -> None:
    """通过 GitHub API 列出并下载 Release 附件, [info]默认走加速[/info].

    终端里直接 [key]gitx release owner/repo[/key] 会先让你挑发布 (含预发布), 再挑要下载的附件;
    两处都直接回车 = 最新发布 + 全部附件。给了 [key]--tag[/key] / [key]--asset[/key] 就是非交互模式。
    中断的下载会留下 [key]<文件>.part[/key], 重跑自动续传 ([key]--fresh[/key] 可忽略)。
    Release 可单独设加速源 ([key]gitx proxy release on gh-proxy[/key]), 不影响克隆等其它功能。
    """
    info = release.parse_target(target)
    prefix = config.active_proxy(proxy, no_proxy, release=True)
    out_dir = output or config.default_dest() or "."
    release.run(info, out_dir, prefix, tag=tag, assets=tuple(assets or ()),
                list_only=list_only, tags=tags, pick=pick, source=source, limit=limit,
                resume=not refresh and bool(config.load().get("resume", True)))


# ================================================================ 同步

@app.command(rich_help_panel=PANEL_SYNC)
def push(
    words: Annotated[Optional[list[str]], typer.Argument(metavar="[备注] [to <仓库地址>]",
                                                         help="提交备注; 可加 to <地址> 关联远程")] = None,
    message: Annotated[str, typer.Option("--message", "-m", help="提交信息")] = "",
    force: Annotated[bool, typer.Option("--force", "-f", help="强制推送")] = False,
    branch: Annotated[str, typer.Option("--branch", "-b", help="推送分支, 默认当前分支")] = "",
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
    no_proxy: Annotated[bool, typer.Option("--no-proxy", help="本次直连")] = False,
) -> None:
    """提交并推送 (推送走直连, 拉取走加速)."""
    free = list(words or [])
    to_url = ""
    if "to" in free:
        i = free.index("to")
        if i + 1 >= len(free):
            console.error("用法: gitx push [备注] to <仓库地址>")
        to_url = free[i + 1]
        free = free[:i] + free[i + 2:]
    sync.do_push(path=path, message=message or " ".join(free), force=force,
                 no_proxy=no_proxy, to_url=to_url, branch=branch)


@app.command(rich_help_panel=PANEL_SYNC)
def pull(
    path: Annotated[str, typer.Argument(metavar="路径", help="仓库路径")] = ".",
    rebase: Annotated[bool, typer.Option("--rebase", help="用变基而不是合并")] = False,
    no_proxy: Annotated[bool, typer.Option("--no-proxy", help="本次直连")] = False,
) -> None:
    """拉取远端更新 (走加速)."""
    sync.do_pull(path, rebase, no_proxy)


@app.command("sync", rich_help_panel=PANEL_SYNC)
def sync_cmd(
    words: Annotated[Optional[list[str]], typer.Argument(metavar="[备注]", help="提交备注")] = None,
    message: Annotated[str, typer.Option("--message", "-m", help="提交信息")] = "",
    merge: Annotated[bool, typer.Option("--merge", help="用合并而不是变基")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="强制推送")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
    no_proxy: Annotated[bool, typer.Option("--no-proxy", help="本次直连")] = False,
) -> None:
    """先拉取再推送, 一步完成日常同步 (默认变基)."""
    rebase = False if merge else bool(config.load().get("sync_rebase", True))
    sync.do_sync(path=path, message=message or " ".join(words or []), force=force,
                 no_proxy=no_proxy, rebase=rebase)


# ================================================================ 仓库

@app.command(rich_help_panel=PANEL_REPO,
             context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def init(
    ctx: typer.Context,
    args: Annotated[Optional[list[str]], typer.Argument(metavar="[目录] [git init 参数]",
                                                        help="目录与额外的 git init 参数")] = None,
    no_zh: Annotated[bool, typer.Option("--no-zh", help="不写入中文友好配置")] = False,
) -> None:
    """初始化仓库: 分支 main + 中文友好配置 (文件名不转义 / 日志 UTF-8)."""
    repo.init([*(args or []), *ctx.args], zh=not no_zh)


@app.command(rich_help_panel=PANEL_REPO)
def info(
    path: Annotated[str, typer.Argument(metavar="路径", help="仓库路径")] = ".",
) -> None:
    """仓库概览: 状态、与远端领先/落后、最近提交、加速状态."""
    repo.info(path)


@app.command(rich_help_panel=PANEL_REPO)
def undo(
    times: Annotated[int, typer.Argument(metavar="次数", help="撤销最近的 N 个提交")] = 1,
    soft: Annotated[bool, typer.Option("--soft", help="改动保留在暂存区 (默认)")] = False,
    mixed: Annotated[bool, typer.Option("--mixed", help="改动回到工作区")] = False,
    hard: Annotated[bool, typer.Option("--hard", help="连改动一起丢弃 (会确认)")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
    yes: Annotated[bool, typer.Option("--yes", "-y", help="跳过确认")] = False,
) -> None:
    """撤销最近 N 个提交 (默认 --soft, 提交仍在 reflog 中可恢复)."""
    mode = "hard" if hard else "mixed" if mixed else "soft"
    repo.undo(times, mode, path, yes)


@app.command("graph", rich_help_panel=PANEL_REPO)
def graph_cmd(
    limit: Annotated[int, typer.Option("--limit", "-n", help="显示多少条提交")] = 15,
    all_refs: Annotated[bool, typer.Option("--all", "-a", help="显示所有引用 (含其它分支/标签)")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """带图形的提交历史 (git log --graph 的上色版)."""
    repo.graph(limit, all_refs, path)


app.command("lg", hidden=True, rich_help_panel=PANEL_REPO,
            help="graph 的别名")(graph_cmd)


@app.command(rich_help_panel=PANEL_BRANCH)
def branches(
    path: Annotated[str, typer.Argument(metavar="路径", help="仓库路径")] = ".",
    include_remote: Annotated[bool, typer.Option("--all", "-a", help="含远端跟踪分支")] = False,
    limit: Annotated[int, typer.Option("--limit", "-n", help="最多显示多少个分支")] = 20,
) -> None:
    """分支列表: 上游 / 领先落后 / 最近提交 (等价 gitx branch)."""
    branch.list_branches(path, include_remote=include_remote, limit=limit)


@app.command(rich_help_panel=PANEL_REPO)
def tidy(
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
    prune: Annotated[bool, typer.Option("--prune", help="删除已合并的本地分支 (会确认)")] = False,
    gc_: Annotated[bool, typer.Option("--gc", help="运行 git gc 打包瘦身")] = False,
    aggressive: Annotated[bool, typer.Option("--aggressive", help="--gc 时更彻底 (更慢)")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="跳过确认")] = False,
) -> None:
    """仓库体检: 体积 / 已合并分支 / 打包瘦身."""
    repo.tidy(path, prune=prune, run_gc=gc_, aggressive=aggressive, yes=yes)


@app.command(rich_help_panel=PANEL_REPO)
def url(
    transport: Annotated[Optional[str], typer.Argument(
        metavar="[accel|https|ssh]", help="切换 origin 地址形态, 缺省则查看")] = None,
    remote: Annotated[str, typer.Option("--remote", "-r", help="远程名")] = "origin",
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """查看或切换远端地址: accel (拉取加速, 推送直连) / https / ssh."""
    repo.url(path, transport or "", remote)


# ================================================================ 分支 (gitx branch / switch / merge / rebase / fetch)

branch_app = typer.Typer(help="分支: 列表 / 新建 / 重命名 / 删除 / 上游", rich_markup_mode="rich",
                         invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})


@branch_app.callback()
def _branch_root(
    ctx: typer.Context,
    include_remote: Annotated[bool, typer.Option("--all", "-a", help="含远端跟踪分支")] = False,
    limit: Annotated[int, typer.Option("--limit", "-n", help="最多显示多少个分支")] = 20,
) -> None:
    # 不带子命令 = 列表
    if ctx.invoked_subcommand is None:
        branch.list_branches(".", include_remote=include_remote, limit=limit)


@branch_app.command("new")
def branch_new(
    name: Annotated[str, typer.Argument(metavar="分支名", help="新分支名")],
    start: Annotated[str, typer.Option("--from", "-b", help="起点 (分支 / 标签 / 提交), 默认 HEAD")] = "",
    switch: Annotated[bool, typer.Option("--switch", "-s", help="建完立即切换过去")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """新建分支."""
    branch.create(name, start=start, switch=switch, path=path)


@branch_app.command("rename")
def branch_rename(
    new: Annotated[str, typer.Argument(metavar="新名字", help="新分支名")],
    old: Annotated[str, typer.Option("--from", "-o", help="旧分支名, 缺省为当前分支")] = "",
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """重命名分支 (缺省改当前分支)."""
    branch.rename(old, new, path=path)


@branch_app.command("delete")
def branch_delete(
    names: Annotated[list[str], typer.Argument(metavar="分支...", help="要删除的分支名")],
    force: Annotated[bool, typer.Option("--force", "-D", help="强制删除未合并的分支")] = False,
    remote: Annotated[bool, typer.Option("--remote", "-r", help="删除 origin 上的远端分支")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="跳过确认")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """删除本地或远端分支."""
    branch.delete(list(names), force=force, remote=remote, yes=yes, path=path)


@branch_app.command("upstream")
def branch_upstream(
    name: Annotated[Optional[str], typer.Argument(metavar="[分支]", help="缺省为当前分支")] = None,
    set_to: Annotated[str, typer.Option("--set", help="设置上游, 如 origin/main")] = "",
    unset: Annotated[bool, typer.Option("--unset", help="取消上游关联")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """查看 / 设置 / 取消上游分支."""
    branch.upstream(name or "", set_to=set_to, unset=unset, path=path)


app.add_typer(branch_app, name="branch", rich_help_panel=PANEL_BRANCH)


@app.command(rich_help_panel=PANEL_BRANCH)
def switch(
    name: Annotated[str, typer.Argument(metavar="分支", help="分支名; - 表示上一个分支")],
    create: Annotated[bool, typer.Option("--create", "-c", help="新建并切换")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="有未提交改动也强制切换")] = False,
    detach: Annotated[bool, typer.Option("--detach", help="切到某次提交 (游离 HEAD)")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """切换分支 (新建: gitx switch -c <分支>)."""
    branch.do_switch(name, create=create, force=force, detach=detach, path=path)


@app.command(rich_help_panel=PANEL_BRANCH)
def merge(
    name: Annotated[Optional[str], typer.Argument(metavar="[分支]", help="要合并进来的分支")] = None,
    no_ff: Annotated[bool, typer.Option("--no-ff", help="总是生成合并提交")] = False,
    squash: Annotated[bool, typer.Option("--squash", help="只把改动放进暂存区, 不提交")] = False,
    abort: Annotated[bool, typer.Option("--abort", help="放弃正在进行的合并")] = False,
    continue_: Annotated[bool, typer.Option("--continue", help="冲突解决后完成合并")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """把某个分支合并进当前分支 (冲突时给出解决/放弃提示)."""
    branch.merge(name or "", no_ff=no_ff, squash=squash, abort=abort, continue_=continue_, path=path)


@app.command(rich_help_panel=PANEL_BRANCH)
def rebase(
    onto: Annotated[Optional[str], typer.Argument(metavar="[目标]", help="变基目标 (分支 / 标签)")] = None,
    interactive: Annotated[bool, typer.Option("--interactive", "-i", help="交互式变基 (可压缩/改写提交)")] = False,
    abort: Annotated[bool, typer.Option("--abort", help="放弃正在进行的变基")] = False,
    continue_: Annotated[bool, typer.Option("--continue", help="冲突解决后继续变基")] = False,
    skip: Annotated[bool, typer.Option("--skip", help="跳过当前这次提交")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """把当前分支变基到目标 (冲突时给出继续/跳过/放弃提示)."""
    branch.rebase(onto or "", interactive=interactive, abort=abort, continue_=continue_, skip=skip, path=path)


@app.command(rich_help_panel=PANEL_SYNC)
def fetch(
    prune: Annotated[bool, typer.Option("--prune", "-p", help="清理远端已删除的分支")] = False,
    all_remotes: Annotated[bool, typer.Option("--all", "-a", help="所有远程")] = False,
    tags: Annotated[bool, typer.Option("--tags", help="同时拉取标签")] = False,
    no_proxy: Annotated[bool, typer.Option("--no-proxy", help="本次直连")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """更新远端跟踪引用 (走加速), 让 gitx branch 的领先/落后更准."""
    branch.fetch(path, prune=prune, all_remotes=all_remotes, tags=tags, no_proxy=no_proxy)


# ================================================================ 暂存与标签 (gitx stash / tag)

stash_app = typer.Typer(help="暂存: 保存 / 查看 / 恢复 / 删除", rich_markup_mode="rich",
                        invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})


@stash_app.callback()
def _stash_root(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-n", help="最多显示多少条")] = 20,
) -> None:
    # 不带子命令 = 列表
    if ctx.invoked_subcommand is None:
        stash.list_stashes(".", limit=limit)


@stash_app.command("list")
def stash_list(
    limit: Annotated[int, typer.Option("--limit", "-n", help="最多显示多少条")] = 20,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """列出暂存内容."""
    stash.list_stashes(path, limit=limit)


@stash_app.command("save")
def stash_save(
    words: Annotated[Optional[list[str]], typer.Argument(metavar="[备注]", help="暂存备注")] = None,
    include_untracked: Annotated[bool, typer.Option("--include-untracked", "-u", help="连同未跟踪文件一起暂存")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """保存当前改动 (工作区恢复干净)."""
    stash.save(" ".join(words or []), include_untracked=include_untracked, path=path)


@stash_app.command("pop")
def stash_pop(
    index: Annotated[int, typer.Argument(metavar="序号", help="stash@{N} 的 N, 默认 0")] = 0,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """恢复并删除该条暂存."""
    stash.pop(index, path=path)


@stash_app.command("apply")
def stash_apply(
    index: Annotated[int, typer.Argument(metavar="序号", help="stash@{N} 的 N, 默认 0")] = 0,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """恢复但保留该条暂存."""
    stash.apply(index, path=path)


@stash_app.command("drop")
def stash_drop(
    index: Annotated[int, typer.Argument(metavar="序号", help="stash@{N} 的 N, 默认 0")] = 0,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="跳过确认")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """删除一条暂存."""
    stash.drop(index, yes=yes, path=path)


@stash_app.command("show")
def stash_show(
    index: Annotated[int, typer.Argument(metavar="序号", help="stash@{N} 的 N, 默认 0")] = 0,
    patch: Annotated[bool, typer.Option("--patch", "-p", help="显示完整 diff")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """查看某条暂存的改动 (默认只看统计)."""
    stash.show(index, patch=patch, path=path)


@stash_app.command("clear")
def stash_clear(
    yes: Annotated[bool, typer.Option("--yes", "-y", help="跳过确认")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """清空所有暂存."""
    stash.clear(yes=yes, path=path)


app.add_typer(stash_app, name="stash", rich_help_panel=PANEL_WIP)


tag_app = typer.Typer(help="标签: 列表 / 新建 / 删除 / 推送", rich_markup_mode="rich",
                      invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})


@tag_app.callback()
def _tag_root(
    ctx: typer.Context,
    pattern: Annotated[str, typer.Option("--pattern", "-p", help="只显示匹配的标签")] = "",
    limit: Annotated[int, typer.Option("--limit", "-n", help="最多显示多少个")] = 30,
) -> None:
    # 不带子命令 = 列表
    if ctx.invoked_subcommand is None:
        tag.list_tags(".", pattern=pattern, limit=limit)


@tag_app.command("list")
def tag_list(
    pattern: Annotated[str, typer.Option("--pattern", "-p", help="只显示匹配的标签")] = "",
    limit: Annotated[int, typer.Option("--limit", "-n", help="最多显示多少个")] = 30,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """列出标签."""
    tag.list_tags(path, pattern=pattern, limit=limit)


@tag_app.command("new")
def tag_new(
    name: Annotated[str, typer.Argument(metavar="标签名", help="如 v1.0.0")],
    words: Annotated[Optional[list[str]], typer.Argument(metavar="[说明]", help="标签说明")] = None,
    annotate: Annotated[bool, typer.Option("--annotate", "-a", help="强制附注标签 (无说明时)")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """新建标签 (带说明即为附注标签)."""
    tag.create(name, " ".join(words or []), annotated=annotate, path=path)


@tag_app.command("delete")
def tag_delete(
    names: Annotated[list[str], typer.Argument(metavar="标签...", help="要删除的标签")],
    remote: Annotated[bool, typer.Option("--remote", "-r", help="同时删除 origin 上的标签")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="跳过确认")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """删除标签."""
    tag.delete(list(names), remote=remote, yes=yes, path=path)


@tag_app.command("push")
def tag_push(
    names: Annotated[Optional[list[str]], typer.Argument(metavar="[标签...]", help="缺省推送全部标签")] = None,
    remote: Annotated[str, typer.Option("--remote", "-r", help="远程名")] = "origin",
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """推送标签到远端 (推送直连)."""
    tag.push(list(names or ()), remote=remote, path=path)


app.add_typer(tag_app, name="tag", rich_help_panel=PANEL_WIP)


# ================================================================ 提交与改动 (gitx commit / diff / discard / clean)

@app.command(rich_help_panel=PANEL_REPO)
def commit(
    message: Annotated[str, typer.Option("--message", "-m", help="提交信息")] = "",
    all_changes: Annotated[bool, typer.Option("--all", "-a", help="提交所有已跟踪文件的改动")] = False,
    amend: Annotated[bool, typer.Option("--amend", help="修订上一次提交")] = False,
    no_edit: Annotated[bool, typer.Option("--no-edit", help="修订时沿用原提交信息")] = False,
    allow_empty: Annotated[bool, typer.Option("--allow-empty", help="允许空提交")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """提交改动 (gitx commit -m "信息"; 修订: --amend)."""
    repo.commit(message, all_changes=all_changes, amend=amend, no_edit=no_edit,
                allow_empty=allow_empty, path=path)


@app.command(rich_help_panel=PANEL_REPO)
def diff(
    paths: Annotated[Optional[list[str]], typer.Argument(metavar="[路径...]", help="只看这些路径")] = None,
    staged: Annotated[bool, typer.Option("--staged", "-s", help="看暂存区与 HEAD 的差异")] = False,
    stat: Annotated[bool, typer.Option("--stat", help="只看统计")] = False,
    name_only: Annotated[bool, typer.Option("--name-only", help="只列文件名")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """看上色后的改动 diff (默认工作区; --staged 看暂存区)."""
    repo.diff(list(paths or ()), staged=staged, stat=stat, name_only=name_only, path=path)


@app.command(rich_help_panel=PANEL_REPO)
def discard(
    paths: Annotated[list[str], typer.Argument(metavar="路径...", help="要丢弃改动的文件 / 目录")],
    staged: Annotated[bool, typer.Option("--staged", "-s", help="只取消暂存, 保留文件改动")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="跳过确认")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """丢弃工作区改动 (git restore; 不可恢复, 会确认)."""
    repo.discard(list(paths), staged=staged, yes=yes, path=path)


@app.command(rich_help_panel=PANEL_REPO)
def clean(
    directories: Annotated[bool, typer.Option("--directories", "-d", help="连未跟踪的目录一起删")] = False,
    ignored: Annotated[bool, typer.Option("--ignored", "-x", help="连 .gitignore 忽略的文件一起删 (危险)")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="跳过确认")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """删除未跟踪的文件 (先预览再确认, 默认只删文件)."""
    repo.clean(directories=directories, ignored=ignored, yes=yes, path=path)


# ================================================================ 探索

@app.command(rich_help_panel=PANEL_HUB)
def search(
    keyword: Annotated[str, typer.Argument(metavar="关键词", help="搜索词, 如 'cli 工具'")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="显示多少个结果 (最多 50)")] = 10,
    sort: Annotated[str, typer.Option("--sort", help="排序: stars / forks / updated")] = "stars",
    language: Annotated[str, typer.Option("--language", "-L", help="限定语言, 如 python / go")] = "",
    download: Annotated[bool, typer.Option("--download", "-d", help="直接下载选中的仓库")] = False,
    dest: Annotated[Optional[str], typer.Option("--output", "-o", help="下载目标路径")] = None,
    depth: Annotated[Optional[int], typer.Option("--depth", help="克隆深度, 0 = 完整克隆")] = None,
    proxy: Annotated[Optional[str], typer.Option("--proxy", help="本次使用的加速源")] = None,
    no_proxy: Annotated[bool, typer.Option("--no-proxy", help="本次直连, 不走加速")] = False,
) -> None:
    """搜索 GitHub 仓库 (走 API, 默认加速), [option]-d[/option] 可直接下载."""
    if sort not in hub.SEARCH_SORTS:
        console.error(f"不支持的排序: {sort} (可选: {', '.join(hub.SEARCH_SORTS)})")
    prefix = config.active_proxy(proxy, no_proxy)
    items = hub.search(keyword, prefix, limit=limit, sort=sort, language=language)
    if not download or not items:
        return
    index = 0
    if len(items) > 1 and console.is_terminal():
        labels = [f"{repo.get('full_name')}  ★{repo.get('stargazers_count')}  "
                  f"{repo.get('description') or ''}"[:90] for repo in items]
        picked = console.select("要下载哪个?", labels, instruction="[↑↓] 选择  [输入] 筛选  [回车] 确认")
        if picked is None:
            console.warn("已取消下载")
            return
        index = picked
    repo_full = str(items[index].get("full_name") or "")
    _do_download(f"https://github.com/{repo_full}", dest, depth, "", proxy, no_proxy)


@app.command(rich_help_panel=PANEL_HUB)
def stat(
    target: Annotated[Optional[str], typer.Argument(
        metavar="[仓库|链接]", help="owner/repo 或 GitHub 链接, 缺省取当前仓库 origin")] = None,
    json_out: Annotated[bool, typer.Option("--json", help="输出 JSON (脚本友好), 不渲染表格")] = False,
    proxy: Annotated[Optional[str], typer.Option("--proxy", help="本次使用的加速源")] = None,
    no_proxy: Annotated[bool, typer.Option("--no-proxy", help="本次直连, 不走加速")] = False,
) -> None:
    """查看仓库信息: [num]star[/num] / fork / [num]topics[/num] / 语言 / 许可证 / 贡献者 / 最新发布.

    不给参数时读取当前仓库的 origin, 例如在仓库目录里直接 [key]gitx stat[/key]。
    数据来自 GitHub API (默认加速); 配置 [key]token[/key] 可把限额 60 提到 5000 次/小时。
    """
    prefix = config.active_proxy(proxy, no_proxy)
    hub.stat(target or "", prefix, json_out=json_out)


@app.command(rich_help_panel=PANEL_HUB)
def web(
    what: Annotated[Optional[str], typer.Argument(
        metavar="[页面]",
        help="issues / pulls / releases / actions / wiki / branch / commit, 缺省为首页")] = None,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
    no_open: Annotated[bool, typer.Option("--print", help="只打印地址, 不打开浏览器")] = False,
) -> None:
    """用浏览器打开当前仓库的 GitHub 页面 (issues / releases / commit ...)."""
    hub.web(path, what or "", browse=not no_open)


@app.command(rich_help_panel=PANEL_HUB)
def ignore(
    names: Annotated[Optional[list[str]], typer.Argument(
        metavar="[模板...]", help="如 python node macos")] = None,
    list_only: Annotated[bool, typer.Option("--list", "-l", help="列出可用模板")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="覆盖已有 .gitignore")] = False,
    output: Annotated[str, typer.Option("--output", "-o", help="写入目录")] = ".",
    proxy: Annotated[Optional[str], typer.Option("--proxy", help="本次使用的加速源")] = None,
    no_proxy: Annotated[bool, typer.Option("--no-proxy", help="本次直连, 不走加速")] = False,
) -> None:
    """从 github/gitignore 拉取 .gitignore 模板并写入 (默认追加)."""
    prefix = config.active_proxy(proxy, no_proxy)
    if list_only:
        hub.list_templates(" ".join(names or []), prefix)
        return
    hub.ignore(list(names or []), output, force=force, prefix=prefix)


# ================================================================ 加速管理

proxy_app = typer.Typer(help="加速管理: 拉取走加速, 推送直连", rich_markup_mode="rich",
                        invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})

# Release 专用加速: 与其它功能分开设置, 例如 Release 换镜像而克隆保持默认
release_proxy_app = typer.Typer(help="Release 专用加速 (与其它功能的加速分开设置)", rich_markup_mode="rich",
                                invoke_without_command=True,
                                context_settings={"help_option_names": ["-h", "--help"]})


@release_proxy_app.callback()
def _release_proxy_root(ctx: typer.Context) -> None:
    # 不带子命令 = 查看 Release 加速状态
    if ctx.invoked_subcommand is None:
        _release_proxy_status()


@release_proxy_app.command("status")
def release_proxy_status() -> None:
    """查看 Release 专用加速源 (与全局对比)."""
    _release_proxy_status()


@release_proxy_app.command("on")
def release_proxy_on(
    source: Annotated[str, typer.Argument(metavar="加速源", help="v6 / v4 / gh-proxy / https://...")] = "v6",
) -> None:
    """开启 Release 独立加速 (默认 v6), 其它功能照旧."""
    source = _checked_source("release_proxy", source)
    config.save({**config.load(), "release_proxy": source})
    console.done(f"Release 已独立加速: {source} ({accel.resolve(source)})")


@release_proxy_app.command("off")
def release_proxy_off() -> None:
    """Release 直连 (其它功能仍按全局设置走加速)."""
    config.save({**config.load(), "release_proxy": "off"})
    console.done("Release 已设为直连 (其它功能不受影响)")


@release_proxy_app.command("follow")
def release_proxy_follow() -> None:
    """恢复为跟随全局加速源 (默认)."""
    config.save({**config.load(), "release_proxy": ""})
    console.done("Release 已恢复为跟随全局加速源")


@release_proxy_app.command("set")
def release_proxy_set(
    source: Annotated[str, typer.Argument(metavar="加速源", help="v6 / v4 / gh-proxy / https://...")],
) -> None:
    """设置 Release 专用加速源."""
    source = _checked_source("release_proxy", source)
    config.save({**config.load(), "release_proxy": source})
    console.done(f"Release 加速源已设为: {source}")


proxy_app.add_typer(release_proxy_app, name="release")


@proxy_app.callback()
def _proxy_root(ctx: typer.Context) -> None:
    # 不带子命令 = 查看状态
    if ctx.invoked_subcommand is None:
        _proxy_status()


@proxy_app.command("status")
def proxy_status() -> None:
    """查看当前加速源与 git insteadOf 规则."""
    _proxy_status()


@proxy_app.command("on")
def proxy_on(
    source: Annotated[str, typer.Argument(metavar="加速源", help="v6 / v4 / gh-proxy / https://...")] = "v6",
) -> None:
    """开启加速 (默认 v6)."""
    cfg = config.load()
    accel.resolve(source)
    config.save({**cfg, "proxy": source})
    console.done(f"已开启加速: {source}")


@proxy_app.command("off")
def proxy_off() -> None:
    """关闭加速 (直连)."""
    config.save({**config.load(), "proxy": "off"})
    console.done("已关闭加速 (直连)")


@proxy_app.command("default")
def proxy_default() -> None:
    """恢复默认加速源 v6."""
    config.save({**config.load(), "proxy": "v6"})
    console.done(f"已恢复默认加速源: v6 ({accel.PROVIDERS['v6']})")


@proxy_app.command("set")
def proxy_set(
    source: Annotated[str, typer.Argument(metavar="加速源", help="v6 / v4 / gh-proxy / https://...")],
) -> None:
    """设置加速源."""
    cfg = config.load()
    accel.resolve(source)
    config.save({**cfg, "proxy": source})
    console.done(f"加速源已设为: {source}")


@proxy_app.command("auto")
def proxy_auto() -> None:
    """实测各加速源与直连的克隆速度, 选用最快的."""
    _proxy_auto()


@proxy_app.command("test")
def proxy_test() -> None:
    """测试当前加速源的连通性 (git 克隆 / raw / API)."""
    _proxy_test()


@proxy_app.command("http")
def proxy_http(
    address: Annotated[str, typer.Argument(metavar="地址", help="http://127.0.0.1:7890 或 off")] = "",
    local: Annotated[bool, typer.Option("--local", help="只对当前仓库生效")] = False,
) -> None:
    """设置 git 的 HTTP(S) 代理 (本地代理软件或公司网络)."""
    _proxy_http(address, local)


@proxy_app.command("install")
def proxy_install(
    local: Annotated[bool, typer.Option("--local", help="只对当前仓库生效")] = False,
) -> None:
    """写入 git insteadOf 规则, 让普通 git 命令也走加速."""
    _proxy_install(local)


@proxy_app.command("uninstall")
def proxy_uninstall(
    local: Annotated[bool, typer.Option("--local", help="只清理当前仓库的规则")] = False,
) -> None:
    """移除 insteadOf 规则."""
    _proxy_uninstall(local)


app.add_typer(proxy_app, name="proxy", rich_help_panel=PANEL_PROXY)


def _release_source_label(cfg: dict) -> tuple[str, str | None, bool]:
    """Release 生效加速源: (显示名, 前缀, 是否独立设置)."""
    raw = config.release_source(cfg)
    env = os.environ.get("GITX_RELEASE_PROXY", "")
    global_name = str(cfg.get("proxy", "v6"))
    if raw:
        chosen, independent = raw, True
    elif env:
        chosen, independent = f"{env} (环境变量 GITX_RELEASE_PROXY)", True
    else:
        chosen, independent = f"跟随全局 ({global_name})", False
    try:
        prefix = accel.resolve(raw or env or global_name)
    except ValueError:
        prefix = None
    return chosen, prefix, independent


def _release_proxy_status() -> None:
    cfg = config.load()
    name, prefix, independent = _release_source_label(cfg)
    table = console.table("项目", "值", title="Release 加速状态")
    table.add_row("Release 加速源",
                  console.txt(f"{name} ({prefix})" if prefix else f"{name} (直连, 未加速)"))
    table.add_row("全局加速源", console.txt(f"{cfg.get('proxy', 'v6')} ({accel.resolve(cfg.get('proxy', 'v6'))})"
                                            if _resolvable(str(cfg.get("proxy", "v6")))
                                            else f"{cfg.get('proxy', 'v6')} (直连, 未加速)"))
    table.add_row("生效范围", console.txt("Release 附件与发布列表 (API)"))
    table.add_row("配置文件", console.txt(str(config.config_path())))
    console.print(table)
    if independent:
        console.info("取消独立设置: gitx proxy release follow (改为跟随全局)")
    else:
        console.info("单独设置: gitx proxy release on gh-proxy | off 直连 | follow 跟随全局")


def _resolvable(name: str) -> str | None:
    try:
        return accel.resolve(name)
    except ValueError:
        return None


def _checked_source(key: str, source: str) -> str:
    """校验加速源后返回; 非法值给中文提示并退出 (而不是抛栈)."""
    try:
        return str(config.normalize(key, source))
    except ValueError as exc:
        console.error(str(exc))


def _proxy_status() -> None:
    cfg = config.load()
    name = str(cfg.get("proxy", "v6"))
    try:
        prefix = accel.resolve(name)
    except ValueError:
        prefix = None
    installed = accel.installed_prefix()
    rel_name, rel_prefix, rel_independent = _release_source_label(cfg)
    table = console.table("项目", "值", title="加速状态")
    table.add_row("加速源", console.txt(f"{name} ({prefix})" if prefix else f"{name} (直连, 未加速)"))
    table.add_row("Release 加速源",
                  console.txt((f"{rel_name} ({rel_prefix})" if rel_prefix else f"{rel_name} (直连, 未加速)")
                              + ("" if rel_independent else "  —  未单独设置")))
    table.add_row("insteadOf", console.txt(f"{installed} (普通 git 命令也走加速)" if installed
                                           else "未安装 (只影响 gitx 自身)"))
    table.add_row("配置文件", console.txt(str(config.config_path())))
    console.print(table)
    console.info("开启/切换: gitx proxy on | auto 测速 | off 直连 | install 让 git 也走加速")
    console.info("Release 单独设置: gitx proxy release on <源> | off 直连 | follow 跟随全局")


def _proxy_auto() -> None:
    """逐个测速并选用最快的加速源 (含直连)."""
    cfg = config.load()
    console.step("正在测速 (git 克隆端点, 越小越快)...")
    probed: list[tuple[str, str | None, float, bool]] = []
    for name, prefix in list(accel.PROVIDERS.items()) + [("off", None)]:
        ms, ok = accel.probe(prefix)
        probed.append((name, prefix, ms, ok))
    reachable = [(name, ms) for name, _prefix, ms, ok in probed if ok]
    if not reachable:
        console.error("所有加速源都不可达, 请检查网络 (gitx proxy test)")
    best = min(reachable, key=lambda item: item[1])[0]
    table = console.table("加速源", "地址", "耗时", "结果", title="加速源测速")
    for name, prefix, ms, ok in probed:
        mark = "[ok]最快[/ok]" if ok and name == best else ("[dim]不可达[/dim]" if not ok else "")
        table.add_row(console.txt(name), console.txt(prefix or "直连"),
                      console.txt(f"{ms:.0f} ms" if ok else "-"), mark)
    console.print(table)
    config.save({**cfg, "proxy": best})
    label = f" ({accel.PROVIDERS[best]})" if best in accel.PROVIDERS else " 直连"
    console.done(f"已选择最快: {best}{label}")


def _proxy_test() -> None:
    cfg = config.load()
    _probe_source(str(cfg.get("proxy", "v6")))
    rel = config.release_source(cfg) or os.environ.get("GITX_RELEASE_PROXY", "")
    if rel and rel != str(cfg.get("proxy", "v6")):
        _probe_source(rel, title="Release 连通性")


def _probe_source(name: str, *, title: str = "连通性") -> None:
    """实测一个加速源的 git / raw / api 三个端点."""
    try:
        prefix = accel.resolve(name)
    except ValueError as exc:
        console.error(str(exc))
    if not prefix:
        console.info(f"加速源 {name}: 直连模式, 跳过测试")
        return
    console.step(f"测试加速源: {name} ({prefix})")
    import urllib.request  # noqa: PLC0415 仅网络命令需要, 避免拖慢其它命令

    table = console.table("端点", "结果", title=title)
    rc, _ = gitcmd.capture(
        ["git", "ls-remote", "--symref", f"{prefix}/https://github.com/octocat/Hello-World.git", "HEAD"]
    )
    table.add_row("git 克隆", console.txt("可达" if rc == 0 else "失败"))
    for label, path in (
        ("raw", prefix + "/https://raw.githubusercontent.com/octocat/Hello-World/master/README"),
        ("api", prefix + "/https://api.github.com/repos/octocat/Hello-World"),
    ):
        try:
            with urllib.request.urlopen(path, timeout=10) as r:
                table.add_row(label, console.txt(f"HTTP {r.status}"))
        except Exception as exc:  # noqa: BLE001
            table.add_row(label, console.txt(f"失败 ({exc})"))
    console.print(table)


def _proxy_http(address: str, local: bool) -> None:
    scope = "--local" if local else "--global"
    for key in ("http.proxy", "https.proxy"):
        rc, cur = gitcmd.capture(["git", "config", scope, "--get", key])
        if address and address not in ("off", "none", "取消"):
            if not address.startswith(("http://", "https://", "socks5://", "socks5h://")):
                console.error(f"代理地址应以 http:// 或 socks5:// 开头: {address}")
            subprocess.run(["git", "config", scope, key, address], check=False, capture_output=True)
        elif address:
            subprocess.run(["git", "config", scope, "--unset-all", key], check=False, capture_output=True)
        elif rc == 0 and cur:
            console.info(f"git {scope} {key} = {cur}")
    if address:
        if address in ("off", "none", "取消"):
            console.done(f"已取消 git {scope} HTTP(S) 代理")
        else:
            console.done(f"已设置 git {scope} 代理: {address}")
    elif not any(gitcmd.capture(["git", "config", scope, "--get", k])[1]
                 for k in ("http.proxy", "https.proxy")):
        console.info(f"git {scope} 代理: 未设置")
    console.info("用法: gitx proxy http http://127.0.0.1:7890 | off | --local")


def _proxy_install(local: bool) -> None:
    cfg = config.load()
    scope = "--local" if local else "--global"
    prefix = accel.resolve(cfg.get("proxy", "v6"))
    if not prefix:
        console.error("当前是直连模式, 先: gitx proxy on")
    accel.install_rewrite(prefix, scope)
    config.save({**cfg, "installed_prefix": prefix, "installed_scope": scope})
    console.done(f"已写入 git {scope} insteadOf 规则: 普通 git 命令也走加速 {prefix}")


def _proxy_uninstall(local: bool) -> None:
    cfg = config.load()
    scope = "--local" if local else str(cfg.get("installed_scope", "--global"))
    prefix = str(cfg.get("installed_prefix", "")) or accel.resolve(cfg.get("proxy", "v6")) or ""
    if prefix:
        accel.uninstall_rewrite(prefix, scope)
    cfg.pop("installed_prefix", None)
    cfg.pop("installed_scope", None)
    config.save(cfg)
    console.done("已移除 insteadOf 规则")


# ================================================================ 配置

config_app = typer.Typer(help="持久化配置 (~/.config/gitx/config.toml, 带注释可手改)", rich_markup_mode="rich",
                         invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})


@config_app.callback()
def _config_root(ctx: typer.Context) -> None:
    # 不带子命令 = 列出配置
    if ctx.invoked_subcommand is None:
        _config_list()


@config_app.command("list")
def config_list() -> None:
    """查看全部配置."""
    _config_list()


@config_app.command("get")
def config_get(key: Annotated[str, typer.Argument(metavar="键", help=_CFG_KEYS)]) -> None:
    """查看单个配置项."""
    value = config.load().get(key, "")
    console.info(f"{key} = {_mask(key, value)}")


@config_app.command("set")
def config_set(
    key: Annotated[str, typer.Argument(metavar="键", help=_CFG_KEYS)],
    value: Annotated[str, typer.Argument(metavar="值")],
) -> None:
    """修改配置项 (bool 接受 true/false/yes/no; 加速源会校验合法性)."""
    try:
        value = config.normalize(key, value)
    except ValueError as exc:
        console.error(str(exc))
    config.save({**config.load(), key: value})
    console.done(f"{key} = {_mask(key, value)}")


@config_app.command("reset")
def config_reset() -> None:
    """恢复默认配置."""
    config.save(dict(config.DEFAULTS))
    console.done("配置已重置为默认")



@config_app.command("path")
def config_path_cmd() -> None:
    """打印配置文件路径."""
    console.info(str(config.config_path()))


@config_app.command("edit")
def config_edit() -> None:
    """用 $VISUAL / $EDITOR 打开配置文件 (首次运行会生成带注释的模板)."""
    import shlex  # noqa: PLC0415

    config.ensure_file()
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
    subprocess.run([*shlex.split(editor), str(config.config_path())])

@config_app.command("zh")
def config_zh(
    global_: Annotated[bool, typer.Option("--global", help="写入全局配置 (默认只写当前仓库)")] = False,
) -> None:
    """一键中文友好配置 (文件名不转义, 日志 UTF-8)."""
    scope = "--global" if global_ else "--local"
    if scope == "--local" and not gitcmd.is_repo("."):
        console.error("当前目录不是 git 仓库\n  全局设置请用: gitx config zh --global")
    changed = gitcmd.apply_zh_config(scope, ".")
    console.done(f"已写入 {scope} 中文友好配置: " + (", ".join(changed) if changed else "已是最新"))


app.add_typer(config_app, name="config", rich_help_panel=PANEL_CONF)


def _mask(key: str, value: object) -> str:
    """token 之类敏感值只显示尾巴."""
    text = str(value)
    if key == "token" and text:
        return f"{'*' * 8}{text[-4:]}" if len(text) > 4 else "*" * len(text)
    return text


def _config_list() -> None:
    config.ensure_file()  # 首次运行就生成带注释的 TOML, 让用户有东西可看
    table = console.table("键", "值", title="gitx 配置")
    for key, value in config.load().items():
        table.add_row(console.txt(key), console.txt(_mask(key, value)))
    console.print(table)
    console.info(f"配置文件: {config.config_path()}   (直接编辑: gitx config edit)")


@app.command(rich_help_panel=PANEL_CONF)
def doctor() -> None:
    """环境自检: git / gh / 仓库 / 加速源 / 编码."""
    cfg = config.load()
    table = console.table("项目", "状态", title=f"gitx {__version__} 环境自检")
    table.add_row("配置文件", console.txt(config.config_path()))
    _, gitver = gitcmd.capture(["git", "--version"])
    table.add_row("git", console.txt(gitver or "未找到"))
    import shutil  # noqa: PLC0415

    gh = shutil.which("gh")
    state = ("已登录" if gitcmd.capture(["gh", "auth", "status"])[0] == 0 else "未登录") if gh else "未安装"
    table.add_row("gh", console.txt(state))
    token = str(cfg.get("token") or "")
    table.add_row("API token", console.txt(
        f"已配置 ({_mask('token', token)})" if token
        else ("复用 gh 的 token" if state == "已登录" else "未配置 (匿名限额 60 次/小时)")))
    table.add_row("缓存", console.txt(str(config.cache_dir())))
    if gitcmd.is_repo():
        origin = gitcmd.remote_url("origin")
        table.add_row("仓库", console.txt(f"是 | 分支 {gitcmd.current_branch() or '(无提交)'}"
                                          + (f" | origin {origin}" if origin else "")))
    else:
        table.add_row("仓库", console.txt("否 (当前目录不是 git 仓库)"))
    quotepath = gitcmd.capture(["git", "config", "--global", "--get", "core.quotepath"])[1]
    if quotepath in ("false", "0", "off"):
        table.add_row("编码", console.txt("core.quotepath=false (中文文件名正常显示)"))
    else:
        table.add_row("编码", console.txt("中文文件名会转义显示, 建议: gitx config zh --global"))
    console.print(table)
    _proxy_test()


# ================================================================ 下载分发

def _clear_dest(dest: str) -> None:
    if os.path.lexists(dest):
        if not console.ask(f"目标已存在: {dest}, 要覆盖吗?", default=False):
            console.error("已取消")
        import shutil  # noqa: PLC0415  懒加载, 少一次标准库导入

        if os.path.isdir(dest) and not os.path.islink(dest):
            shutil.rmtree(dest)
        else:
            os.remove(dest)


def _do_download(url: str, dest: Optional[str], depth: Optional[int], branch: str,
                 proxy: Optional[str], no_proxy: bool, *, list_only: bool = False,
                 assets: Optional[list[str]] = None, source: bool = False,
                 limit: int = release.DEFAULT_LIMIT, archive: bool = False,
                 extract: bool = False, submodules: bool = False, fresh: bool = False) -> None:
    try:
        info = github.parse_url(url)
    except ValueError as exc:
        console.error(f"{exc}\n提示: 其它 git 子命令可直接透传, 如 gitx status")
    cfg = config.load()
    base = config.default_dest()  # 配置里的默认下载目录 (展开 ~), 留空 = 当前目录
    prefix = config.active_proxy(proxy, no_proxy, cfg=cfg, release=info["mode"] in ("release", "asset"))
    if info["mode"] in ("release", "asset"):
        release.run(info, dest or base or ".", prefix, assets=tuple(assets or ()),
                    list_only=list_only, source=source, limit=limit,
                    resume=not fresh and bool(cfg.get("resume", True)))
        return
    if archive and info["mode"] != "repo":
        console.error("--archive 只对仓库链接有效 (文件夹/单个文件请直接下载)")
    item_name = os.path.basename(info["path"]) if info["path"] else info["repo"]
    target = dest or (os.path.join(base, item_name) if base else item_name)
    _clear_dest(target)
    if depth is None:
        depth = int(cfg.get("depth", 1) or 1)
    download.run(info, target, prefix, depth, branch,
                 archive=archive, extract=extract, submodules=submodules,
                 resume=not fresh and bool(cfg.get("resume", True)))


def main(argv: list[str] | None = None) -> None:
    """typer 应用入口 (git 透传 / --version 的快速通道见 dispatch.handle)."""
    console.apply_color(str(config.load().get("color", "auto")))
    app(list(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    main()