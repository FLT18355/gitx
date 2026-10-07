"""分支相关操作: 列表 / 新建 / 切换 / 重命名 / 删除 / 上游 / 合并 / 变基 / 更新引用.

对应命令:
  gitx branch            分支表: 上游 / 领先落后 / 最近提交 (含远端跟踪)
  gitx branch new        新建分支 (--from <起点>, --switch 建完即切换)
  gitx branch rename     重命名分支 (缺省改当前分支)
  gitx branch delete     删除本地分支 (--remote 删远端, --force 强删)
  gitx branch upstream   查看 / 设置 / 取消上游分支
  gitx switch            切换分支 (--create 新建)
  gitx merge             合并分支 (冲突时给出解决/放弃提示)
  gitx rebase            变基 (冲突时给出继续/跳过/放弃提示)
  gitx fetch             更新远端跟踪引用 (走加速, --prune 清理已删除的远端分支)
"""

from __future__ import annotations

import subprocess

from . import config, console, gitcmd


# ---------------------------------------------------------------- 内部助手

def _head_text(path: str = ".") -> str:
    brief = gitcmd.commit_brief("HEAD", path)
    if not brief:
        return "(尚无提交)"
    parts = (brief.split("|", 3) + ["", "", "", ""])[:4]
    return f"{parts[0]} ({parts[1]}, {parts[2]}) {parts[3]}"


def _tracking_exists(name: str, path: str = ".") -> bool:
    """本地是否已有同名远端跟踪分支 (离线判断, 不发起网络请求)."""
    _, out = gitcmd.capture(["git", "-C", path, "for-each-ref", "--format=%(refname:short)",
                             f"refs/remotes/*/{name}"])
    return bool(out)


def _conflict_count(path: str = ".") -> int:
    return gitcmd.status_counts(path)[3]


# ---------------------------------------------------------------- 列表

def list_branches(path: str = ".", *, include_remote: bool = False, limit: int = 20) -> None:
    """gitx branch —— 分支列表: 上游 / 领先落后 / 最近提交."""
    gitcmd.require_repo(path)
    rows = gitcmd.branches_info(path, include_remote)
    if not rows:
        console.error("还没有分支 (仓库没有提交)")
    table = console.table("", "分支", "上游", "同步", "最近提交", "说明",
                          title=f"分支 {len(rows)} 个" + (" (含远端跟踪)" if include_remote else ""))
    for row in rows[:limit]:
        if row["upstream"]:
            if row["track"] == "[gone]":
                sync = console.styled("[warn]上游已删除[/warn]")
            elif row["ahead"] or row["behind"]:
                sync = console.styled(f"[num]↑{row['ahead']} ↓{row['behind']}[/num]")
            else:
                sync = console.styled("[ok]一致[/ok]")
        else:
            sync = console.txt("未关联")
        table.add_row(
            console.styled("[ok]*[/ok]") if row["head"] else console.txt(""),
            console.txt(row["name"]),
            console.txt(row["upstream"] or "-"),
            sync,
            console.txt(f"{row['sha']} {row['date']}"),
            console.txt(row["subject"][:40]),
        )
    console.print(table)
    console.info("切换: gitx switch <分支>   |   新建: gitx branch new <分支>   |   清理: gitx tidy --prune")


# ---------------------------------------------------------------- 新建 / 切换

def create(name: str, *, start: str = "", switch: bool = False, path: str = ".") -> None:
    """新建分支; start 为空时基于 HEAD, switch=True 时建完立即切换."""
    gitcmd.require_repo(path)
    if not name:
        console.error("用法: gitx branch new <分支名> [--from <起点>] [--switch]")
    if gitcmd.local_branch_exists(name, path):
        console.error(f"分支已存在: {name} (切换: gitx switch {name})")
    args = ["git", "-C", path, "branch", name]
    if start:
        args.append(start)
    rc, out = gitcmd.run_capture(args)
    if rc != 0:
        console.error(f"新建分支失败: {out}" if out else f"新建分支失败: {name}")
    console.done(f"已新建分支: {name}" + (f" (起点 {start})" if start else f" (起点 {_head_text(path)})"))
    if switch:
        do_switch(name, path=path)


