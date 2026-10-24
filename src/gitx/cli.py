"""gitx 命令行入口: 用 Typer + Rich 构建的分组式 CLI.

命令分组:
  下载 (download / clone / release)   同步 (push / pull / sync / fetch)
  仓库 (init / info / commit / diff / discard / clean / undo / graph / tidy / url)
  分支 (branch / switch / merge / rebase)  暂存 (stash)  标签 (tag)
  探索 (search / stat / web / ignore)      加速 (proxy ...)  配置 (config ... / doctor)
  发行版管理 (publish: 创建 / 上传附件 / 编辑 / 删除, 交给已登录的 gh)
  工作流 (actions: 运行列表 / 详情 / 日志 / 重跑 / 产物下载, 交给 gh)
  账号 (auth: 登录 / 退出 / 切换 / 权限 / 令牌, 交给 gh)
  我的仓库 (repos: 挑 / 搜一个仓库 -> 进编辑界面改设置 / 克隆 / 归档 / 删除, 交给 gh)
非 gitx 自己的词一律透传 git (gitx status / gitx log --oneline), 这条快速通道
由 dispatch.py 在导入 typer 之前处理, 因此几乎瞬时完成。
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Annotated

import typer
from rich.markup import escape

from . import (__version__, accel, actions, auth, branch, cache, config, console, daemon, download, ghrepo,
               gitcmd, github, hub, pr, publish, release, remote, repo, stash, submodule, sync, tag,
               upgrade, workspace)

PANEL_DL = "下载 (默认加速)"
PANEL_PUB = "发行版管理 (创建 / 上传 / 编辑)"
PANEL_SYNC = "同步"
PANEL_REPO = "仓库 (提交 / 改动 / 历史)"
PANEL_BRANCH = "分支 (切换 / 合并 / 变基)"
PANEL_WIP = "暂存与标签"
PANEL_HUB = "探索 (搜索 / 网页 / 模板)"
PANEL_COLLAB = "协作 (PR / 子模组)"
PANEL_ACT = "工作流 (Actions 运行)"
PANEL_GHR = "我的仓库 (挑一个 -> 编辑)"
PANEL_AUTH = "账号 (登录态)"
PANEL_PROXY = "加速管理"
PANEL_CONF = "配置与自检"

_CFG_KEYS = "/".join(config.DEFAULTS)

_HELP = f"""[key]gitx[/key] -- 给中国人用的 GitHub 加速与同步工具 [dim]v{__version__}[/dim]

