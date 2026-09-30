"""仓库级操作: 初始化 / 概览 / 撤销提交.

对应命令:
  gitx init  分支 main + 中文友好配置 (core.quotepath=false 等)
  gitx info  状态、与远端领先/落后、最近提交、加速状态
  gitx undo  撤销最近 N 次提交 (soft/mixed/hard)
"""

from __future__ import annotations

import os
import subprocess

from . import config, console, gitcmd


def init_cmd(argv: list[str]) -> None:
    """gitx init [目录] [git init 参数] [--no-zh]."""
    zh = True
    pos: list[str] = []
    extra: list[str] = []
    has_branch_flag = False
    for a in argv:
        if a == "--no-zh":
            zh = False
        elif a in ("-h", "--help"):
            console.info("用法: gitx init [目录] [git init 参数] [--no-zh]\n"
                         "  默认分支 main, 并写入中文友好配置:\n"
                         "    core.quotepath=false       中文文件名不再显示为 \\344\\270\\255\n"
                         "    i18n.commitEncoding=utf-8  提交信息按 UTF-8 记录\n"
                         "    i18n.logOutputEncoding=utf-8  日志按 UTF-8 输出\n"
                         "  原生 git init 用: gitx git init")
            return
        else:
            if a in ("-b", "--initial-branch") or a.startswith("--initial-branch="):
                has_branch_flag = True
            (extra if a.startswith("-") else pos).append(a)
    args = ["git", "init"]
    if not has_branch_flag:
        args.append("--initial-branch=main")
    args += extra + pos
    if subprocess.run(args).returncode != 0:
        console.error("初始化失败")
    target = pos[0] if pos else "."
    console.info(f"仓库: {os.path.abspath(target)}")
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


def info_cmd(argv: list[str]) -> None:
    """gitx info [路径] —— 仓库概览."""
    path = "."
    for a in argv:
        if a in ("-h", "--help"):
            console.info("用法: gitx info [路径]")
            return
        if not a.startswith("-"):
            path = a
    if not gitcmd.is_repo(path):
        console.error(f"{path} 不是 git 仓库")

    _, root = gitcmd.capture(["git", "-C", path, "rev-parse", "--show-toplevel"])
    branch = gitcmd.current_branch(path) or "(尚无提交)"
    console.info(f"仓库: {root or os.path.abspath(path)}  |  分支: {branch}")

    fetch = gitcmd.remote_url("origin", path)
    push = gitcmd.remote_push_url("origin", path)
    if fetch:
        line = f"远端: origin = {fetch}"
        if push and push != fetch:
            line += f"  |  推送: {push}"
        console.info(line)
    else:
        console.warn("远端: 未关联 (用 gitx push to <仓库地址> 关联)")

    staged, modified, untracked, conflicts = gitcmd.status_counts(path)
    console.info(f"状态: 暂存 {staged} | 修改 {modified} | 未跟踪 {untracked} | 冲突 {conflicts}")

    behind, ahead = gitcmd.behind_ahead(path)
    if behind < 0:
        console.info("对比远端: 无上游分支")
    elif not behind and not ahead:
        console.info("对比远端: 与远端一致")
    else:
        console.info(f"对比远端: 领先 {ahead} | 落后 {behind}"
                     + ("   先 gitx pull 再推送" if behind else ""))

    brief = gitcmd.commit_brief("HEAD", path)
    if brief:
        console.info(f"最近提交: {_brief_text('HEAD', path)}")
    else:
        console.warn("最近提交: 还没有提交")

    prefix = config.active_proxy()
    console.info("加速: " + (f"{config.load().get('proxy')} ({prefix}) [拉取加速 / 推送直连]" if prefix else "直连"))

    quotepath = gitcmd.capture(["git", "-C", path, "config", "--get", "core.quotepath"])[1]
    if quotepath not in ("false", "0", "off"):
        console.warn("中文文件名会被转义显示, 建议执行: gitx config zh")


def undo_cmd(argv: list[str]) -> None:
    """gitx undo [次数] [--soft|--mixed|--hard] [-C 路径] [-y]."""
    times = 1
    mode = "soft"
    path = "."
    assume_yes = False

    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--soft", "--mixed", "--hard"):
            mode = a[2:]
        elif a in ("-y", "--yes"):
            assume_yes = True
        elif a in ("-C", "--path") and i + 1 < len(argv):
            i += 1
            path = argv[i]
        elif a in ("-h", "--help"):
            console.info("用法: gitx undo [次数] [--soft|--mixed|--hard] [-C 路径] [-y]\n"
                         "  --soft (默认) 改动保留在暂存区\n"
                         "  --mixed       改动回到工作区(未暂存)\n"
                         "  --hard        丢弃改动 (会询问确认, 可用 -y 跳过)")
            return
        elif a.startswith("-"):
            console.error(f"未知参数: {a}")
        elif a.isdigit():
            times = int(a)
        else:
            path = a
        i += 1

    if not gitcmd.is_repo(path):
        console.error(f"{path} 不是 git 仓库")
    if not gitcmd.has_commits(path):
        console.error("仓库还没有提交, 无需撤销")
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
            if (staged or modified) and not assume_yes:
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