def do_switch(name: str, *, create: bool = False, force: bool = False,
              detach: bool = False, path: str = ".") -> None:
    """切换分支 (gitx switch)."""
    gitcmd.require_repo(path)
    if not name:
        console.error("用法: gitx switch <分支> [-c 新建] [-f 强制] [--detach]")
    before = gitcmd.current_branch(path)
    args = ["git", "-C", path, "switch"]
    if create:
        args += ["-c", name]
    else:
        if detach:
            args.append("--detach")
        elif force:
            args.append("--force")
        if name != "-" and not detach and not gitcmd.local_branch_exists(name, path) \
                and not _tracking_exists(name, path):
            console.error(f"没有分支 {name}\n"
                          f"  新建并切换: gitx switch -c {name}\n"
                          f"  切到某次提交: gitx switch --detach {name}   (也可用标签 / 哈希)")
        args.append(name)
    rc, out = gitcmd.run_capture(args)
    if rc != 0:
        if name == "-":
            console.error(f"切换失败: {out}\n提示: 上一个分支可能已被删除, 用 gitx branch 挑一个")
        console.error(f"切换失败: {out}\n提示: 有未提交改动时先 gitx stash, 或加 -f 强制切换")
    now = gitcmd.current_branch(path)
    if create:
        console.done(f"已新建并切换到: {now or name}")
    else:
        console.done(f"已切换: {before or '?'} -> {now or name + ' (游离 HEAD)'}")
    behind, ahead = gitcmd.behind_ahead(path)
    if behind > 0:
        console.warn(f"当前分支落后远端 {behind} 个提交 (gitx pull 拉取)")
    elif ahead > 0:
        console.info(f"当前分支领先远端 {ahead} 个提交 (gitx push 推送)")


def rename(old: str, new: str, *, path: str = ".") -> None:
    """重命名分支 (gitx branch rename)."""
    gitcmd.require_repo(path)
    if not new:
        console.error("用法: gitx branch rename [<旧名>] <新名>")
    label = old or gitcmd.current_branch(path)
    if old and not gitcmd.local_branch_exists(old, path):
        console.error(f"没有分支: {old}")
    if gitcmd.local_branch_exists(new, path):
        console.error(f"分支已存在: {new}")
    args = ["git", "-C", path, "branch", "-m"]
    if old:
        args.append(old)
    args.append(new)
    rc, out = gitcmd.run_capture(args)
    if rc != 0:
        console.error(f"重命名失败: {out}" if out else "重命名失败")
    console.done(f"已重命名: {label} -> {new}")


# ---------------------------------------------------------------- 删除 / 上游

def delete(names: list[str], *, force: bool = False, remote: bool = False,
           yes: bool = False, path: str = ".") -> None:
    """删除分支 (gitx branch delete): 本地默认 -d, --force 用 -D; --remote 删 origin 上的."""
    gitcmd.require_repo(path)
    if not names:
        console.error("用法: gitx branch delete <分支...> [--force] [--remote]")

    if remote:
        if not gitcmd.remote_url("origin", path):
            console.error("没有 origin 远程 (gitx push to <仓库地址> 关联)")
        prefix = config.active_proxy()
        for name in names:
            if not gitcmd.remote_branch_exists("origin", name, path, prefix):
                console.warn(f"远端没有分支: origin/{name}")
                continue
            console.step(f"删除远端分支 origin/{name}...")
            rc, out = gitcmd.delete_remote_ref(path, "origin", f"refs/heads/{name}")
            if rc != 0:
                console.error(f"删除失败: origin/{name} (受保护分支或网络问题)\n{out}")
            console.done(f"已删除远端分支: origin/{name}")
        return

    current = gitcmd.current_branch(path)
    if current in names:
        console.error(f"不能删除当前分支: {current} (先 gitx switch 到别的分支)")
    if force and not yes and not console.ask(
            f"-D 会强制删除 {len(names)} 个分支 (未合并的提交将丢失), 继续?", default=False):
        console.error("已取消")
    for name in names:
        if not gitcmd.local_branch_exists(name, path):
            console.warn(f"没有分支: {name}")
            continue
        if gitcmd.delete_branch(name, path, force=force):
            console.done(f"已删除分支: {name}")
        else:
            console.warn(f"分支 {name} 尚未合并, 未删除 (确认无误: gitx branch delete {name} --force)")