拉取 (克隆 / 文件 / Release 附件 / API) 默认走加速镜像 [num]{accel.PROVIDERS['v6']}[/num], 推送直连 GitHub。
直接给一个 GitHub 链接或 [key]owner/repo[/key] 即可下载: [key]gitx cli/cli[/key]
其它词一律透传 git, 且不加载 typer, 因此几乎瞬时: [key]gitx status[/key] / [key]gitx log --oneline[/key]"""

_EPILOG = """[key]示例[/key]
  gitx https://github.com/owner/repo                下载仓库 -> ./repo
  gitx cli/cli                                      链接可省成 owner/repo, 同上
  gitx https://github.com/owner/repo/tree/main/src  只下载某个文件夹 (部分克隆, 实测快 8 倍)
  gitx https://github.com/owner/repo -x             下载并解压源码包 (不用 git, 只取一个流)
  gitx ws cli/cli                                   克隆到工作区 ~/gitx-workspaces/cli
  gitx ws cli/cli ~/code/cli                        克隆到指定目录并登记
  gitx ws sync                                      工作区里的仓库逐个拉取 (有改动只 fetch)
  gitx ws each git status -s                        每个仓库都跑一遍同一条命令
  gitx release cli/cli --list                       看最新发布的附件清单
  gitx release cli/cli --asset '*linux_amd64*'      只下匹配的附件
  gitx publish create v1.0.5 dist/* -p -F 说明.md    创建发行版并上传附件 (交给 gh)
  gitx actions                                      看最近的 Actions 运行 (可按分支 / 状态过滤)
  gitx actions view --log-failed                     只看失败步骤的日志
  gitx actions download -D 产物目录                   下载运行产物 (附件)
  gitx auth                                         看登录了哪些账号 (当前账号标出来)
  gitx auth token --save                            复用 gh 的令牌, 把 API 限额提到 5000 次/小时
  gitx ws use work ~/code/work                      切换默认工作区, 根目录随你放 (任意路径)
  gitx ws move ~/code                               把当前工作区整个搬过去 (仓库一起搬)
  gitx ws -s oss list                               临时看另一个工作区
  gitx ws -h                                        工作区全部子命令 (list / add / rm / spaces / drop)
  gitx repos                                       上下键挑我的仓库 -> 进编辑界面 (改描述 / 话题 / 可见性)
  gitx repos -n 5                                  只取最近 5 个仓库来挑 (超出的不上屏)
  gitx repos -q dotfile                            按关键词搜仓库 (搜得到全部, 不受 -n 限制)
  gitx repos --fresh                               不吃缓存, 重新向 GitHub 取一次
  gitx search "cli 工具" --language go -d           搜仓库并下载第 1 个
  gitx search                                      交互式搜: 问关键词 -> 挑一个 -> 下载 / 概览 / 网页
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
  gitx remote add upstream https://github.com/o/r   加远程 (拉取加速, 推送直连)
  gitx submodule update                             拉取子模组 (同样走加速)
  gitx pr list                                      看当前仓库的 Pull Request
  gitx upgrade                                      自更新到最新版本 (走加速)
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
    ("gitx <链接|owner/repo>", "下载仓库 / 文件夹 / 文件 / 源码包 (默认加速)"),
    ("gitx ws owner/repo", "克隆到工作区并统一管理 (status / sync / each / cd)"),
    ("gitx ws use work ~/code", "切换默认工作区, 根目录随你放 (多工作区: spaces / move)"),
    ("gitx release owner/repo", "交互式挑选并下载 Release 附件"),
    ("gitx publish", "发行版管理: 列表 / 创建 / 上传附件 / 编辑 / 删除"),
    ("gitx sync", "先拉取再推送, 一步完成日常同步 (默认变基)"),
    ("gitx push / gitx pull", "提交并推送 / 拉取远端更新"),
    ("gitx info", "仓库概览: 状态 / 领先落后 / 最近提交"),
    ("gitx branch", "分支表; 切换 switch / 合并 merge / 变基 rebase"),
    ("gitx stash / gitx tag", "暂存与标签的保存 / 查看 / 恢复"),
    ("gitx commit -m / gitx diff", "提交改动 / 查看上色 diff"),
    ("gitx search [关键词]", "搜仓库; 不写关键词 = 交互式挑, 可下载 / 看概览"),
    ("gitx stat owner/repo", "仓库信息: star / 语言 / 贡献者 / 最新发布"),
    ("gitx proxy auto", "实测测速, 自动选用最快的加速源"),
    ("gitx remote", "查看/添加远程 (拉取加速, 推送直连)"),
    ("gitx pr / gitx submodule", "PR 列表与详情 / 子模组一条龙 (走加速)"),
    ("gitx actions", "Actions 运行: 列表 / 日志 / 重跑 / 产物下载 (交给 gh)"),
    ("gitx auth", "登录状态 / 切换账号 / 取令牌 (--save 提升 API 限额)"),
    ("gitx repos", "挑/搜我的仓库 (-q 关键词) -> 进编辑界面改设置 (结果走缓存, --fresh 回源)"),
    ("gitx daemon", "守护进程: 低配机提速 (config set daemon true 打开)"),
    ("gitx cache", "缓存: 查看 / 明细 / 清理 ~/.cache/gitx"),
    ("gitx upgrade", "自更新到最新版本 (下载走加速)"),
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
    console.quicklist(_WELCOME_TIPS, title="快速上手")
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
    targets: Annotated[list[str] | None, typer.Argument(
        metavar="URL|路径...",
        help="一个或多个 GitHub 链接 (也可写 owner/repo); 只给一个链接时, 第二个参数可当保存路径")] = None,
    branch: Annotated[str, typer.Option("--branch", "-b", help="指定分支")] = "",
    depth: Annotated[int | None, typer.Option("--depth", "-d", help="克隆深度, 0 = 完整克隆")] = None,
    archive: Annotated[bool, typer.Option("--archive", "-x", "--tarball",
                                          help="下载源码包 tar.gz, 不用 git (不要历史时最快)")] = False,
    extract: Annotated[bool, typer.Option("--extract", "-X", help="下载源码包并直接解压 (隐含 -x)")] = False,
    submodules: Annotated[bool, typer.Option("--submodules", help="连同子模组一起拉取 (同样走加速)")] = False,
    fresh: Annotated[bool, typer.Option("--fresh", help="忽略 .part 断点, 从零下载")] = False,
    list_only: Annotated[bool, typer.Option("--list", "-l", help="仅列出附件 (发布页链接)")] = False,
    limit: Annotated[int, typer.Option(
        "--limit", "-n", help="发布列表条数 (发布页链接挑选发布用, 最多 100)")] = release.DEFAULT_LIMIT,
    assets: Annotated[list[str] | None, typer.Option("--asset", "-a", help="仅下载匹配的附件, 可重复")] = None,
    source: Annotated[bool, typer.Option("--source", help="额外下载源码包 (发布页链接)")] = False,
    output: Annotated[str | None, typer.Option(
        "--output", "-o", help="保存路径; 多个链接或指向已存在目录 (以 / 结尾) 时作为目录")] = None,
    links_file: Annotated[str, typer.Option("--file", "-f", help="从文本文件读取链接 (每行一个, # 注释; - 表示标准输入)")] = "",
    proxy: Annotated[str | None, typer.Option("--proxy", help="本次使用的加速源: v6 / v4 / gh-proxy / https://...")] = None,
    no_proxy: Annotated[bool, typer.Option("--no-proxy", help="本次直连, 不走加速")] = False,
) -> None:
    """下载仓库 / 文件夹 / 单个文件 / 源码包 / Release 附件, [info]默认走加速[/info].

    要历史用 [key]git clone[/key] 路线 (浅克隆), 只要文件树用 [key]-x[/key] 源码包路线,
    只要某个目录用 [key]tree[/key] 链接 (部分克隆 + 稀疏检出), 单个文件用 [key]blob[/key] 链接。

    可以一次给多个链接 (逐个下载, 单个失败不影响其余的), 也可以 [key]-f[/key] 从文本文件读;
    多个链接时 [key]-o[/key] 视为保存目录, 每个仓库各建一个子目录。
    """
    urls = list(targets or [])
    if links_file:
        urls += _read_links(links_file)
    if not urls:
        console.error("请给出至少一个 GitHub 链接 / owner/repo (或 gitx download <链接...> -f 链接文件)")
    from .dispatch import is_download  # 仅此处用来区分"链接"和"保存路径"

    dest = output
    if dest is None and len(urls) >= 2 and not is_download(urls[-1]):
        dest = urls.pop()
    if len(urls) == 1 and dest and (os.path.isdir(dest) or dest.endswith(("/", os.sep))):
        dest = _batch_target(urls[0], dest)  # 目标是目录 / 以斜杠结尾 -> 存进目录, 不覆盖它
    _do_download_many(urls, dest, depth, branch, proxy, no_proxy,
                      list_only=list_only, assets=assets, source=source, limit=limit,
                      archive=archive or extract, extract=extract, submodules=submodules, fresh=fresh)


app.command("clone", hidden=True, rich_help_panel=PANEL_DL,
            help="download 的别名")(download_cmd)


@app.command("release", rich_help_panel=PANEL_DL)
def release_cmd(
    target: Annotated[str, typer.Argument(metavar="仓库|链接", help="owner/repo 或发布页 / 附件链接")],
    tag: Annotated[str, typer.Option("--tag", "-t", help="Release 标签, 默认最新")] = "",
    tags: Annotated[bool, typer.Option("--tags", help="列出最近的 Release, 不下载")] = False,
    limit: Annotated[int, typer.Option(
        "--limit", "-n", help="发布列表条数 (挑选发布与 --tags 用, 最多 100)")] = release.DEFAULT_LIMIT,
    assets: Annotated[list[str] | None, typer.Option("--asset", "-a", help="只下载匹配的附件 (支持通配, 可重复)")] = None,
    pick: Annotated[bool, typer.Option("--pick", "-i", "--choose", help="交互式挑选发布与附件 (含预发布)")] = False,
    list_only: Annotated[bool, typer.Option("--list", "-l", help="只列出附件清单, 不下载")] = False,
    source: Annotated[bool, typer.Option("--source", help="额外下载源码包 (tarball)")] = False,
    output: Annotated[str, typer.Option("--output", "-o", help="保存目录")] = ".",
    refresh: Annotated[bool, typer.Option("--fresh", help="忽略 .part 断点, 从零下载")] = False,
    proxy: Annotated[str | None, typer.Option("--proxy", help="本次使用的加速源: v6 / v4 / gh-proxy / https://...")] = None,
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
    words: Annotated[list[str] | None, typer.Argument(metavar="[备注] [to <仓库地址>]",
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
    words: Annotated[list[str] | None, typer.Argument(metavar="[备注]", help="提交备注")] = None,
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
    args: Annotated[list[str] | None, typer.Argument(metavar="[目录] [git init 参数]",
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
    # --soft 是默认模式 (由下面的三选一决定), 参数只为与 --mixed / --hard 对称
    soft: Annotated[bool, typer.Option("--soft", help="改动保留在暂存区 (默认)")] = False,  # noqa: ARG001
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
    transport: Annotated[str | None, typer.Argument(
        metavar="[accel|https|ssh]", help="切换远程地址形态, 缺省则查看")] = None,
    remote: Annotated[str, typer.Option("--remote", "-r", help="远程名 (缺省用配置 remote)")] = "",
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
    name: Annotated[str | None, typer.Argument(metavar="[分支]", help="缺省为当前分支")] = None,
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
    name: Annotated[str | None, typer.Argument(metavar="[分支]", help="要合并进来的分支")] = None,
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
    onto: Annotated[str | None, typer.Argument(metavar="[目标]", help="变基目标 (分支 / 标签)")] = None,
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
    words: Annotated[list[str] | None, typer.Argument(metavar="[备注]", help="暂存备注")] = None,
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
    words: Annotated[list[str] | None, typer.Argument(metavar="[说明]", help="标签说明")] = None,
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
    names: Annotated[list[str] | None, typer.Argument(metavar="[标签...]", help="缺省推送全部标签")] = None,
    remote: Annotated[str, typer.Option("--remote", "-r", help="远程名 (缺省用配置 remote)")] = "",
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """推送标签到远端 (推送直连)."""
    tag.push(list(names or ()), remote=remote or config.default_remote(), path=path)


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
    paths: Annotated[list[str] | None, typer.Argument(metavar="[路径...]", help="只看这些路径")] = None,
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
    keyword: Annotated[str | None, typer.Argument(
        metavar="[关键词]", help="搜索词, 如 'cli 工具'; 留空 = 交互式搜索")] = None,
    limit: Annotated[int | None, typer.Option(
        "--limit", "-n", help="显示多少个结果 (最多 50; 缺省用配置 search_limit)")] = None,
    sort: Annotated[str, typer.Option("--sort", help="排序: stars / forks / updated")] = "stars",
    language: Annotated[str, typer.Option("--language", "-L", help="限定语言, 如 python / go")] = "",
    interactive: Annotated[bool, typer.Option(
        "--interactive", "-i", help="交互式: 结果可上下键挑, 再 下载 / 概览 / 打开网页")] = False,
    download: Annotated[bool, typer.Option("--download", "-d", help="直接下载选中的仓库")] = False,
    dest: Annotated[str | None, typer.Option("--output", "-o", help="下载目标路径")] = None,
    depth: Annotated[int | None, typer.Option("--depth", help="克隆深度, 0 = 完整克隆")] = None,
    proxy: Annotated[str | None, typer.Option("--proxy", help="本次使用的加速源")] = None,
    no_proxy: Annotated[bool, typer.Option("--no-proxy", help="本次直连, 不走加速")] = False,
) -> None:
    """搜索 GitHub 仓库 (走 API, [info]默认加速[/info]); 不给关键词就是交互式搜索.

    交互式搜索: 先问搜索词, 结果列出来后用 [key]↑↓[/key] 挑一个 (直接打字即筛选),
    再选 [key]下载 / 看概览 / 打开网页[/key]; 挑完能接着挑下一个, 想换词就选"换个关键词再搜"。
    [key]-d[/key] 是"挑一个直接下载"的快捷方式, 适合只想下载的场合。
    """
    if sort not in hub.SEARCH_SORTS:
        console.error(f"不支持的排序: {sort} (可选: {', '.join(hub.SEARCH_SORTS)})")
    limit = limit or config.default_limit("search_limit", 10)
    prefix = config.active_proxy(proxy, no_proxy)
    if keyword is None or interactive:
        _search_shell(keyword or "", prefix, limit=limit, sort=sort, language=language,
                      dest=dest, depth=depth, proxy=proxy, no_proxy=no_proxy)
        return
    items = hub.search(keyword, prefix, limit=limit, sort=sort, language=language)
    if not download or not items:
        return
    index = 0
    if len(items) > 1 and console.is_terminal():
        picked = console.select("要下载哪个?", _result_labels(items),
                                instruction="[↑↓] 选择  [输入] 筛选  [回车] 确认")
        if picked is None:
            console.warn("已取消下载")
            return
        index = picked
    repo_full = str(items[index].get("full_name") or "")
    _do_download(f"https://github.com/{repo_full}", dest, depth, "", proxy, no_proxy)


# 交互式搜索结果里的动作: (代号, 说明) —— 单选列表, 顺序即重要性
_SEARCH_ACTIONS: tuple[tuple[str, str], ...] = (
    ("download", "下载到本地 (走加速)"),
    ("stat", "看仓库概览 (star / 语言 / 贡献者 / 最新发布)"),
    ("web", "打开仓库网页"),
    ("again", "换个关键词再搜"),
    ("quit", "退出搜索"),
)


def _result_labels(items: list[dict]) -> list[str]:
    """搜索结果的一行摘要 (挑选器与 -d 共用): 仓库 / star / 简介."""
    return [f"{repo.get('full_name')}  ★{repo.get('stargazers_count')}  "
            f"{repo.get('description') or ''}"[:90] for repo in items]


def _search_shell(keyword: str, prefix: str | None, *, limit: int, sort: str, language: str,
                  dest: str | None, depth: int | None, proxy: str | None,
                  no_proxy: bool) -> None:
    """交互式搜索: 问关键词 -> 结果表 -> 挑一个 -> 下载 / 概览 / 网页, 可以一直搜下去.

    一个回合只问一次关键词, 之后在结果列表里反复挑; 因此"搜了再搜"不必重敲命令行。
    """
    if not console.is_terminal():
        console.error("交互式搜索需要交互终端\n提示: 直接给关键词, 如 gitx search \"cli 工具\"")
    keyword = keyword.strip()
    while True:
        answer = console.text("搜索关键词" + (f" (当前: {language})" if language else ""),
                              default=keyword, instruction="[回车] 用这个词  [Ctrl+C] 退出")
        if answer is None:
            console.warn("已退出交互式搜索")
            return
        keyword = answer.strip()
        if not keyword:
            console.warn("关键词不能为空")
            continue
        total, items = hub.query(keyword, prefix, limit=limit, sort=sort, language=language)
        hub.render_results(total, items, keyword)
        if not items:
            continue
        if not _search_round(items, prefix, dest=dest, depth=depth, proxy=proxy,
                             no_proxy=no_proxy):
            console.warn("已退出交互式搜索")
            return


def _search_round(items: list[dict], prefix: str | None, *, dest: str | None, depth: int | None,
                  proxy: str | None, no_proxy: bool) -> bool:
    """在结果里挑一个并执行动作; 返回 False = 退出搜索, True = 换个关键词再搜."""
    labels = _result_labels(items)
    while True:
        index = console.select("挑一个仓库", labels,
                               instruction="[↑↓] 选择  [输入] 筛选  [回车] 确认")
        if index is None:
            return False
        repo = items[index]
        full = str(repo.get("full_name") or "")
        url = str(repo.get("html_url") or f"https://github.com/{full}")
        choice = console.select(f"{full} 要做什么?", [label for _, label in _SEARCH_ACTIONS],
                                instruction="[↑↓] 选择  [回车] 确认")
        if choice is None:
            return False
        action = _SEARCH_ACTIONS[choice][0]
        if action == "quit":
            return False
        if action == "again":
            return True
        if action == "download":
            _do_download(url, dest, depth, "", proxy, no_proxy)
        elif action == "stat":
            hub.stat(full, prefix)
        else:  # web: 打开浏览器 (webbrowser 较重, 只在真要打开时才导入)
            import webbrowser

            console.print(console.link(url, url))
            if not webbrowser.open(url):
                console.warn("未能自动打开浏览器, 请手动访问上面的链接")


@app.command(rich_help_panel=PANEL_HUB)
def stat(
    target: Annotated[str | None, typer.Argument(
        metavar="[仓库|链接]", help="owner/repo 或 GitHub 链接, 缺省取当前仓库 origin")] = None,
    json_out: Annotated[bool, typer.Option("--json", help="输出 JSON (脚本友好), 不渲染表格")] = False,
    proxy: Annotated[str | None, typer.Option("--proxy", help="本次使用的加速源")] = None,
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
    what: Annotated[str | None, typer.Argument(
        metavar="[页面]",
        help="issues / pulls / releases / actions / wiki / branch / commit, 缺省为首页")] = None,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
    no_open: Annotated[bool, typer.Option("--print", help="只打印地址, 不打开浏览器")] = False,
) -> None:
    """用浏览器打开当前仓库的 GitHub 页面 (issues / releases / commit ...)."""
    hub.web(path, what or "", browse=not no_open)


@app.command(rich_help_panel=PANEL_HUB)
def ignore(
    names: Annotated[list[str] | None, typer.Argument(
        metavar="[模板...]", help="如 python node macos")] = None,
    list_only: Annotated[bool, typer.Option("--list", "-l", help="列出可用模板")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="覆盖已有 .gitignore")] = False,
    output: Annotated[str, typer.Option("--output", "-o", help="写入目录")] = ".",
    proxy: Annotated[str | None, typer.Option("--proxy", help="本次使用的加速源")] = None,
    no_proxy: Annotated[bool, typer.Option("--no-proxy", help="本次直连, 不走加速")] = False,
) -> None:
    """从 github/gitignore 拉取 .gitignore 模板并写入 (默认追加)."""
    prefix = config.active_proxy(proxy, no_proxy)
    if list_only:
        hub.list_templates(" ".join(names or []), prefix)
        return
    hub.ignore(list(names or []), output, force=force, prefix=prefix)


# ================================================================ 协作 (远程 / 子模组 / PR)

remote_app = typer.Typer(help="远程管理: 查看 / 添加 / 删除 / 重命名 / 改地址", rich_markup_mode="rich",
                         invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})


@remote_app.callback()
def _remote_root(ctx: typer.Context) -> None:
    # 不带子命令 = 列出远程 (gitx remote -v 等未知参数仍透传给 git, 见 dispatch.py)
    if ctx.invoked_subcommand is None:
        remote.list_remotes()


@remote_app.command("list")
def remote_list(
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """列出全部远程 (拉取 / 推送地址)."""
    remote.list_remotes(path)


@remote_app.command("add")
def remote_add(
    name: Annotated[str, typer.Argument(metavar="远程名", help="如 origin / upstream")],
    url: Annotated[str, typer.Argument(metavar="地址", help="GitHub 链接或任意 git 地址")],
    push_url: Annotated[str, typer.Option("--push", help="单独指定推送地址 (默认自动: 直连或 SSH)")] = "",
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """添加远程 (GitHub 地址自动: 拉取走加速, 推送直连)."""
    remote.add(name, url, push_url=push_url, path=path)


@remote_app.command("remove")
def remote_remove(
    name: Annotated[str, typer.Argument(metavar="远程名", help="要删除的远程")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="跳过确认")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """删除远程."""
    remote.remove(name, yes=yes, path=path)


@remote_app.command("rename")
def remote_rename(
    old: Annotated[str, typer.Argument(metavar="旧名", help="原远程名")],
    new: Annotated[str, typer.Argument(metavar="新名", help="新远程名")],
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """重命名远程."""
    remote.rename(old, new, path=path)


@remote_app.command("set-url")
def remote_set_url(
    name: Annotated[str, typer.Argument(metavar="远程名", help="要改的远程")],
    url: Annotated[str, typer.Argument(metavar="地址", help="新的拉取地址")],
    push_only: Annotated[bool, typer.Option("--push", help="只改推送地址, 不动拉取地址")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """修改远程地址 (GitHub 地址默认连推送地址一起改好)."""
    remote.set_url(name, url, push_only=push_only, path=path)


@remote_app.command("show")
def remote_show(
    name: Annotated[str, typer.Argument(metavar="远程名", help="要查看的远程")],
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """查看单个远程的地址与形态."""
    remote.show(name, path)


app.add_typer(remote_app, name="remote", rich_help_panel=PANEL_REPO)


submodule_app = typer.Typer(help="子模组: 添加 / 更新 / 查看 / 同步 / 删除 (拉取走加速)",
                            rich_markup_mode="rich", invoke_without_command=True,
                            context_settings={"help_option_names": ["-h", "--help"]})


@submodule_app.callback()
def _submodule_root(ctx: typer.Context) -> None:
    # 不带子命令 = 列出子模组
    if ctx.invoked_subcommand is None:
        submodule.list_submodules()


@submodule_app.command("list")
def submodule_list(
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """列出子模组状态."""
    submodule.list_submodules(path)


@submodule_app.command("status")
def submodule_status(
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """列出子模组状态 (同 list)."""
    submodule.list_submodules(path)


@submodule_app.command("add")
def submodule_add(
    url: Annotated[str, typer.Argument(metavar="地址", help="子模组仓库链接")],
    sub_path: Annotated[str | None, typer.Argument(metavar="[路径]", help="检出到哪个目录")] = None,
    name: Annotated[str, typer.Option("--name", help="子模组名 (默认取路径)")] = "",
    branch: Annotated[str, typer.Option("--branch", "-b", help="跟踪的分支")] = "",
    depth: Annotated[int, typer.Option("--depth", help="浅克隆深度, 0 = 完整")] = 0,
    force: Annotated[bool, typer.Option("--force", "-f", help="目标已存在也强制添加")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """添加子模组 (拉取同样走加速)."""
    submodule.add(url, sub_path or "", name=name, branch=branch, depth=depth, force=force, path=path)


@submodule_app.command("update")
def submodule_update(
    paths: Annotated[list[str] | None, typer.Argument(metavar="[路径...]", help="只更新指定子模组")] = None,
    init: Annotated[bool, typer.Option("--init/--no-init", help="未初始化的子模组也一并初始化")] = True,
    remote: Annotated[bool, typer.Option("--remote", help="跟踪子模组的远端最新提交, 而不是 .gitmodules 里锁定的提交")] = False,
    depth: Annotated[int, typer.Option("--depth", help="浅克隆深度, 0 = 完整")] = 0,
    jobs: Annotated[int, typer.Option("--jobs", "-j", help="并行拉取的子模组数, 0 = git 默认")] = 0,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """拉取子模组内容 (默认 --init --recursive, 走加速)."""
    submodule.update(tuple(paths or ()), init=init, remote=remote, depth=depth, jobs=jobs, path=path)


@submodule_app.command("sync")
def submodule_sync(
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """把子模组远端地址同步成 .gitmodules 里的配置."""
    submodule.sync(path)


@submodule_app.command("remove")
def submodule_remove(
    sub_path: Annotated[str, typer.Argument(metavar="路径", help="子模组路径")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="跳过确认")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """删除子模组 (含 .gitmodules 条目与本地缓存)."""
    submodule.remove(sub_path, yes=yes, path=path)


app.add_typer(submodule_app, name="submodule", rich_help_panel=PANEL_COLLAB)


pr_app = typer.Typer(help="Pull Request: 列表 / 详情 / 创建", rich_markup_mode="rich",
                     invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})


@pr_app.callback()
def _pr_root(ctx: typer.Context) -> None:
    # 不带子命令 = 列出当前仓库的开放 PR
    if ctx.invoked_subcommand is None:
        pr.list_pulls("", state="open", limit=20, prefix=config.active_proxy())


@pr_app.command("list")
def pr_list(
    target: Annotated[str, typer.Argument(metavar="[仓库]", help="owner/repo 或链接, 缺省取当前仓库 origin")] = "",
    state: Annotated[str, typer.Option("--state", help="open / closed / all")] = "open",
    limit: Annotated[int, typer.Option("--limit", "-n", help="显示多少条 (最多 100)")] = 20,
    proxy: Annotated[str | None, typer.Option("--proxy", help="本次使用的加速源")] = None,
    no_proxy: Annotated[bool, typer.Option("--no-proxy", help="本次直连, 不走加速")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """列出 Pull Request (走 API, 默认加速)."""
    if state not in pr.STATES:
        console.error(f"不支持的 state: {state} (可选: {', '.join(pr.STATES)})")
    pr.list_pulls(target, state=state, limit=limit, prefix=config.active_proxy(proxy, no_proxy), path=path)


@pr_app.command("view")
def pr_view(
    number: Annotated[int, typer.Argument(metavar="编号", help="PR 编号")],
    target: Annotated[str, typer.Argument(metavar="[仓库]", help="owner/repo 或链接, 缺省取当前仓库")] = "",
    web: Annotated[bool, typer.Option("--web", help="同时用浏览器打开")] = False,
    proxy: Annotated[str | None, typer.Option("--proxy", help="本次使用的加速源")] = None,
    no_proxy: Annotated[bool, typer.Option("--no-proxy", help="本次直连, 不走加速")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """查看单个 PR 的标题 / 状态 / 正文."""
    pr.view(number, target, prefix=config.active_proxy(proxy, no_proxy), browse=web, path=path)


@pr_app.command("create")
def pr_create(
    title: Annotated[str, typer.Option("--title", "-t", help="标题, 缺省时由 gh 交互询问")] = "",
    body: Annotated[str, typer.Option("--body", "-b", help="正文")] = "",
    base: Annotated[str, typer.Option("--base", help="目标分支, 如 main")] = "",
    head: Annotated[str, typer.Option("--head", help="来源分支, 缺省为当前分支")] = "",
    fill: Annotated[bool, typer.Option("--fill", help="用提交信息自动填标题与正文")] = False,
    draft: Annotated[bool, typer.Option("--draft", help="创建为草稿 PR")] = False,
    path: Annotated[str, typer.Option("--path", "-C", help="仓库路径")] = ".",
) -> None:
    """用已登录的 gh 创建 Pull Request."""
    pr.create(title, body, base=base, head=head, fill=fill, draft=draft, path=path)


app.add_typer(pr_app, name="pr", rich_help_panel=PANEL_COLLAB)


# ================================================================ 工作流 (Actions)

actions_app = typer.Typer(help="工作流 (Actions): 运行列表 / 日志 / 重跑 / 产物下载 (交给已登录的 gh)",
                          rich_markup_mode="rich", invoke_without_command=True,
                          context_settings={"help_option_names": ["-h", "--help"]})

_RUN_HELP = "运行号; 留空 = 由 gh 弹出选择器让人挑 (需要终端)"
_ACT_REPO_HELP = "目标仓库 (owner/repo 或链接), 默认当前仓库"
_STATUS_HELP = "gh 的状态名: queued / in_progress / success / failure / cancelled / timed_out ..."


@actions_app.callback()
def _actions_root(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-n", help="列表条数 (gh 默认 20)")] = 20,
    workflow: Annotated[str, typer.Option("--workflow", "-w", help="只看某个工作流 (文件名或名称)")] = "",
    branch: Annotated[str, typer.Option("--branch", "-b", help="只看某个分支")] = "",
    status: Annotated[str, typer.Option("--status", "-s", help=_STATUS_HELP)] = "",
    event: Annotated[str, typer.Option("--event", "-e",
                                       help="按触发事件过滤: push / pull_request / workflow_dispatch ...")] = "",
    user: Annotated[str, typer.Option("--user", "-u", help="按触发人过滤")] = "",
    repo: Annotated[str, typer.Option("--repo", "-R", help=_ACT_REPO_HELP)] = "",
) -> None:
    # 不带子命令 = 列出最近的运行
    if ctx.invoked_subcommand is None:
        actions.list_runs(repo, workflow=workflow, branch=branch, status=status,
                          event=event, user=user, limit=limit)


@actions_app.command("list")
def actions_list(
    limit: Annotated[int, typer.Option("--limit", "-n", help="列表条数 (gh 默认 20)")] = 20,
    workflow: Annotated[str, typer.Option("--workflow", "-w", help="只看某个工作流 (文件名或名称)")] = "",
    branch: Annotated[str, typer.Option("--branch", "-b", help="只看某个分支")] = "",
    status: Annotated[str, typer.Option("--status", "-s", help=_STATUS_HELP)] = "",
    event: Annotated[str, typer.Option("--event", "-e", help="按触发事件过滤")] = "",
    user: Annotated[str, typer.Option("--user", "-u", help="按触发人过滤")] = "",
    all_workflows: Annotated[bool, typer.Option("--all", "-a", help="连已停用的工作流一起算")] = False,
    repo: Annotated[str, typer.Option("--repo", "-R", help=_ACT_REPO_HELP)] = "",
) -> None:
    """列出运行: 运行号 / 状态 / 工作流 / 标题 / 分支 / 触发时间."""
    actions.list_runs(repo, workflow=workflow, branch=branch, status=status, event=event,
                      user=user, limit=limit, all_workflows=all_workflows)


@actions_app.command("view")
def actions_view(
    run: Annotated[str, typer.Argument(metavar="[运行号]", help=_RUN_HELP)] = "",
    job: Annotated[str, typer.Option("--job", "-j", help="只看某个作业 (作业编号或名字)")] = "",
    attempt: Annotated[int, typer.Option("--attempt", "-a", help="看第几次尝试 (默认最后一次)")] = 0,
    log: Annotated[bool, typer.Option("--log", help="打印完整日志 (交给 gh)")] = False,
    log_failed: Annotated[bool, typer.Option("--log-failed", help="只打印失败步骤的日志")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="连每个步骤一起列出来")] = False,
    web: Annotated[bool, typer.Option("--web", "-w", help="在浏览器中打开这次运行")] = False,
    exit_status: Annotated[bool, typer.Option("--exit-status",
                                              help="运行没成功则以非 0 退出 (脚本里判断用)")] = False,
    repo: Annotated[str, typer.Option("--repo", "-R", help=_ACT_REPO_HELP)] = "",
) -> None:
    """看运行详情: 标题 / 分支 / 耗时 + 作业表 (--verbose 连步骤).

    例: [key]gitx actions view --log-failed[/key] 直接看失败的步骤,
    [key]gitx actions view 1234 --job 测试 --log[/key] 只看某个作业的日志。
    """
    actions.view(run, repo, job=job, attempt=attempt, log=log, log_failed=log_failed,
                 verbose=verbose, web=web, exit_status=exit_status)


@actions_app.command("watch")
def actions_watch(
    run: Annotated[str, typer.Argument(metavar="[运行号]", help=_RUN_HELP)] = "",
    interval: Annotated[int, typer.Option("--interval", "-i", help="刷新间隔秒数 (gh 默认 3)")] = 0,
    compact: Annotated[bool, typer.Option("--compact", help="只显示相关 / 失败的步骤")] = False,
    exit_status: Annotated[bool, typer.Option("--exit-status", help="跑失败则以非 0 退出")] = False,
    repo: Annotated[str, typer.Option("--repo", "-R", help=_ACT_REPO_HELP)] = "",
) -> None:
    """实时盯一个运行到结束 (会阻塞到跑完)."""
    actions.watch(run, repo, interval=interval, compact=compact, exit_status=exit_status)


@actions_app.command("rerun")
def actions_rerun(
    run: Annotated[str, typer.Argument(metavar="[运行号]", help=_RUN_HELP)] = "",
    failed: Annotated[bool, typer.Option("--failed", help="只重跑失败的作业 (含它们的依赖)")] = False,
    job: Annotated[str, typer.Option("--job", "-j", help="只重跑这个作业")] = "",
    debug: Annotated[bool, typer.Option("--debug", help="带调试日志重跑")] = False,
    repo: Annotated[str, typer.Option("--repo", "-R", help=_ACT_REPO_HELP)] = "",
) -> None:
    """重跑运行 ([key]--failed[/key] 只重跑失败的作业)."""
    actions.rerun(run, repo, failed=failed, job=job, debug=debug)


@actions_app.command("cancel")
def actions_cancel(
    run: Annotated[str, typer.Argument(metavar="[运行号]", help=_RUN_HELP)] = "",
    force: Annotated[bool, typer.Option("--force", help="强制取消 (用于卡住不动的运行)")] = False,
    repo: Annotated[str, typer.Option("--repo", "-R", help=_ACT_REPO_HELP)] = "",
) -> None:
    """取消运行."""
    actions.cancel(run, repo, force=force)


@actions_app.command("download")
def actions_download(
    run: Annotated[str, typer.Argument(metavar="[运行号]", help=_RUN_HELP)] = "",
    dest: Annotated[str, typer.Option("--dir", "-D", help="下载到哪个目录")] = ".",
    name: Annotated[list[str] | None, typer.Option("--name", "-N", help="只下这些产物 (可重复)")] = None,
    pattern: Annotated[list[str] | None, typer.Option("--pattern", "-p", help="按通配匹配产物 (可重复)")] = None,
    repo: Annotated[str, typer.Option("--repo", "-R", help=_ACT_REPO_HELP)] = "",
) -> None:
    """下载运行产物 (每个产物一个子目录)."""
    actions.download(run, repo, dest=dest, names=list(name or []), patterns=list(pattern or []))


@actions_app.command("workflows")
def actions_workflows(
    limit: Annotated[int, typer.Option("--limit", "-n", help="最多列出多少个 (gh 默认 50)")] = 50,
    all_workflows: Annotated[bool, typer.Option("--all", "-a", help="连已停用的也列出来")] = False,
    repo: Annotated[str, typer.Option("--repo", "-R", help=_ACT_REPO_HELP)] = "",
) -> None:
    """列出工作流: 名称 / 状态 / 路径 / 编号."""
    actions.workflows(repo, limit=limit, all_workflows=all_workflows)


@actions_app.command("dispatch")
def actions_dispatch(
    workflow: Annotated[str, typer.Argument(metavar="工作流", help="工作流文件名 (如 build.yml) 或名称")],
    ref: Annotated[str, typer.Option("--ref", "-r", help="在哪个分支 / 标签上跑, 默认默认分支")] = "",
    field: Annotated[list[str] | None, typer.Option("--field", "-F",
                                                    help="参数 键=值, 值支持 @文件 读文件内容 (可重复)")] = None,
    raw_field: Annotated[list[str] | None, typer.Option("--raw-field", "-f",
                                                        help="参数 键=值, 原样当字符串传 (可重复)")] = None,
    json_input: Annotated[bool, typer.Option("--json", help="从标准输入读整份 JSON 参数")] = False,
    repo: Annotated[str, typer.Option("--repo", "-R", help=_ACT_REPO_HELP)] = "",
) -> None:
    """手动触发工作流 (工作流里要有 [key]workflow_dispatch[/key] 事件).

    例: [key]gitx actions dispatch build.yml -F version=1.0.6[/key]
    """
    actions.dispatch(workflow, repo, ref=ref, fields=list(field or []),
                     raw_fields=list(raw_field or []), json_input=json_input)


app.add_typer(actions_app, name="actions", rich_help_panel=PANEL_ACT)


# ================================================================ 发行版管理 (创建 / 上传 / 编辑 / 删除)

publish_app = typer.Typer(help="发行版管理: 创建 / 上传附件 / 编辑 / 删除 (交给已登录的 gh)",
                          rich_markup_mode="rich", invoke_without_command=True,
                          context_settings={"help_option_names": ["-h", "--help"]})

_REPO_HELP = "目标仓库 (owner/repo 或链接), 默认当前仓库"
_LIMIT_HELP = "列表条数 (gh 默认 30)"


@publish_app.callback()
def _publish_root(
    ctx: typer.Context,
    limit: Annotated[int, typer.Option("--limit", "-n", help=_LIMIT_HELP)] = 30,
    drafts: Annotated[bool, typer.Option("--drafts/--no-drafts", help="列表是否含草稿")] = True,
    prereleases: Annotated[bool, typer.Option("--prereleases/--no-prereleases", help="列表是否含预发布")] = True,
    repo: Annotated[str, typer.Option("--repo", "-R", help=_REPO_HELP)] = "",
) -> None:
    # 不带子命令 = 列出发行版 (含草稿与预发布)
    if ctx.invoked_subcommand is None:
        publish.list_releases(repo, limit=limit, drafts=drafts, prereleases=prereleases)


@publish_app.command("list")
def publish_list(
    limit: Annotated[int, typer.Option("--limit", "-n", help=_LIMIT_HELP)] = 30,
    drafts: Annotated[bool, typer.Option("--drafts/--no-drafts", help="是否含草稿")] = True,
    prereleases: Annotated[bool, typer.Option("--prereleases/--no-prereleases", help="是否含预发布")] = True,
    repo: Annotated[str, typer.Option("--repo", "-R", help=_REPO_HELP)] = "",
) -> None:
    """列出发行版: 标签 / 名称 / 状态 / 发布时间 (含草稿与预发布)."""
    publish.list_releases(repo, limit=limit, drafts=drafts, prereleases=prereleases)


@publish_app.command("view")
def publish_view(
    tag: Annotated[str, typer.Argument(metavar="标签", help="发行版标签; 留空 = 最新")] = "",
    repo: Annotated[str, typer.Option("--repo", "-R", help=_REPO_HELP)] = "",
    web: Annotated[bool, typer.Option("--web", "-w", help="在浏览器中打开发行版页面")] = False,
) -> None:
    """查看发行版: 状态 / 时间 / 说明首行 / 附件清单."""
    publish.view(tag, repo, browse=web)


@publish_app.command("create")
def publish_create(
    tag: Annotated[str, typer.Argument(metavar="标签", help="发行版标签, 如 v1.0.5-pre2")],
    files: Annotated[list[str] | None, typer.Argument(
        metavar="附件...", help="要上传的附件 (支持通配; 也可加 #显示名)")] = None,
    repo: Annotated[str, typer.Option("--repo", "-R", help=_REPO_HELP)] = "",
    title: Annotated[str, typer.Option("--title", "-T", help="发行版标题")] = "",
    notes: Annotated[str, typer.Option("--notes", "-n", help="说明 (Markdown 文本)")] = "",
    notes_file: Annotated[str, typer.Option("--notes-file", "-F", help="从文件读说明 (- 表示标准输入)")] = "",
    prerelease: Annotated[bool, typer.Option("--prerelease", "-p", help="标记为预发布")] = False,
    draft: Annotated[bool, typer.Option("--draft", "-d", help="先建为草稿, 不直接发布")] = False,
    latest: Annotated[bool | None, typer.Option("--latest/--no-latest", help="是否设为最新 (默认 GitHub 自动判定)")] = None,
    commitish: Annotated[str, typer.Option("--target", help="标签不存在时用它自动创建 (分支 / 提交)")] = "",
    generate_notes: Annotated[bool, typer.Option("--generate-notes", help="交给 GitHub 自动生成说明")] = False,
    verify_tag: Annotated[bool, typer.Option("--verify-tag", help="标签不存在就报错 (不自动创建)")] = False,
) -> None:
    """创建发行版并上传附件 (交给已登录的 gh).

    附件一般给构建产物: [key]gitx publish create v1.0.5-pre2 dist/*.tar.gz dist/*.whl[/key];
    说明用 [key]--notes-file[/key] 从文件读 ([key]-[/key] = 标准输入, 便于配合发布模板),
    预发布加 [key]--prerelease[/key], 只想先看看加 [key]--draft[/key]。
    """
    publish.create(tag, list(files or []), target=repo, title=title, notes=notes,
                   notes_file=notes_file, prerelease=prerelease, draft=draft, latest=latest,
                   commitish=commitish, generate_notes=generate_notes, verify_tag=verify_tag)


@publish_app.command("upload")
def publish_upload(
    tag: Annotated[str, typer.Argument(metavar="标签", help="发行版标签")],
    files: Annotated[list[str] | None, typer.Argument(metavar="附件...", help="要上传的附件")] = None,
    repo: Annotated[str, typer.Option("--repo", "-R", help=_REPO_HELP)] = "",
    clobber: Annotated[bool, typer.Option("--clobber", help="同名附件先删除再上传")] = False,
) -> None:
    """给已有发行版补传附件."""
    publish.upload(tag, list(files or []), target=repo, clobber=clobber)


@publish_app.command("edit")
def publish_edit(
    tag: Annotated[str, typer.Argument(metavar="标签", help="发行版标签")],
    repo: Annotated[str, typer.Option("--repo", "-R", help=_REPO_HELP)] = "",
    new_tag: Annotated[str, typer.Option("--tag", help="把标签改成新名字")] = "",
    title: Annotated[str, typer.Option("--title", "-T", help="新标题")] = "",
    notes: Annotated[str, typer.Option("--notes", "-n", help="新说明 (Markdown 文本)")] = "",
    notes_file: Annotated[str, typer.Option("--notes-file", "-F", help="从文件读新说明 (- 表示标准输入)")] = "",
    prerelease: Annotated[bool | None, typer.Option("--prerelease/--no-prerelease",
                                                       help="预发布开关")] = None,
    draft: Annotated[bool | None, typer.Option("--draft/--no-draft",
                                                  help="草稿开关 (--no-draft 即发布)")] = None,
    latest: Annotated[bool | None, typer.Option("--latest/--no-latest",
                                                   help="是否标记为最新")] = None,
) -> None:
    """修改发行版: 标题 / 说明 / 预发布 / 草稿 / 最新.

    例: [key]gitx publish edit v1.0.5-pre2 --no-draft[/key] 把草稿正式发布,
    [key]gitx publish edit v1.0.5-pre2 --no-prerelease --latest[/key] 转为正式版并设为最新。
    """
    publish.edit(tag, new_tag=new_tag, target=repo, title=title, notes=notes, notes_file=notes_file,
                 prerelease=prerelease, draft=draft, latest=latest)


@publish_app.command("delete")
def publish_delete(
    tag: Annotated[str, typer.Argument(metavar="标签", help="发行版标签")],
    repo: Annotated[str, typer.Option("--repo", "-R", help=_REPO_HELP)] = "",
    cleanup_tag: Annotated[bool, typer.Option("--cleanup-tag", help="连 git 标签一起删除")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="跳过确认")] = False,
) -> None:
    """删除发行版 (会确认; [key]--cleanup-tag[/key] 连标签一起删)."""
    publish.delete(tag, target=repo, cleanup_tag=cleanup_tag, yes=yes)


app.add_typer(publish_app, name="publish", rich_help_panel=PANEL_PUB)


# ================================================================ 我的仓库 (挑一个 -> 编辑界面)

repos_app = typer.Typer(help="我的仓库: 挑一个 -> 编辑设置 / 克隆 / 复刻 / 归档 / 删除 (交给已登录的 gh)",
                        rich_markup_mode="rich", invoke_without_command=True,
                        context_settings={"help_option_names": ["-h", "--help"]})

_REPO_ARG = "仓库 (owner/repo 或链接); 留空则上下键挑一个"
# 挑选器参数: callback 填一次, 子命令共用 (所以 `gitx repos -n 5 view` 的挑选器只看前 5 个)
_PICK: dict[str, object] = {}


@repos_app.callback()
def _repos_root(
    ctx: typer.Context,
    limit: Annotated[int | None, typer.Option(
        "--limit", "-n",
        help="一次取几个仓库来挑 (缺省用配置 repos_limit; 只想看前几个给小数字)")] = None,
    owner: Annotated[str, typer.Option("--owner", "-o", help="看谁的仓库 (默认当前登录账号)")] = "",
    visibility: Annotated[str, typer.Option("--visibility",
                                            help="按可见性过滤: public / private / internal")] = "",
    language: Annotated[str, typer.Option("--language", "-l", help="按主要语言过滤")] = "",
    topic: Annotated[str, typer.Option("--topic", "-t", help="按话题过滤")] = "",
    source: Annotated[bool, typer.Option("--source", help="只看原创 (非复刻) 仓库")] = False,
    forks: Annotated[bool, typer.Option("--fork", help="只看复刻仓库")] = False,
    archived: Annotated[bool, typer.Option("--archived", help="只看已归档仓库")] = False,
    no_archived: Annotated[bool, typer.Option("--no-archived", help="排除已归档仓库")] = False,
    search: Annotated[str, typer.Option(
        "--search", "-q", help="按关键词搜 (搜得到全部仓库, 不受 -n 限制)")] = "",
    fresh: Annotated[bool, typer.Option(
        "--fresh", help="不吃本地缓存, 重新向 GitHub 取一次")] = False,
) -> None:
    limit = limit or config.default_limit("repos_limit", 30)
    # 过滤项写在子命令前面 (`gitx repos -o cli list`) 时, 要靠这里把它们带进子命令
    _PICK.update(owner=owner, limit=limit, visibility=visibility, language=language, topic=topic,
                 source=source, forks=forks, archived=archived, no_archived=no_archived,
                 keyword=search, fresh=fresh)
    if ctx.invoked_subcommand is None:
        ghrepo.shell(owner=owner, limit=limit, visibility=visibility, language=language,
                     topic=topic, source=source, forks=forks, archived=archived,
                     no_archived=no_archived, keyword=search, fresh=fresh)


def _pick_target(target: str, what: str) -> str:
    """子命令的仓库参数: 留空就用仓库挑选器 (过滤选项同 `gitx repos`)."""
    return ghrepo.resolve(target, what=what, **_PICK)


def _fresh() -> bool:
    """`--fresh` 写在子命令前面 (`gitx repos --fresh view ...`) 时, 由子命令从这里取."""
    return bool(_PICK.get("fresh"))


_UNSET = ("", None, False)


def _merged(**given: object) -> dict[str, object]:
    """子命令自己的过滤选项优先; 没给 (空串 / 未开) 就沿用子命令前面的那些.

    因此 `gitx repos -o cli list` 与 `gitx repos list -o cli` 等价 —— 选项写在子命令前后都生效。
    """
    merged = dict(given)
    for name, value in given.items():
        if value in _UNSET and _PICK.get(name) not in _UNSET:
            merged[name] = _PICK[name]
    return merged


@repos_app.command("list")
def repos_list(
    limit: Annotated[int | None, typer.Option(
        "--limit", "-n", help="列几个 (缺省用配置 repos_limit)")] = None,
    owner: Annotated[str, typer.Option("--owner", "-o", help="看谁的仓库 (默认当前登录账号)")] = "",
    visibility: Annotated[str, typer.Option("--visibility",
                                            help="按可见性过滤: public / private / internal")] = "",
    language: Annotated[str, typer.Option("--language", "-l", help="按主要语言过滤")] = "",
    topic: Annotated[str, typer.Option("--topic", "-t", help="按话题过滤")] = "",
    source: Annotated[bool, typer.Option("--source", help="只看原创 (非复刻) 仓库")] = False,
    forks: Annotated[bool, typer.Option("--fork", help="只看复刻仓库")] = False,
    archived: Annotated[bool, typer.Option("--archived", help="只看已归档仓库")] = False,
    no_archived: Annotated[bool, typer.Option("--no-archived", help="排除已归档仓库")] = False,
    search: Annotated[str, typer.Option(
        "--search", "-q", help="按关键词搜 (搜得到全部仓库, 不受 -n 限制)")] = "",
    fresh: Annotated[bool, typer.Option("--fresh", help="不吃本地缓存, 重新向 GitHub 取一次")] = False,
) -> None:
    """列出仓库: 仓库 / 描述 / 可见性 / star / 语言 / 更新 / 标记.

    给 [key]-q[/key] 就是搜索 ([key]gitx repos list -q dotfiles[/key]), 否则按最近推送列前 [key]-n[/key] 个。
    """
    picked = _merged(owner=owner, visibility=visibility, language=language, topic=topic,
                     source=source, forks=forks, archived=archived,
                     no_archived=no_archived, keyword=search, fresh=fresh)
    ghrepo.list_repos(limit=int(limit or _PICK.get("limit") or config.default_limit("repos_limit", 30)),
                      **picked)  # type: ignore[arg-type]


@repos_app.command("edit")
def repos_edit(
    target: Annotated[str, typer.Argument(metavar="[仓库]", help=_REPO_ARG)] = "",
    description: Annotated[str | None, typer.Option("--description", "-d",
                                                    help="新描述 (空串 = 清空)")] = None,
    homepage: Annotated[str | None, typer.Option("--homepage", "-H",
                                                 help="新主页地址 (空串 = 清空)")] = None,
    add_topic: Annotated[list[str] | None, typer.Option("--topic", "-t", help="加话题 (可重复)")] = None,
    remove_topic: Annotated[list[str] | None, typer.Option("--remove-topic",
                                                           help="删话题 (可重复)")] = None,
    visibility: Annotated[str, typer.Option("--visibility",
                                            help="改成 public / private / internal (会确认)")] = "",
    default_branch: Annotated[str, typer.Option("--default-branch", "-b", help="改默认分支")] = "",
    template: Annotated[bool | None, typer.Option("--template/--no-template",
                                                  help="模板仓库开关")] = None,
    issues: Annotated[bool | None, typer.Option("--issues/--no-issues", help="议题开关")] = None,
    wiki: Annotated[bool | None, typer.Option("--wiki/--no-wiki", help="Wiki 开关")] = None,
    projects: Annotated[bool | None, typer.Option("--projects/--no-projects", help="项目开关")] = None,
    discussions: Annotated[bool | None, typer.Option("--discussions/--no-discussions",
                                                     help="讨论开关")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="跳过改可见性的确认")] = False,
) -> None:
    """改仓库设置(描述 / 主页 / 话题 / 可见性 / 默认分支 / 功能开关 / 模板).

    什么选项都不给 = 进交互式编辑界面 (上下键选项, 回车确认):

      gitx repos edit                挑一个仓库 -> 编辑界面
      gitx repos edit owner/repo     直接进这个仓库的编辑界面

    非交互则直接给选项, 例: [key]gitx repos edit owner/repo -d "新描述" -t cli --no-wiki[/key]
    """
    features: dict[str, bool] = {
        field: value for field, value in (("hasIssuesEnabled", issues), ("hasWikiEnabled", wiki),
                                          ("hasProjectsEnabled", projects),
                                          ("hasDiscussionsEnabled", discussions))
        if value is not None}
    if not (description is not None or homepage is not None or add_topic or remove_topic
            or visibility or default_branch or template is not None or features):
        if not console.is_terminal():
            console.error('没有要改的项\n提示: 直接给选项, 如 gitx repos edit owner/repo -d "新描述"')
        ghrepo.shell(target, **_PICK)
        return
    nwo = _pick_target(target, "edit")
    if visibility and visibility not in ("public", "private", "internal"):
        console.error("可见性只能是 public / private / internal")
    if visibility and not yes:
        console.warn("改可见性有副作用: 会掉 star / 断掉复刻关系 / 关闭推送规则集")
        if not console.ask(f"确认把 {nwo} 改成 {visibility}?", default=False):
            console.warn("已取消")
            return
    ghrepo.edit(nwo, description=description, homepage=homepage, add_topics=tuple(add_topic or ()),
                remove_topics=tuple(remove_topic or ()), visibility=visibility,
                default_branch=default_branch, template=template, features=features or None)


@repos_app.command("view")
def repos_view(
    target: Annotated[str, typer.Argument(metavar="[仓库]", help=_REPO_ARG)] = "",
    web: Annotated[bool, typer.Option("--web", "-w", help="在浏览器打开仓库页面")] = False,
) -> None:
    """看仓库的当前设置: 描述 / 主页 / 话题 / 可见性 / 默认分支 / 功能."""
    ghrepo.view(_pick_target(target, "view"), web=web, fresh=_fresh())


@repos_app.command("clone")
def repos_clone(
    target: Annotated[str, typer.Argument(metavar="[仓库]", help=_REPO_ARG)] = "",
    dest: Annotated[str, typer.Option("--dir", "-D", help="放到哪个目录")] = "",
    depth: Annotated[int, typer.Option("--depth", "-d", help="克隆深度, 0 = 完整克隆")] = 1,
) -> None:
    """克隆到本地 ([info]公开仓库和 gitx download 一样走加速[/info]; 私有仓库交给 gh, 它自带凭据)."""
    ghrepo.clone(_pick_target(target, "clone"), dest, depth=depth)


@repos_app.command("create")
def repos_create(
    name: Annotated[str, typer.Argument(metavar="名字", help="新仓库名; owner/名字 可指定归属")],
    description: Annotated[str, typer.Option("--description", "-d", help="仓库描述")] = "",
    homepage: Annotated[str, typer.Option("--homepage", "-H", help="主页地址")] = "",
    visibility: Annotated[str, typer.Option("--visibility",
                                            help="public / private / internal, 缺省交给 gh 询问")] = "",
    readme: Annotated[bool, typer.Option("--readme", help="顺带初始化一个 README")] = False,
    gitignore: Annotated[str, typer.Option("--gitignore", "-g", help=".gitignore 模板名 (如 Python)")] = "",
    license_: Annotated[str, typer.Option("--license", help="开源许可证名 (如 mit)")] = "",
    template: Annotated[str, typer.Option("--template", "-p", help="按模板仓库创建")] = "",
    source: Annotated[str, typer.Option("--source", "-s", help="用本地目录当源 (连同远程一起配好)")] = "",
    push: Annotated[bool, typer.Option("--push", help="把本地提交推上去")] = False,
    clone_: Annotated[bool, typer.Option("--clone", "-c", help="顺手克隆到当前目录")] = False,
    no_issues: Annotated[bool, typer.Option("--no-issues", help="不启用议题")] = False,
    no_wiki: Annotated[bool, typer.Option("--no-wiki", help="不启用 Wiki")] = False,
    team: Annotated[str, typer.Option("--team", help="给组织里的某个团队开权限")] = "",
) -> None:
    """新建仓库 (默认交给 gh 自己询问可见性等).

    例: [key]gitx repos create my-tool --source . --push --public -d "一句话介绍"[/key]
    """
    ghrepo.create(name, visibility=visibility, description=description, homepage=homepage,
                  readme=readme, gitignore=gitignore, license_=license_, template=template,
                  source=source, push=push, clone_=clone_, disable_issues=no_issues,
                  disable_wiki=no_wiki, team=team)


@repos_app.command("fork")
def repos_fork(
    target: Annotated[str, typer.Argument(metavar="[仓库]", help=_REPO_ARG)] = "",
    clone_: Annotated[bool, typer.Option("--clone", "-c", help="顺带克隆到本地")] = False,
    remote: Annotated[bool, typer.Option("--remote", help="给本地仓库加一个远程")] = False,
    org: Annotated[str, typer.Option("--org", help="复刻到某个组织下")] = "",
    fork_name: Annotated[str, typer.Option("--fork-name", help="复刻后改名")] = "",
    default_branch_only: Annotated[bool, typer.Option("--default-branch-only",
                                                      help="只复刻默认分支")] = False,
) -> None:
    """把仓库复刻到自己账号下 (别人的仓库也能复刻: gitx repos fork cli/cli)."""
    ghrepo.fork(_pick_target(target, "fork"), clone_=clone_, remote=remote, org=org,
                fork_name=fork_name, default_branch_only=default_branch_only)


@repos_app.command("rename")
def repos_rename(
    target: Annotated[str, typer.Argument(metavar="[仓库]", help=_REPO_ARG)] = "",
    new_name: Annotated[str, typer.Argument(metavar="[新名字]", help="新仓库名 (不含 owner)")] = "",
) -> None:
    """改仓库名 (新名字留空就问一次; 本地远程地址需要自己 gitx remote set-url)."""
    nwo = _pick_target(target, "rename")
    if not new_name:
        if not console.is_terminal():
            console.error("请给出新名字: gitx repos rename owner/repo 新名字")
        new_name = console.text("新仓库名 (不含 owner)", default=nwo.split("/")[-1]) or ""
    ghrepo.rename(nwo, new_name)


@repos_app.command("archive")
def repos_archive(target: Annotated[str, typer.Argument(metavar="[仓库]", help=_REPO_ARG)] = "") -> None:
    """归档仓库 (归档后变只读)."""
    ghrepo.archive(_pick_target(target, "archive"))


@repos_app.command("unarchive")
def repos_unarchive(target: Annotated[str, typer.Argument(metavar="[仓库]", help=_REPO_ARG)] = "") -> None:
    """取消归档."""
    ghrepo.archive(_pick_target(target, "unarchive"), archived=False)


@repos_app.command("sync")
def repos_sync(
    target: Annotated[str, typer.Argument(metavar="[仓库]", help=_REPO_ARG)] = "",
    source: Annotated[str, typer.Option("--source", "-s", help="源仓库; 缺省 = 它的上游")] = "",
    branch: Annotated[str, typer.Option("--branch", "-b", help="同步哪个分支 (缺省默认分支)")] = "",
    force: Annotated[bool, typer.Option("--force", help="硬对齐 (丢弃目标分支上的提交)")] = False,
) -> None:
    """把仓库对齐到源仓库 (复刻与上游同步最常用)."""
    ghrepo.sync(_pick_target(target, "sync"), source=source, branch=branch, force=force)


@repos_app.command("star")
def repos_star(target: Annotated[str, typer.Argument(metavar="[仓库]", help=_REPO_ARG)] = "") -> None:
    """收藏仓库 (别人的也行: gitx repos star cli/cli)."""
    ghrepo.star(_pick_target(target, "star"), on=True)


@repos_app.command("unstar")
def repos_unstar(target: Annotated[str, typer.Argument(metavar="[仓库]", help=_REPO_ARG)] = "") -> None:
    """取消收藏."""
    ghrepo.star(_pick_target(target, "unstar"), on=False)


@repos_app.command("set-default")
def repos_set_default(target: Annotated[str, typer.Argument(metavar="[仓库]", help=_REPO_ARG)] = "") -> None:
    """把仓库设为当前目录的默认仓库 (之后 gh / gitx 少写 -R)."""
    ghrepo.set_default(_pick_target(target, "set-default"))


@repos_app.command("delete")
def repos_delete(
    target: Annotated[str, typer.Argument(metavar="[仓库]", help=_REPO_ARG)] = "",
    yes: Annotated[bool, typer.Option("--yes", "-y", help="跳过确认")] = False,
) -> None:
    """删除仓库 ([err]不可恢复[/err], 需要 gh 有 delete_repo 权限)."""
    ghrepo.delete(_pick_target(target, "delete"), yes=yes)


app.add_typer(repos_app, name="repos", rich_help_panel=PANEL_GHR)


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
    source = _checked_source("proxy", source)
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
    source = _checked_source("proxy", source)
    config.save({**config.load(), "proxy": source})
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


# ================================================================ 账号 (gh 登录态)

auth_app = typer.Typer(help="账号: 登录 / 退出 / 切换 / 权限 / 令牌 (交给已安装的 gh)",
                       rich_markup_mode="rich", invoke_without_command=True,
                       context_settings={"help_option_names": ["-h", "--help"]})

_HOST_HELP = "GitHub 主机名 (只有 GitHub Enterprise 才需要)"


@auth_app.callback()
def _auth_root(
    ctx: typer.Context,
    hostname: Annotated[str, typer.Option("--hostname", help=_HOST_HELP)] = "",
    active: Annotated[bool, typer.Option("--active", help="只看当前账号")] = False,
    show_token: Annotated[bool, typer.Option("--show-token", help="连令牌一起显示 (交给 gh 打印)")] = False,
) -> None:
    # 不带子命令 = 看登录状态
    if ctx.invoked_subcommand is None:
        auth.status(hostname=hostname, active_only=active, show_token=show_token)


@auth_app.command("status")
def auth_status(
    hostname: Annotated[str, typer.Option("--hostname", help=_HOST_HELP)] = "",
    active: Annotated[bool, typer.Option("--active", help="只看当前账号")] = False,
    show_token: Annotated[bool, typer.Option("--show-token", help="连令牌一起显示 (交给 gh 打印)")] = False,
) -> None:
    """看登录状态: 主机 / 账号 / 状态 / git 协议."""
    auth.status(hostname=hostname, active_only=active, show_token=show_token)


@auth_app.command("login")
def auth_login(
    hostname: Annotated[str, typer.Option("--hostname", help=_HOST_HELP)] = "",
    git_protocol: Annotated[str, typer.Option("--git-protocol", "-p", help="git 协议: ssh / https")] = "",
    web: Annotated[bool, typer.Option("--web", "-w", help="用浏览器登录")] = False,
    with_token: Annotated[bool, typer.Option("--with-token", help="从标准输入读令牌 (不进命令行历史)")] = False,
    scopes: Annotated[list[str] | None, typer.Option("--scopes", "-s", help="额外申请的权限 (可重复)")] = None,
    clipboard: Annotated[bool, typer.Option("--clipboard", help="把设备码复制到剪贴板")] = False,
    skip_ssh_key: Annotated[bool, typer.Option("--skip-ssh-key", help="不生成 / 上传 SSH 密钥")] = False,
    insecure_storage: Annotated[bool, typer.Option("--insecure-storage", help="令牌明文存盘 (不用凭据管理器)")] = False,
) -> None:
    """登录 GitHub (不加选项时由 gh 交互询问登录方式).

    例: [key]echo <令牌> | gitx auth login --with-token[/key] 或 [key]gitx auth login --web[/key]
    """
    auth.login(hostname=hostname, git_protocol=git_protocol, web=web, with_token=with_token,
               scopes=list(scopes or []), clipboard=clipboard, skip_ssh_key=skip_ssh_key,
               insecure_storage=insecure_storage)


@auth_app.command("logout")
def auth_logout(
    user: Annotated[str, typer.Argument(metavar="[账号]", help="要退出的账号; 留空由 gh 选择")] = "",
    hostname: Annotated[str, typer.Option("--hostname", help=_HOST_HELP)] = "",
) -> None:
    """退出登录."""
    auth.logout(user, hostname=hostname)


@auth_app.command("switch")
def auth_switch(
    user: Annotated[str, typer.Argument(metavar="[账号]", help="切到哪个账号; 留空由 gh 列出来挑")] = "",
    hostname: Annotated[str, typer.Option("--hostname", help=_HOST_HELP)] = "",
) -> None:
    """切换当前账号 (登录了多个账号时用)."""
    auth.switch(user, hostname=hostname)


@auth_app.command("refresh")
def auth_refresh(
    hostname: Annotated[str, typer.Option("--hostname", help=_HOST_HELP)] = "",
    scopes: Annotated[list[str] | None, typer.Option("--scopes", "-s", help="要补的权限 (可重复)")] = None,
    remove_scopes: Annotated[list[str] | None, typer.Option("--remove-scopes", help="要收回的权限 (可重复)")] = None,
    reset_scopes: Annotated[bool, typer.Option("--reset-scopes", help="重置为最小权限集")] = False,
    clipboard: Annotated[bool, typer.Option("--clipboard", help="把设备码复制到剪贴板")] = False,
    insecure_storage: Annotated[bool, typer.Option("--insecure-storage", help="令牌明文存盘")] = False,
) -> None:
    """调整授权范围: [key]gitx auth refresh -s workflow[/key] 补权限."""
    auth.refresh(hostname=hostname, scopes=list(scopes or []),
                 remove_scopes=list(remove_scopes or []), reset_scopes=reset_scopes,
                 clipboard=clipboard, insecure_storage=insecure_storage)


@auth_app.command("token")
def auth_token(
    hostname: Annotated[str, typer.Option("--hostname", help=_HOST_HELP)] = "",
    user: Annotated[str, typer.Option("--user", "-u", help="取哪个账号的令牌")] = "",
    save: Annotated[bool, typer.Option("--save", help="顺手写进 gitx 配置 (token 项)")] = False,
) -> None:
    """打印当前账号的令牌 ([key]--save[/key] 写进 gitx 配置提升 API 限额).

    只打印时原样输出 gh 的结果, 方便 [key]gitx auth token > token.txt[/key] 这样接管道。
    """
    auth.token(hostname=hostname, user=user, save=save)


@auth_app.command("setup-git")
def auth_setup_git(
    hostname: Annotated[str, typer.Option("--hostname", help=_HOST_HELP)] = "",
    force: Annotated[bool, typer.Option("--force", "-f", help="主机不认识时也强行配置")] = False,
) -> None:
    """让 git 的 https 推送 / 拉取走 gh 的凭据."""
    auth.setup_git(hostname=hostname, force=force)


app.add_typer(auth_app, name="auth", rich_help_panel=PANEL_AUTH)


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
    for name, prefix in [*accel.PROVIDERS.items(), ("off", None)]:
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
    import urllib.request  # 仅网络命令需要, 避免拖慢其它命令

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


# ================================================================ 工作区 (克隆 + 统一管理)

ws_app = typer.Typer(help="工作区: 克隆 GitHub 项目到指定目录, 并统一管理所有已克隆的仓库", rich_markup_mode="rich",
                     invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})


@ws_app.callback()
def _ws_root(
    ctx: typer.Context,
    space: Annotated[str, typer.Option("--space", "-s", help="操作哪个工作区 (缺省 = 默认)")] = "",
) -> None:
    # 不带子命令 = 列出工作区 (`gitx ws <链接>` 由 dispatch 改写成 gitx ws clone)
    ctx.obj = {"space": space}  # 子命令未显式给 -s 时沿用这里的值
    if ctx.invoked_subcommand is None:
        workspace.list_repos(_ws_space(ctx, space))


def _ws_space(ctx: typer.Context, flag: str) -> str:
    """本次生效的工作区名: 子命令的 -s > 组级 -s > GITX_WS_SPACE > 默认."""
    if flag:
        return flag
    carried = (ctx.obj or {}).get("space") if isinstance(ctx.obj, dict) else ""
    return str(carried or workspace.space_name())


@ws_app.command("list")
def ws_list(
    ctx: typer.Context,
    space: Annotated[str, typer.Option("--space", "-s", help="操作哪个工作区 (缺省 = 默认)")] = "",
) -> None:
    """列出工作区里的全部仓库 (状态 / 分支 / 领先落后 / 最新提交)."""
    workspace.list_repos(_ws_space(ctx, space))


@ws_app.command("clone")
def ws_clone(
    ctx: typer.Context,
    target: Annotated[str, typer.Argument(metavar="仓库|链接", help="owner/repo 或 GitHub 链接")],
    dest: Annotated[str, typer.Argument(metavar="[目录]", help="克隆到哪个目录; 已存在的目录视为父目录")] = "",
    depth: Annotated[int | None, typer.Option("--depth", "-d", help="克隆深度, 0 = 完整克隆")] = None,
    branch: Annotated[str, typer.Option("--branch", "-b", help="指定分支")] = "",
    submodules: Annotated[bool, typer.Option("--submodules", help="连同子模组一起拉取")] = False,
    root_override: Annotated[str, typer.Option("--root", help="本次使用的工作区根目录")] = "",
    name: Annotated[str, typer.Option("--name", "-n", help="清单里的名字 (默认取仓库名)")] = "",
    proxy: Annotated[str | None, typer.Option("--proxy", help="本次加速源")] = None,
    no_proxy: Annotated[bool, typer.Option("--no-proxy", help="本次直连")] = False,
    space: Annotated[str, typer.Option("--space", "-s", help="登记到哪个工作区 (缺省 = 默认)")] = "",
) -> None:
    """克隆并登记一个仓库 (显式写法, 等价 gitx ws <仓库>)."""
    workspace.clone(target, dest, depth=depth, branch=branch, proxy=proxy, no_proxy=no_proxy,
                    submodules=submodules, name=name, root_override=root_override,
                    space=_ws_space(ctx, space))


@ws_app.command("add")
def ws_add(
    ctx: typer.Context,
    paths: Annotated[list[str], typer.Argument(metavar="目录...", help="已有本地克隆的目录")],
    name: Annotated[str, typer.Option("--name", "-n", help="清单里的名字 (仅单个目录时有效)")] = "",
    space: Annotated[str, typer.Option("--space", "-s", help="登记到哪个工作区 (缺省 = 默认)")] = "",
) -> None:
    """把已有的本地克隆登记进工作区."""
    for path in paths:
        workspace.register_path(path, name=name if len(paths) == 1 else "",
                                space=_ws_space(ctx, space))


@ws_app.command("rm")
def ws_rm(
    ctx: typer.Context,
    names: Annotated[list[str], typer.Argument(metavar="名字...", help="要移除的仓库 (名字 / owner/repo / 路径)")],
    delete: Annotated[bool, typer.Option("--delete", help="连本地目录一起删掉")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="删除目录时跳过确认")] = False,
    space: Annotated[str, typer.Option("--space", "-s", help="操作哪个工作区 (缺省 = 默认)")] = "",
) -> None:
    """从工作区移除仓库 (默认只移出清单, 不动文件)."""
    workspace.remove(list(names), delete=delete, yes=yes, space=_ws_space(ctx, space))


@ws_app.command("status")
def ws_status(
    ctx: typer.Context,
    names: Annotated[list[str] | None, typer.Argument(metavar="[名字...]", help="缺省 = 全部")] = None,
    all_: Annotated[bool, typer.Option("--all", "-a", help="全部仓库")] = False,
    space: Annotated[str, typer.Option("--space", "-s", help="操作哪个工作区 (缺省 = 默认)")] = "",
) -> None:
    """逐个仓库看改动与领先 / 落后."""
    workspace.status(list(names or []), all_=all_, space=_ws_space(ctx, space))


@ws_app.command("sync")
def ws_sync(
    ctx: typer.Context,
    names: Annotated[list[str] | None, typer.Argument(metavar="[名字...]", help="缺省 = 全部")] = None,
    all_: Annotated[bool, typer.Option("--all", "-a", help="全部仓库")] = False,
    jobs: Annotated[int, typer.Option("--jobs", "-j", help="并行个数 (仅 fetch 阶段; 1 = 顺序)")] = 1,
    proxy: Annotated[str | None, typer.Option("--proxy", help="本次加速源")] = None,
    no_proxy: Annotated[bool, typer.Option("--no-proxy", help="本次直连")] = False,
    space: Annotated[str, typer.Option("--space", "-s", help="操作哪个工作区 (缺省 = 默认)")] = "",
) -> None:
    """逐个拉取 (fetch + 变基), 工作区有改动的仓库只 fetch 不合并."""
    workspace.sync(list(names or []), pull=True, all_=all_, proxy=proxy, no_proxy=no_proxy,
                   jobs=jobs, space=_ws_space(ctx, space))


@ws_app.command("fetch")
def ws_fetch(
    ctx: typer.Context,
    names: Annotated[list[str] | None, typer.Argument(metavar="[名字...]", help="缺省 = 全部")] = None,
    all_: Annotated[bool, typer.Option("--all", "-a", help="全部仓库")] = False,
    jobs: Annotated[int, typer.Option("--jobs", "-j", help="并行个数 (1 = 顺序)")] = 1,
    proxy: Annotated[str | None, typer.Option("--proxy", help="本次加速源")] = None,
    no_proxy: Annotated[bool, typer.Option("--no-proxy", help="本次直连")] = False,
    space: Annotated[str, typer.Option("--space", "-s", help="操作哪个工作区 (缺省 = 默认)")] = "",
) -> None:
    """只更新远端跟踪引用, 不改工作区."""
    workspace.sync(list(names or []), pull=False, all_=all_, proxy=proxy, no_proxy=no_proxy,
                   jobs=jobs, space=_ws_space(ctx, space))


@ws_app.command("info")
def ws_info(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(metavar="名字", help="仓库名 / owner/repo / 路径")],
    space: Annotated[str, typer.Option("--space", "-s", help="操作哪个工作区 (缺省 = 默认)")] = "",
) -> None:
    """看某个仓库的概览 (同 gitx info)."""
    workspace.info(name, space=_ws_space(ctx, space))


@ws_app.command("path")
def ws_path(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(metavar="名字", help="仓库名 / owner/repo / 路径")],
    space: Annotated[str, typer.Option("--space", "-s", help="操作哪个工作区 (缺省 = 默认)")] = "",
) -> None:
    """只打印绝对路径 (cd "$(gitx ws path x)")."""
    console.print(workspace.resolve_path(name, space=_ws_space(ctx, space)))


@ws_app.command("cd")
def ws_cd(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(metavar="名字", help="仓库名 / owner/repo / 路径")],
    shell: Annotated[bool, typer.Option("--shell", help="输出 cd 命令 (供 eval 使用)")] = False,
    space: Annotated[str, typer.Option("--space", "-s", help="操作哪个工作区 (缺省 = 默认)")] = "",
) -> None:
    """打印仓库路径与进入方法 (子进程不能改父 shell 的目录)."""
    target = workspace.resolve_path(name, space=_ws_space(ctx, space))
    if shell:
        console.print(f'cd "{target}"')
        return
    console.print(target)
    console.hint(f'进入: cd "{target}"   |   或 eval "$(gitx ws cd {name} --shell)"')


@ws_app.command("each", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def ws_each(
    ctx: typer.Context,
    command: Annotated[list[str], typer.Argument(metavar="命令...", help="要在每个仓库里执行的命令")],
    names: Annotated[list[str] | None, typer.Option("--name", "-n", help="只在这些仓库里执行 (可重复)")] = None,
    all_: Annotated[bool, typer.Option("--all", "-a", help="全部仓库")] = False,
    space: Annotated[str, typer.Option("--space", "-s", help="操作哪个工作区 (缺省 = 默认)")] = "",
) -> None:
    """在每个仓库目录里执行同一条命令."""
    workspace.each(list(command), list(names or []), all_=all_, space=_ws_space(ctx, space))


@ws_app.command("find")
def ws_find(
    ctx: typer.Context,
    keyword: Annotated[str, typer.Argument(metavar="关键词", help="按名字 / owner/repo / 路径搜")],
    space: Annotated[str, typer.Option("--space", "-s", help="操作哪个工作区 (缺省 = 默认)")] = "",
) -> None:
    """在工作区里按关键词找仓库."""
    workspace.find(keyword, space=_ws_space(ctx, space))


@ws_app.command("root")
def ws_root_cmd(
    ctx: typer.Context,
    path: Annotated[str | None, typer.Argument(metavar="[目录]", help="新的工作区根目录; 留空 = 查看")] = None,
    space: Annotated[str, typer.Option("--space", "-s", help="操作哪个工作区 (缺省 = 默认)")] = "",
) -> None:
    """查看或设置某个工作区的根目录 (缺省 = 默认工作区)."""
    chosen = _ws_space(ctx, space)
    if path:
        workspace.set_root(path, chosen)
    else:
        console.info(f"工作区 {chosen} 的根目录: {workspace.root(chosen)}")


@ws_app.command("prune")
def ws_prune(
    ctx: typer.Context,
    space: Annotated[str, typer.Option("--space", "-s", help="操作哪个工作区 (缺省 = 默认)")] = "",
) -> None:
    """清理清单里目录已不存在的项."""
    workspace.prune(_ws_space(ctx, space))


@ws_app.command("use")
def ws_use(
    name: Annotated[str | None, typer.Argument(
        metavar="[名字]", help="要设为默认的工作区 (不存在就新建); 留空 = 看当前默认")] = None,
    path: Annotated[str, typer.Argument(
        metavar="[目录]", help="工作区根目录 (任意位置, 不必在 ~ 下); 已存在的工作区会改根目录")] = "",
    root: Annotated[str, typer.Option("--root", help="同上 (等价写法)")] = "",
) -> None:
    """切换默认工作区 (之后不带 -s 的命令都作用在它上面; 不存在则新建).

    根目录可以放在任何地方: [key]gitx ws use work ~/code[/key] / [key]gitx ws use work /data/repos[/key];
    只给名字时才是 ~/gitx-workspaces/<名字>。
    """
    if not name:
        chosen, item = workspace.get_space(required=True)
        console.info(f"默认工作区: {chosen} ({item['root']}, {len(item['repos'])} 个仓库)")
        console.hint("切换: gitx ws use <名字> [目录]   |   全部工作区: gitx ws spaces")
        return
    workspace.use(name, root or path)


@ws_app.command("move")
def ws_move(
    ctx: typer.Context,
    dest: Annotated[str, typer.Argument(metavar="新目录", help="工作区的新根目录 (任意位置)")],
    space: Annotated[str, typer.Option("--space", "-s", help="操作哪个工作区 (缺省 = 默认)")] = "",
) -> None:
    """把工作区整个搬到别处 (仓库目录一起搬, 清单里的路径同步更新)."""
    workspace.move(dest, space=_ws_space(ctx, space))


@ws_app.command("spaces")
def ws_spaces() -> None:
    """列出所有工作区 (默认的标出来)."""
    workspace.list_spaces()


@ws_app.command("drop")
def ws_drop(
    name: Annotated[str, typer.Argument(metavar="名字", help="要删除的工作区")],
    delete: Annotated[bool, typer.Option("--delete", help="连它管理的仓库目录一起删掉")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="跳过确认")] = False,
) -> None:
    """删除工作区 (默认只删清单记录, 不动目录)."""
    workspace.drop_space(name, delete=delete, yes=yes)


app.add_typer(ws_app, name="ws", rich_help_panel=PANEL_DL)


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
    if key == "workspace":  # 工作区根目录的真源在清单里, 这里转交给它 (顺带同步配置)
        workspace.set_root(str(value) or workspace.DEFAULT_ROOT)
        return
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
    import shlex

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


cache_app = typer.Typer(help="缓存管理: 查看 / 清理 ~/.cache/gitx (可再生的数据)",
                        rich_markup_mode="rich", invoke_without_command=True,
                        context_settings={"help_option_names": ["-h", "--help"]})


@cache_app.callback()
def _cache_root(ctx: typer.Context) -> None:
    # 不带子命令 = 查看缓存占用
    if ctx.invoked_subcommand is None:
        cache.info()


@cache_app.command("info")
def cache_info() -> None:
    """查看缓存目录与占用 (整文件 + 键值缓存)."""
    cache.info()


@cache_app.command("list")
def cache_list(
    all_: Annotated[bool, typer.Option("--all", "-a", help="连已过期的也列出来")] = False,
) -> None:
    """列出缓存明细: 缓存键 / 写入时间 / 有效期 / 状态."""
    cache.list_entries(all_=all_)


@cache_app.command("prune")
def cache_prune() -> None:
    """只清掉已过期的缓存 (留着的都还在有效期内)."""
    cache.prune()


@cache_app.command("clear")
def cache_clear(
    yes: Annotated[bool, typer.Option("--yes", "-y", help="跳过确认")] = False,
) -> None:
    """清空缓存 (下次使用自动重建)."""
    cache.clear(yes=yes)


# ================================================================ 守护进程

PANEL_DAEMON = "性能 (守护进程)"

daemon_app = typer.Typer(help="守护进程: 低配机上把启动开销摊到一次 (默认关闭)",
                         rich_markup_mode="rich", invoke_without_command=True,
                         context_settings={"help_option_names": ["-h", "--help"]})


@daemon_app.callback()
def _daemon_root(ctx: typer.Context) -> None:
    # 不带子命令 = 看状态 (正常情况已被 dispatch 的快速通道接管, 这里只是兜底)
    if ctx.invoked_subcommand is None:
        raise SystemExit(daemon.control(["status"]))


# status / start / stop / restart 走 dispatch 的零依赖快速通道 (见 daemon.control):
# 这几条必须本地跑 (交给守护进程执行会死锁), 因此不导入 typer / rich, 保持在毫秒级。
# 这里只放需要 typer 的两条: bench (实测耗时) 与 serve (内部前台运行)。


@daemon_app.command("bench")
def daemon_bench(
    runs: Annotated[int, typer.Option("--runs", "-n", help="各跑几轮 (取中位数)")] = 3,
    cmd: Annotated[str, typer.Option(
        "--cmd", help="用哪条命令来量 (默认 config path; 别用 gitx daemon ... —— 它按设计不走守护进程)")] = "config path",
) -> None:
    """实测这台机器上"有守护进程 vs 没有"的启动耗时 (各跑几轮取中位数).

    量的是同一条命令的两种走法: 本地执行 (环境里带 GITX_IN_DAEMON=1, 等价于没开守护进程)
    与经守护进程执行。导入便宜 (快盘 + 热缓存) 的机器上差距小, 低配机 / 冷缓存 / 机械盘上差距大。
    """
    import os
    import statistics
    import subprocess
    import time

    argv = cmd.split()
    count = max(1, runs)

    def measure(routed: bool) -> float:
        env = dict(os.environ)
        if routed:
            env.pop("GITX_IN_DAEMON", None)
        else:
            env["GITX_IN_DAEMON"] = "1"  # 入口看到它就只本地跑, 等于"没开守护进程"
        times = []
        for _ in range(count):
            start = time.perf_counter()
            subprocess.run([sys.executable, "-m", "gitx", *argv], env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            times.append(time.perf_counter() - start)
        return statistics.median(times)

    if not daemon.enabled():
        console.warn("配置里 daemon = false: 「经守护进程」那一行不会真的走守护进程\n"
                     "提示: 开启用 gitx config set daemon true")
    if not daemon.running():
        daemon.spawn(force=True)
    console.step(f"各跑 {count} 轮: gitx {' '.join(argv)}")
    local, routed = measure(False), measure(True)
    table = console.table("走法", "中位耗时", title="启动耗时实测")
    table.add_row(console.txt("本地执行 (没守护进程)"), console.txt(f"{local * 1000:.0f} ms"))
    table.add_row(console.txt("经守护进程"), console.txt(f"{routed * 1000:.0f} ms"))
    console.print(table)
    saved = local - routed
    if saved > 0.02:
        console.done(f"每次省约 {saved * 1000:.0f} ms")
    else:
        console.info("这台机器上导入本来就便宜 (快盘 / 热缓存), 省下的不多; "
                     "低配机 / 冷缓存 / 机械盘上差距更大")


@daemon_app.command("serve", hidden=True)
def daemon_serve() -> None:
    """(内部) 前台运行守护进程 —— 由 gitx 自己在后台调用."""
    daemon.serve()




app.add_typer(cache_app, name="cache", rich_help_panel=PANEL_CONF)
app.add_typer(daemon_app, name="daemon", rich_help_panel=PANEL_DAEMON)


@app.command("upgrade", rich_help_panel=PANEL_CONF)
def upgrade_cmd(
    check: Annotated[bool, typer.Option("--check", help="只检查是否有新版本, 不安装")] = False,
    force: Annotated[bool, typer.Option("--force", help="同版本或更旧也强制重装")] = False,
    no_proxy: Annotated[bool, typer.Option("--no-proxy", help="本次直连, 不走加速")] = False,
) -> None:
    """自更新到最新版本 (查 Release 与下载 wheel 都走加速)."""
    upgrade.run(check_only=check, force=force, no_proxy=no_proxy)


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
def doctor(
    fix: Annotated[bool, typer.Option("--fix", help="交互式修复可自动处理的问题 (编码 / pull 策略 / 上游)")] = False,
) -> None:
    """环境自检: git / gh / 仓库 / 加速源 / 编码 (--fix 可顺手修好)."""
    cfg = config.load()
    table = console.table("项目", "状态", title=f"gitx {__version__} 环境自检")
    table.add_row("配置文件", console.txt(config.config_path()))
    _, gitver = gitcmd.capture(["git", "--version"])
    table.add_row("git", console.txt(gitver or "未找到"))
    import shutil

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
    if fix:
        _doctor_fix()
    _proxy_test()


def _doctor_fix() -> None:
    """按需修好几项常见问题 (逐项询问, assume_yes=true 时自动全做)."""
    console.step("检查可自动修复的项...")
    prefix = config.active_proxy()
    fixes: list[tuple[str, str, object]] = []
    quotepath = gitcmd.capture(["git", "config", "--global", "--get", "core.quotepath"])[1]
    if quotepath not in ("false", "0", "off"):
        fixes.append(("中文文件名会转义", "写入 core.quotepath=false 与 UTF-8 日志编码",
                      lambda: gitcmd.apply_zh_config("--global")))
    if not gitcmd.capture(["git", "config", "--global", "--get", "pull.rebase"])[1]:
        fixes.append(("git pull 未设调和策略", "设置 pull.rebase=false, 避免裸 git pull 在分支分歧时报错",
                      lambda: gitcmd.capture(["git", "config", "--global", "pull.rebase", "false"])))
    if gitcmd.is_repo():
        branch = gitcmd.current_branch()
        if branch and not gitcmd.has_upstream() and gitcmd.remote_branch_exists("origin", branch, ".", prefix):
            fixes.append((f"分支 {branch} 未关联上游", f"关联 origin/{branch}",
                          lambda: gitcmd.set_upstream("origin", branch)))
    if not fixes:
        console.done("没有需要修复的项")
        return
    for title, desc, action in fixes:
        if console.ask(f"{title} —— {desc}?", default=True):
            action()  # type: ignore[operator]
            console.done(f"已处理: {title}")
        else:
            console.info(f"已跳过: {title}")
    console.done("修复完成")


# ================================================================ 下载分发

def _clear_dest(dest: str) -> None:
    if os.path.lexists(dest):
        if not console.ask(f"目标已存在: {dest}, 要覆盖吗?", default=False):
            console.error("已取消")
        import shutil  # 懒加载, 少一次标准库导入

        if os.path.isdir(dest) and not os.path.islink(dest):
            shutil.rmtree(dest)
        else:
            os.remove(dest)


def _read_links(path: str) -> list[str]:
    """从文本文件读取链接 (每行一个, 空行与 # 注释跳过; - 表示标准输入)."""
    try:
        if path == "-":
            text = sys.stdin.read()
        else:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
    except OSError as exc:
        console.error(f"读取链接文件失败: {exc}")
    return [line.strip() for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")]


def _batch_target(url: str, dest: str | None) -> str | None:
    """批量下载时按链接算各自的保存路径 (dest 视为目录)."""
    if not dest:
        return None
    try:
        info = github.parse_url(url)
    except ValueError:
        return os.path.join(dest, "download")
    name = os.path.basename(info["path"]) if info["path"] else info["repo"]
    return os.path.join(dest, name)


def _do_download_many(urls: list[str], dest: str | None, depth: int | None, branch: str,
                      proxy: str | None, no_proxy: bool, **kwargs: object) -> None:
    """一个链接走原路径; 多个链接逐个下载, 单个失败不影响其余, 末尾汇总."""
    if len(urls) == 1:
        _do_download(urls[0], dest, depth, branch, proxy, no_proxy, **kwargs)  # type: ignore[arg-type]
        return
    ok = 0
    failed: list[str] = []
    for index, url in enumerate(urls, 1):
        console.step(f"[{index}/{len(urls)}] {url}")
        try:
            _do_download(url, _batch_target(url, dest), depth, branch, proxy, no_proxy, **kwargs)  # type: ignore[arg-type]
            ok += 1
        except SystemExit:
            failed.append(url)  # console.error 会抛 SystemExit: 记录后继续下一个
    if failed:
        console.error(f"批量下载结束: 成功 {ok} 个, 失败 {len(failed)} 个\n  失败: " + "; ".join(failed))
    console.done(f"批量下载完成: {ok} 个链接全部成功")


def _do_download(url: str, dest: str | None, depth: int | None, branch: str,
                 proxy: str | None, no_proxy: bool, *, list_only: bool = False,
                 assets: list[str] | None = None, source: bool = False,
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
    cfg = config.load()
    console.apply_color(str(cfg.get("color", "auto")))
    console.apply_palette(config.palette_mode())  # 守护进程模式下换成终端自己的配色
    app(list(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    main()
