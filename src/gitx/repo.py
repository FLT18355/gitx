"""仓库级操作: 初始化 / 概览 / 撤销 / 提交图 / 维护 / 远端地址 / 日常提交与改动.

对应命令:
  gitx init      分支 main + 中文友好配置 (core.quotepath=false 等)
  gitx info      状态、与远端领先/落后、最近提交、加速状态
  gitx undo      撤销最近 N 次提交 (soft/mixed/hard)
  gitx graph     提交历史 (git log --graph 上色版)
  gitx tidy      仓库体积 / 已合并分支 / 打包瘦身
  gitx url       查看或切换 origin 的地址形态 (accel / https / ssh)
  gitx commit    提交改动 (--amend 修订上次提交)
  gitx diff      查看改动 diff (上色渲染, --staged / --stat)
  gitx discard   丢弃工作区(或暂存区)改动
  gitx clean     删除未跟踪文件

分支相关命令见 branch.py。
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Sequence

from rich.text import Text

from . import accel, config, console, gitcmd, github


def init(args: list[str], zh: bool = True) -> None:
    """gitx init [目录] [git init 参数] [--no-zh]."""
    pos: list[str] = []
    extra: list[str] = []
    has_branch = False
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-b", "--initial-branch"):
            has_branch = True
            extra.append(a)
            if i + 1 < len(args):
                i += 1
                extra.append(args[i])
        elif a.startswith("--initial-branch="):
            has_branch = True
            extra.append(a)
        elif a.startswith("-"):
            extra.append(a)
        else:
            pos.append(a)
        i += 1

    command = ["git", "init"]
    if not has_branch:
        command.append("--initial-branch=main")
    command += extra + pos
    target = pos[0] if pos else "."
    if subprocess.run(command).returncode != 0:
        console.error("初始化失败")
    console.done(f"仓库: {os.path.abspath(target)}")
    if zh:
        changed = gitcmd.apply_zh_config("--local", target)
        console.done("中文友好配置: " + (", ".join(changed) if changed else "已是最新"))
    branch = gitcmd.current_branch(target) or "main"
    console.info(f"分支: {branch}  |  下一步: gitx push to <仓库地址> 关联远程并推送")


def _brief_text(ref: str, path: str = ".") -> str:
    """把 '短哈希|时间|作者|说明' 格式化成一行中文摘要."""
    brief = gitcmd.commit_brief(ref, path)
    if not brief:
        return "(尚无提交)"
    parts = (brief.split("|", 3) + ["", "", "", ""])[:4]
    return f"{parts[0]} ({parts[1]}, {parts[2]}) {parts[3]}"


def info(path: str = ".") -> None:
    """gitx info [路径] —— 仓库概览."""
    gitcmd.require_repo(path)

    _, root = gitcmd.capture(["git", "-C", path, "rev-parse", "--show-toplevel"])
    branch = gitcmd.current_branch(path) or "(尚无提交)"
    fetch = gitcmd.remote_url("origin", path)
    push = gitcmd.remote_push_url("origin", path)
    if fetch:
        remote = fetch + (f"  (推送: {push})" if push and push != fetch else "")
    else:
        remote = "未关联 (用 gitx push to <仓库地址> 关联)"

    staged, modified, untracked, conflicts = gitcmd.status_counts(path)
    behind, ahead = gitcmd.behind_ahead(path)
    if behind < 0:
        track = "无上游分支"
    elif not behind and not ahead:
        track = "与远端一致"
    else:
        track = f"领先 {ahead} | 落后 {behind}" + ("   先 gitx pull 再推送" if behind else "")

    cfg = config.load()
    prefix = config.active_proxy(cfg=cfg)
    speed = (f"{cfg.get('proxy')} ({prefix}) [拉取加速 / 推送直连]"
             if prefix else "直连")
    rel_raw = config.release_source(cfg)
    if rel_raw:
        rel_prefix = config.active_proxy(release=True, cfg=cfg)
        speed += f" | Release: {rel_raw} ({rel_prefix})" if rel_prefix else f" | Release: {rel_raw} (直连)"

    repo_table = console.table("项目", "值", title="仓库")
    repo_table.add_row("路径", console.txt(root or os.path.abspath(path)))
    repo_table.add_row("分支", console.txt(branch))
    repo_table.add_row("远端", console.txt(remote))
    repo_table.add_row("状态", console.txt(f"暂存 {staged} | 修改 {modified} | "
                                          f"未跟踪 {untracked} | 冲突 {conflicts}"))
    repo_table.add_row("对比远端", console.txt(track))
    repo_table.add_row("最近提交", console.txt(_brief_text("HEAD", path)))
    repo_table.add_row("加速", console.txt(speed))
    console.print(repo_table)

    if not fetch:
        console.warn("远端: 未关联 (用 gitx push to <仓库地址> 关联)")
    if not gitcmd.commit_brief("HEAD", path):
        console.warn("最近提交: 还没有提交")
    quotepath = gitcmd.capture(["git", "-C", path, "config", "--get", "core.quotepath"])[1]
    if quotepath not in ("false", "0", "off"):
        console.warn("中文文件名会被转义显示, 建议执行: gitx config zh")


def undo(times: int = 1, mode: str = "soft", path: str = ".", yes: bool = False) -> None:
    """撤销最近 times 个提交 (soft / mixed / hard)."""
    gitcmd.require_repo(path)
    gitcmd.require_commits(path)
    total = gitcmd.commit_count(path)
    if times < 1 or times > total:
        console.error(f"撤销次数不合法: 仓库共 {total} 个提交, 无法撤销 {times} 个")

    old_sha = gitcmd.resolve_sha("HEAD", path)
    console.info(f"将撤销最近 {times} 个提交 ({mode}), 当前 HEAD: {_brief_text('HEAD', path)}")

    if times == total:
        if mode == "hard":
            console.error("撤销全部提交时无法同时丢弃文件, 请改用 --soft (默认) 或 --mixed")
        if not gitcmd.delete_head(path):
            console.error("撤销失败")
        if mode == "mixed":
            gitcmd.unstage_all(path)
    else:
        if mode == "hard":
            staged, modified, _untracked, _conflicts = gitcmd.status_counts(path)
            if (staged or modified) and not yes:
                if not console.ask(f"--hard 会丢弃 {staged + modified} 个文件的未提交改动, 继续?", default=False):
                    console.error("已取消")
        if not gitcmd.reset(path, mode, f"HEAD~{times}"):
            console.error("撤销失败")

    console.done(f"已撤销最近 {times} 个提交 ({mode})")
    console.info(f"现在 HEAD: {_brief_text('HEAD', path)}")
    staged, modified, untracked, _conflicts = gitcmd.status_counts(path)
    console.info(f"改动: 暂存 {staged} | 工作区修改 {modified} | 未跟踪 {untracked}")
    console.info(f"如需恢复: git reset --hard {old_sha[:7]}   (原提交仍在 reflog 中)")
    _behind, ahead = gitcmd.behind_ahead(path)
    if ahead > 0:
        console.info("提示: 撤销的提交若已推送, 再次推送需要加 -f: gitx push -f")


# ---------------------------------------------------------------- 提交图 (gitx graph)

_GRAPH_RE = re.compile(r"^(?P<graph>[^0-9a-f]*)(?P<hash>[0-9a-f]{7,40})"
                       r"(?P<deco> \([^)]*\))?(?P<rest>.*)$")


def _ref_style(ref: str) -> str:
    if ref.startswith("tag: "):
        return "tag"
    if ref.startswith("HEAD"):
        return "head" if ref == "HEAD" else "branch"
    if "/" in ref:  # origin/main 之类的远端跟踪分支
        return "date"
    return "branch"


def _color_line(line: str) -> Text:
    """给 `git log --graph --oneline` 的一行上色 (图形保留 git 的对齐)."""
    m = _GRAPH_RE.match(line)
    if not m:
        return Text(line, style="graph")
    out = Text()
    out.append(m.group("graph"), style="graph")
    out.append(m.group("hash"), style="hash")
    deco = m.group("deco")
    if deco:
        out.append(" (", style="dim")
        for i, ref in enumerate(deco[2:-1].split(", ")):
            if i:
                out.append(", ", style="dim")
            out.append(ref, style=_ref_style(ref))
        out.append(")", style="dim")
    rest = m.group("rest").strip()
    if rest:
        out.append(" " + rest)
    return out


def graph(limit: int = 15, all_refs: bool = False, path: str = ".") -> None:
    """gitx graph —— 带图形的提交历史 (git log --graph 上色版)."""
    gitcmd.require_repo(path)
    gitcmd.require_commits(path)
    lines = gitcmd.graph_lines(limit, all_refs, path)
    if not lines:
        console.error("没有可显示的提交")
    body = Text()
    for i, line in enumerate(lines):
        if i:
            body.append("\n")
        body.append_text(_color_line(line))
    name = os.path.basename(os.path.abspath(path))
    console.panel(body, title=f"{name} 最近 {len(lines)} 次提交"
                             + (" (全部引用)" if all_refs else ""))
    console.info(f"更多: gitx graph -n 50 | gitx graph --all | gitx log --oneline (原生 git)")


# ---------------------------------------------------------------- 维护 (gitx tidy)

def tidy(path: str = ".", *, prune: bool = False, run_gc: bool = False,
         aggressive: bool = False, yes: bool = False) -> None:
    """gitx tidy —— 仓库体检: 体积 / 已合并分支 / 打包瘦身."""
    gitcmd.require_repo(path)

    size = gitcmd.repo_size(path)
    total = size["loose"] + size["pack"] + size["garbage"]
    table = console.table("项目", "值", title="仓库体积")
    table.add_row("松散对象", console.txt(f"{console.human_size(size['loose'])}"
                                        f" ({size['loose_objects']} 个)"))
    table.add_row("打包对象", console.txt(f"{console.human_size(size['pack'])}"
                                        f" ({size['pack_objects']} 个, {size['packs']} 个包)"))
    table.add_row("垃圾", console.txt(console.human_size(size["garbage"])))
    table.add_row("合计", console.styled(f"[num]{console.human_size(total)}[/num]"))
    console.print(table)

    merged = gitcmd.merged_branches(path)
    if merged:
        console.info(f"已合并分支 {len(merged)} 个: {', '.join(merged[:8])}"
                     + (" …" if len(merged) > 8 else ""))
    else:
        console.info("没有已合并的本地分支")

    if prune:
        if not merged:
            console.warn("没有可清理的分支")
        else:
            if not yes and not console.ask(f"删除这 {len(merged)} 个已合并分支?", default=False):
                console.error("已取消")
            removed = [name for name in merged if gitcmd.delete_branch(name, path)]
            console.done(f"已删除 {len(removed)} 个已合并分支")

    if run_gc:
        console.step("正在打包与清理 (git gc --prune=now)...")
        if not gitcmd.gc(path, aggressive):
            console.error("git gc 失败")
        after = gitcmd.repo_size(path)
        new_total = after["loose"] + after["pack"] + after["garbage"]
        console.done(f"打包完成: {console.human_size(total)} -> {console.human_size(new_total)}")
    else:
        console.info("打包瘦身: gitx tidy --gc   (可选 --aggressive 更彻底但更慢)")


# ---------------------------------------------------------------- 远端地址 (gitx url)

_TRANSPORTS = ("accel", "https", "ssh")


def url(path: str = ".", transport: str = "", remote: str = "origin") -> None:
    """gitx url —— 查看/切换 origin 的地址形态: accel(加速) / https(直连) / ssh."""
    gitcmd.require_repo(path)
    names = gitcmd.remote_names(path)
    if not names:
        console.error("没有配置远程仓库 (gitx push to <仓库地址> 关联)")
    if remote not in names:
        console.error(f"没有名为 {remote} 的远程 (现有: {', '.join(names)})")
    fetch = gitcmd.remote_url(remote, path)
    push = gitcmd.remote_push_url(remote, path) or fetch

    if not transport:
        table = console.table("项目", "值", title=f"远程 {remote}")
        table.add_row("拉取", console.txt(fetch))
        table.add_row("推送", console.txt(push))
        table.add_row("形态", console.styled(_transport_label(fetch, push)))
        console.print(table)
        console.info("切换: gitx url accel (拉取加速) | gitx url https (直连) | gitx url ssh")
        return

    parsed = github.owner_repo(fetch)
    if not parsed:
        console.error(f"远程不是 GitHub 地址, 无法自动切换: {fetch}")
    owner, repo = parsed
    direct = github.repo_clone_url(owner, repo)
    if transport == "ssh":
        target = push_target = f"git@github.com:{owner}/{repo}.git"
    elif transport == "https":
        target = push_target = direct
    else:
        prefix = config.active_proxy()
        if not prefix:
            console.error("当前是直连模式, 先用: gitx proxy on")
        target = accel.wrap(direct, prefix)
        push_target = gitcmd.github_push_url(direct, path)
    if not gitcmd.set_remote_urls(remote, target, push_target, path):
        console.error("切换失败, 请检查远程名与地址")
    console.done(f"{remote} 已切换为 {transport}: 拉取 {target}"
                 + (f"  推送 {push_target}" if push_target != target else ""))


def _transport_label(fetch: str, push: str) -> str:
    """按地址形态给出人话标签."""
    if fetch.startswith("git@"):
        return "[tag]ssh[/tag]"
    if "github.com" not in fetch:
        return "[dim]非 GitHub 远端[/dim]"
    if fetch.startswith("https://github.com/"):
        return "[ok]https 直连[/ok]"
    return f"[num]加速[/num] {push.startswith('git@') and '(推送走 ssh)' or ''}".strip()


# ---------------------------------------------------------------- 提交 (gitx commit)

def commit(message: str = "", *, all_changes: bool = False, amend: bool = False,
           no_edit: bool = False, allow_empty: bool = False, path: str = ".") -> None:
    """gitx commit —— 提交改动 (gitx commit -m '信息' [--all] [--amend])."""
    gitcmd.require_repo(path)
    # 未 amend 时必须有提交信息; amend 可以不带 -m (走编辑器改, 或 --no-edit 沿用原信息)
    if not message and not amend:
        console.error("用法: gitx commit -m '提交信息' [--all] [--amend]")
    staged, _modified, _untracked, _conflicts = gitcmd.status_counts(path)
    if not amend and not allow_empty and not all_changes and staged == 0:
        console.info("没有已暂存的改动 (先 git add <文件>, 或用 -a 提交已跟踪文件的改动)")
        return

    args = ["git", "-C", path, "commit"]
    if all_changes:
        args.append("-a")
    if amend:
        args.append("--amend")
    if no_edit:
        args.append("--no-edit")
    if allow_empty:
        args.append("--allow-empty")
    if message:
        args += ["-m", message]

    if amend and not message and not no_edit:
        # 未给信息的修订要打开编辑器: 继承终端, 不捕获输出
        if subprocess.run(args).returncode != 0:
            console.error("提交失败")
    else:
        rc, out = gitcmd.run_capture(args)
        if rc != 0:
            console.error(out or "提交失败")

    console.done(f"已提交: {message or '修订上次提交'}")
    console.info(f"现在 HEAD: {_brief_text('HEAD', path)}")


# ---------------------------------------------------------------- 查看改动 (gitx diff)

def diff(paths: Sequence[str] = (), *, staged: bool = False, stat: bool = False,
         name_only: bool = False, path: str = ".") -> None:
    """gitx diff [路径...] —— 查看改动 (--staged / --stat / --name-only)."""
    gitcmd.require_repo(path)
    args = ["git", "-C", path, "diff", "--no-ext-diff", "--color=never"]
    if staged:
        args.append("--cached")
    if stat:
        args.append("--stat")
    if name_only:
        args.append("--name-only")
    if paths:
        args.append("--")
        args += list(paths)

    rc, out = gitcmd.run_capture(args)
    if rc != 0:
        console.error(out or "git diff 失败")
    if not out:
        console.info("暂存区与 HEAD 没有差异" if staged else "工作区没有未暂存的改动")
        return
    if stat or name_only:
        console.print(console.txt(out))  # 原样输出, 不做 markup 解析
        return
    from rich.syntax import Syntax  # 延迟导入: 只有渲染 diff 时才需要
    console.print(Syntax(out, "diff", line_numbers=False, word_wrap=False))


# ---------------------------------------------------------------- 丢弃改动 (gitx discard)

def discard(paths: Sequence[str], *, staged: bool = False, yes: bool = False,
            path: str = ".") -> None:
    """gitx discard <路径...> —— 丢弃工作区 (或 --staged 暂存区) 改动."""
    gitcmd.require_repo(path)
    if not paths:
        console.error("用法: gitx discard <路径...> [--staged] [-y]")
    if not staged and not yes:
        if not console.ask(f"将丢弃 {len(paths)} 个路径的未提交改动 (无法恢复), 继续?",
                           default=False):
            console.error("已取消")

    args = ["git", "-C", path, "restore"]
    if staged:
        args.append("--staged")
    args.append("--")
    args += list(paths)

    rc, out = gitcmd.run_capture(args)
    if rc != 0:
        console.error(out or "丢弃失败")
    console.done(f"已丢弃 {len(paths)} 个路径的{'暂存改动' if staged else '改动'}")


# ---------------------------------------------------------------- 清理未跟踪文件 (gitx clean)

def clean(*, directories: bool = False, ignored: bool = False, yes: bool = False,
          path: str = ".") -> None:
    """gitx clean —— 删除未跟踪文件 (--directories 连目录 / --ignored 含忽略项 / --yes 免确认)."""
    gitcmd.require_repo(path)
    flags: list[str] = []
    if directories:
        flags.append("-d")
    if ignored:
        flags.append("-x")

    rc, preview = gitcmd.run_capture(["git", "-C", path, "clean", "-n", *flags])
    if rc != 0:
        console.error(preview or "git clean 失败")
    if not preview:
        console.info("没有可清理的未跟踪文件")
        return
    console.print(console.txt(preview))  # 原样打印预览

    if not yes:
        question = "确认删除以上未跟踪文件?"
        if ignored:
            question = "-x 会连同被 .gitignore 忽略的文件一起删除, 确认删除?"
        if not console.ask(question, default=False):
            console.error("已取消")

    rc, out = gitcmd.run_capture(["git", "-C", path, "clean", "-f", *flags])
    if rc != 0:
        console.error(out or "清理失败")
    console.done("已清理未跟踪文件")