def upstream(branch: str = "", *, set_to: str = "", unset: bool = False, path: str = ".") -> None:
    """查看 / 设置 / 取消上游分支 (gitx branch upstream)."""
    gitcmd.require_repo(path)
    target = branch or gitcmd.current_branch(path)
    if not target:
        console.error("无法确定分支 (仓库还没有提交)")
    if not gitcmd.local_branch_exists(target, path):
        console.error(f"没有分支: {target}")

    if unset:
        if not gitcmd.ok(["git", "-C", path, "branch", "--unset-upstream", target]):
            console.error(f"{target} 没有上游分支")
        console.done(f"已取消 {target} 的上游关联")
        return

    if set_to:
        rc, out = gitcmd.run_capture(["git", "-C", path, "branch",
                                      f"--set-upstream-to={set_to}", target])
        if rc != 0:
            console.error(f"设置上游失败: {out}\n提示: 先 gitx fetch 同步远端分支, 或检查名字")
        console.done(f"{target} 的上游已设为: {set_to}")
        return

    current = gitcmd.upstream_of(target, path)
    if not current:
        console.info(f"{target} 未关联上游")
        console.hint(f"设置: gitx branch upstream {target} --set origin/{target}")
        return
    behind, ahead = gitcmd.diverge(current, target, path)
    if behind < 0:
        sync = "?"
    elif not behind and not ahead:
        sync = "与上游一致"
    else:
        sync = f"领先 {ahead} | 落后 {behind}"
    console.info(f"{target} -> {current}   ({sync})")


# ---------------------------------------------------------------- 合并 / 变基

def merge(branch: str, *, no_ff: bool = False, squash: bool = False,
          abort: bool = False, continue_: bool = False, path: str = ".") -> None:
    """合并分支到当前分支 (gitx merge); 冲突时给出继续/放弃的提示."""
    gitcmd.require_commits(path)
    if abort or continue_:
        flag = "--abort" if abort else "--continue"
        rc, out = gitcmd.run_capture(["git", "-C", path, "merge", flag])
        if rc != 0:
            console.error(f"merge {flag} 失败: {out}\n提示: 只有在合并冲突未解决时才需要 {flag}")
        console.done("已中止合并, 恢复到合并前状态" if abort else "合并已提交")
        return

    if not branch:
        console.error("用法: gitx merge <分支> [--no-ff] [--squash] [--abort]")
    if not (gitcmd.local_branch_exists(branch, path) or _tracking_exists(branch, path)
            or gitcmd.resolve_sha(branch, path)):
        console.error(f"没有分支或提交: {branch} (先 gitx fetch 更新远端分支)")
    current = gitcmd.current_branch(path)
    staged, modified, _untracked, _conflicts = gitcmd.status_counts(path)
    if staged or modified:
        console.warn(f"工作区有 {staged + modified} 个未提交改动, 合并可能被拒 (先 gitx commit 或 gitx stash)")

    args = ["git", "-C", path, "merge"]
    if no_ff:
        args.append("--no-ff")
    if squash:
        args.append("--squash")
    args.append(branch)
    console.step(f"合并 {branch} 到 {current}...")
    # 合并前 git 会自己 `git stash create` 存一份快照 (merge.c 的 save_state); 索引里有
    # "mtime/大小变了、内容没变" 的条目时, 这次快照会静默失败, 合并随即报"储藏失败"而中止。
    # 先刷新索引 (纯 stat 变化回到干净), 万一还是踩到就再刷新重试 —— 此时 git 还没动过
    # 索引 / 工作区 / HEAD, 重试是安全的。
    attempts = 3
    for attempt in range(attempts):
        gitcmd.refresh_index(path)
        rc, out = gitcmd.run_capture(args)
        if rc == 0 or not gitcmd.is_stash_failure(out):
            break
        if attempt < attempts - 1:
            console.warn(f"git 存合并快照失败 (储藏失败): 有文件在合并瞬间被改写, 刷新索引后重试"
                         f" ({attempt + 2}/{attempts})")
    if rc != 0:
        conflicts = _conflict_count(path)
        if conflicts:
            console.error(f"合并产生 {conflicts} 个冲突文件\n"
                          "  解决冲突后: gitx commit -m '合并'   (或原生 git add 后再 gitx commit)\n"
                          "  放弃合并: gitx merge --abort")
        if gitcmd.is_stash_failure(out):
            console.error("合并失败: " + out + "\n"
                          "  原因: git 合并前用 `git stash create` 存快照, 只要索引里有\"mtime 变了、"
                          "内容没变\"的条目 (别的程序在同时改写跟踪文件) 它就会静默失败\n"
                          f"  已自动刷新索引并重试 {attempts} 次; 仍失败就先 gitx stash 再合并")
        console.error(f"合并失败: {out}")
    if squash:
        console.done(f"已把 {branch} 的改动合并进暂存区 (下一步: gitx commit -m '...')")
    else:
        console.done(f"已合并 {branch} 到 {current}")
        console.info(f"现在 HEAD: {_head_text(path)}")


