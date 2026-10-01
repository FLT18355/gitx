"""gitx 命令行入口: 用 Typer + Rich 构建的分组式 CLI.

命令分组:
  下载 (download / clone / release)   同步 (push / pull / sync)
  仓库 (init / info / undo)           加速 (proxy ...)   配置 (config ... / doctor)
其它 git 子命令直接透传 (gitx status / gitx log --oneline)。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import urllib.request
from typing import Annotated, Optional

import typer

from . import __version__, accel, config, console, download, gitcmd, github, release, repo, sync

PANEL_DL = "下载 (默认加速)"
PANEL_SYNC = "同步"
PANEL_REPO = "仓库"
PANEL_PROXY = "加速管理"
PANEL_CONF = "配置与自检"

_HELP = f"""[key]gitx[/key] -- 给中国人用的 GitHub 加速与同步工具 [dim]v{__version__}[/dim]

拉取 (克隆 / 文件 / Release 附件 / API) 默认走加速镜像 [num]{accel.PROVIDERS['v6']}[/num], 推送直连 GitHub。
直接给一个 GitHub 链接即可下载: [key]gitx https://github.com/owner/repo[/key]
其它 git 子命令会原样透传: [key]gitx status[/key] / [key]gitx log --oneline[/key]"""

_EPILOG = """[key]示例[/key]
  gitx https://github.com/owner/repo                下载仓库 -> ./repo
  gitx https://github.com/owner/repo/tree/main/src  只下载某个文件夹
  gitx release cli/cli --list                       看最新发布的附件清单
  gitx release cli/cli --asset '*linux_amd64*'      只下匹配的附件
  gitx proxy auto                                   自动测速并选用最快加速源

环境变量 [num]GITX_PROXY[/num] = off | v6 | gh-proxy | https://... 可设置全局默认加速源。"""

app = typer.Typer(
    name="gitx",
    help=_HELP,
    epilog=_EPILOG,
    rich_markup_mode="rich",
    no_args_is_help=True,
    add_completion=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"[key]gitx[/key] {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: Annotated[bool, typer.Option("--version", "-V", callback=_version_callback,
                                          is_eager=True, help="显示版本并退出")] = False,
) -> None:
    # 无子命令时由 no_args_is_help 显示帮助
    del version


# ================================================================ 下载

@app.command("download", rich_help_panel=PANEL_DL)
def download_cmd(
    url: Annotated[str, typer.Argument(metavar="URL", help="GitHub 链接: 仓库 / tree / blob / releases")],
    dest: Annotated[Optional[str], typer.Argument(metavar="目标路径", help="保存位置, 默认用仓库名")] = None,
    branch: Annotated[str, typer.Option("--branch", "-b", help="指定分支")] = "",
    depth: Annotated[Optional[int], typer.Option("--depth", "-d", help="克隆深度, 0 = 完整克隆")] = None,
    list_only: Annotated[bool, typer.Option("--list", "-l", help="仅列出附件 (发布页链接)")] = False,
    limit: Annotated[int, typer.Option("--limit", "-n", help="发布列表条数 (发布页链接挑选发布用, 最多 100)")] = release.DEFAULT_LIMIT,
    assets: Annotated[Optional[list[str]], typer.Option("--asset", "-a", help="仅下载匹配的附件, 可重复")] = None,
    source: Annotated[bool, typer.Option("--source", help="额外下载源码包 (发布页链接)")] = False,
    proxy: Annotated[Optional[str], typer.Option("--proxy", help="本次使用的加速源: v6 / gh-proxy / https://...")] = None,
    no_proxy: Annotated[bool, typer.Option("--no-proxy", help="本次直连, 不走加速")] = False,
) -> None:
    """下载仓库 / 文件夹 / 单个文件 / Release 附件, [info]默认走加速[/info]."""
    _do_download(url, dest, depth, branch, proxy, no_proxy,
                 list_only=list_only, assets=assets, source=source, limit=limit)


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
    proxy: Annotated[Optional[str], typer.Option("--proxy", help="本次使用的加速源: v6 / gh-proxy / https://...")] = None,
    no_proxy: Annotated[bool, typer.Option("--no-proxy", help="本次直连, 不走加速")] = False,
) -> None:
    """通过 GitHub API 列出并下载 Release 附件, [info]默认走加速[/info].

    终端里直接 [key]gitx release owner/repo[/key] 会先让你挑发布 (含预发布), 再挑要下载的附件;
    两处都直接回车 = 最新发布 + 全部附件。给了 [key]--tag[/key] / [key]--asset[/key] 就是非交互模式。
    """
    info = release.parse_target(target)
    prefix = config.active_proxy(proxy, no_proxy)
    release.run(info, output, prefix, tag=tag, assets=tuple(assets or ()),
                list_only=list_only, tags=tags, pick=pick, source=source, limit=limit)


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
    sync.do_sync(path=path, message=message or " ".join(words or []), force=force,
                 no_proxy=no_proxy, rebase=not merge)


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


# ================================================================ 加速管理

proxy_app = typer.Typer(help="加速管理: 拉取走加速, 推送直连", rich_markup_mode="rich",
                        invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})


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
    source: Annotated[str, typer.Argument(metavar="加速源", help="v6 / gh-proxy / https://...")] = "v6",
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
    source: Annotated[str, typer.Argument(metavar="加速源", help="v6 / gh-proxy / https://...")],
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


def _proxy_status() -> None:
    cfg = config.load()
    name = str(cfg.get("proxy", "v6"))
    try:
        prefix = accel.resolve(name)
    except ValueError:
        prefix = None
    installed = accel.installed_prefix()
    table = console.table("项目", "值", title="加速状态")
    table.add_row("加速源", console.txt(f"{name} ({prefix})" if prefix else f"{name} (直连, 未加速)"))
    table.add_row("insteadOf", console.txt(f"{installed} (普通 git 命令也走加速)" if installed
                                           else "未安装 (只影响 gitx 自身)"))
    table.add_row("配置文件", console.txt(str(config.config_path())))
    console.print(table)
    console.info("开启/切换: gitx proxy on | auto 测速 | off 直连 | install 让 git 也走加速")


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
    name = str(cfg.get("proxy", "v6"))
    try:
        prefix = accel.resolve(name)
    except ValueError as exc:
        console.error(str(exc))
    if not prefix:
        console.info("当前为直连模式, 跳过测试 (gitx proxy on 开启加速)")
        return
    console.step(f"测试加速源: {name} ({prefix})")
    table = console.table("端点", "结果", title="连通性")
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

config_app = typer.Typer(help="持久化配置 (~/.config/gitx/config.json)", rich_markup_mode="rich",
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
def config_get(key: Annotated[str, typer.Argument(metavar="键", help="proxy / depth / branch / message")]) -> None:
    """查看单个配置项."""
    console.info(f"{key} = {config.load().get(key, '')}")


@config_app.command("set")
def config_set(
    key: Annotated[str, typer.Argument(metavar="键", help="proxy / depth / branch / message")],
    value: Annotated[str, typer.Argument(metavar="值")],
) -> None:
    """修改配置项."""
    if key not in config.DEFAULTS:
        console.error(f"未知配置键: {key} (可用: {', '.join(config.DEFAULTS)})")
    if key == "proxy":
        accel.resolve(value)
    if key == "depth":
        try:
            int(value)
        except ValueError:
            console.error("depth 必须是整数")
    config.save({**config.load(), key: value})
    console.done(f"{key} = {value}")


@config_app.command("reset")
def config_reset() -> None:
    """恢复默认配置."""
    config.save(dict(config.DEFAULTS))
    console.done("配置已重置为默认")


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


def _config_list() -> None:
    table = console.table("键", "值", title="gitx 配置")
    for key, value in config.load().items():
        table.add_row(console.txt(key), console.txt(value))
    console.print(table)
    console.info(f"配置文件: {config.config_path()}")


@app.command(rich_help_panel=PANEL_CONF)
def doctor() -> None:
    """环境自检: git / gh / 仓库 / 加速源 / 编码."""
    table = console.table("项目", "状态", title=f"gitx {__version__} 环境自检")
    table.add_row("配置文件", console.txt(config.config_path()))
    _, gitver = gitcmd.capture(["git", "--version"])
    table.add_row("git", console.txt(gitver or "未找到"))
    gh = shutil.which("gh")
    state = ("已登录" if gitcmd.capture(["gh", "auth", "status"])[0] == 0 else "未登录") if gh else "未安装"
    table.add_row("gh", console.txt(state))
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


# ================================================================ 透传与分发

_GIT_CMDS: set[str] | None = None

_SUBCOMMANDS = {"download", "clone", "release", "push", "pull", "sync",
                "init", "info", "undo", "proxy", "config", "doctor", "git"}


def _git_commands() -> set[str]:
    global _GIT_CMDS
    if _GIT_CMDS is None:
        cmds: set[str] = set()
        rc, out = gitcmd.capture(["git", "help", "-a"])
        if rc == 0:
            for line in out.splitlines():
                for tok in re.split(r"\s+", line.strip()):
                    if tok and not tok.startswith(("-", "(", "'")):
                        cmds.add(tok)
        _GIT_CMDS = cmds
    return _GIT_CMDS


def _is_git_command(name: str) -> bool:
    if not name or name.startswith("-"):
        return False
    return name in _git_commands()


def _passthrough(argv: list[str]) -> None:
    raise SystemExit(subprocess.run(["git", *argv]).returncode)


def _clear_dest(dest: str) -> None:
    if os.path.lexists(dest):
        if not console.ask(f"目标已存在: {dest}, 要覆盖吗?", default=False):
            console.error("已取消")
        if os.path.isdir(dest) and not os.path.islink(dest):
            shutil.rmtree(dest)
        else:
            os.remove(dest)


def _do_download(url: str, dest: Optional[str], depth: Optional[int], branch: str,
                 proxy: Optional[str], no_proxy: bool, *, list_only: bool = False,
                 assets: Optional[list[str]] = None, source: bool = False,
                 limit: int = release.DEFAULT_LIMIT) -> None:
    try:
        info = github.parse_url(url)
    except ValueError as exc:
        console.error(f"{exc}\n提示: 其它 git 子命令可直接透传, 如 gitx status")
    prefix = config.active_proxy(proxy, no_proxy)
    if info["mode"] in ("release", "asset"):
        release.run(info, dest or ".", prefix, assets=tuple(assets or ()),
                    list_only=list_only, source=source, limit=limit)
        return
    item_name = os.path.basename(info["path"]) if info["path"] else info["repo"]
    target = dest or item_name
    _clear_dest(target)
    if depth is None:
        depth = int(config.load().get("depth", 1))
    download.download(url, target, prefix, depth, branch)
    console.done(f"完成! 已保存到: {target}")


def main(argv: list[str] | None = None) -> None:
    """入口: 先分流"git 透传 / GitHub 链接直下", 其余交给 typer 子命令."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        first = argv[0]
        if first in ("-h", "--help", "help"):
            argv = []
        elif first in ("-V", "--version"):
            pass  # 交给 typer 的 --version
        elif first == "git":
            _passthrough(argv[1:])
        elif first not in _SUBCOMMANDS:
            if _is_git_command(first):
                _passthrough(argv)
            argv = ["download", *argv]
    app(argv)


if __name__ == "__main__":
    main()