def rebase(onto: str = "", *, interactive: bool = False, abort: bool = False,
           continue_: bool = False, skip: bool = False, path: str = ".") -> None:
    """变基 (gitx rebase): 冲突时给出继续/跳过/放弃的提示."""
    gitcmd.require_commits(path)
    flag = "--abort" if abort else "--continue" if continue_ else "--skip" if skip else ""
    if flag:
        rc, out = gitcmd.run_capture(["git", "-C", path, "rebase", flag])
        if rc != 0:
            console.error(f"变基 {flag} 失败: {out}\n提示: 只有在变基冲突未解决时才需要 {flag}")
        console.done(f"变基 {flag} 完成")
        return

    if not onto:
        console.error("用法: gitx rebase <目标> [--interactive] [--continue|--abort|--skip]")
    current = gitcmd.current_branch(path)
    console.step(f"把 {current} 变基到 {onto}...")
    if interactive:
        # -i 会打开编辑器, 必须继承终端 (不能捕获输出)
        rc = subprocess_run(["git", "-C", path, "rebase", "--interactive", onto])
        if rc != 0:
            console.error("交互式变基未完成 (可 gitx rebase --abort 放弃)")
        console.done("交互式变基完成")
        return

    rc, out = gitcmd.run_capture(["git", "-C", path, "rebase", onto])
    if rc != 0:
        conflicts = _conflict_count(path)
        if conflicts:
            console.error(f"变基产生 {conflicts} 个冲突文件\n"
                          "  解决后: gitx rebase --continue   (或 git add 后执行)\n"
                          "  跳过本次: gitx rebase --skip      放弃: gitx rebase --abort")
        console.error(f"变基失败: {out}")
    console.done(f"已把 {current} 变基到 {onto}")
    console.info(f"现在 HEAD: {_head_text(path)}")


def subprocess_run(args: list[str]) -> int:
    """继承终端的运行 (交互式命令如 rebase -i 需要真终端)."""
    try:
        return subprocess.run(args).returncode
    except FileNotFoundError:
        console.error("未找到 git")


# ---------------------------------------------------------------- 更新引用

def fetch(path: str = ".", *, prune: bool = False, all_remotes: bool = False,
          tags: bool = False, no_proxy: bool = False) -> None:
    """gitx fetch —— 更新远端跟踪引用 (走加速)."""
    gitcmd.require_repo(path)
    if not gitcmd.remote_names(path):
        console.error("没有远程仓库 (gitx push to <仓库地址> 关联)")
    prefix = config.active_proxy(no_proxy=no_proxy)
    console.step("正在更新远端引用..." + (" [加速]" if prefix else ""))
    if not gitcmd.fetch_remote(path, prefix=prefix, prune=prune,
                               all_remotes=all_remotes, tags=tags):
        console.error("更新失败 (可尝试 --no-proxy 直连)")
    console.done("远端引用已更新" + (" (已清理远端删除的分支)" if prune else ""))
    behind, ahead = gitcmd.behind_ahead(path)
    if behind > 0:
        console.info(f"当前分支落后远端 {behind} 个提交 (gitx pull 拉取)")
    elif ahead > 0:
        console.info(f"当前分支领先远端 {ahead} 个提交")