"""暂存相关操作: 列表 / 保存 / 弹出 / 应用 / 删除 / 查看 / 清空.

对应命令:
  gitx stash             暂存列表 (序号 / 时间 / 说明)
  gitx stash save        把当前改动暂存起来 (--untracked 含未跟踪文件)
  gitx stash pop         弹出最近一次暂存并恢复 (恢复后删除该条目)
  gitx stash apply       应用某次暂存但不删除条目
  gitx stash drop        删除某次暂存
  gitx stash show        查看某次暂存的改动概览 (--patch 看具体 diff)
  gitx stash clear       清空全部暂存
"""

from __future__ import annotations

from . import console, gitcmd


_STASH_FMT = "%gd%x00%cr%x00%gs"


def _exists(index: int, path: str = ".") -> bool:
    """暂存条目 index 是否存在 (负数 / 越界都算不存在)."""
    if index < 0:
        return False
    rc, out = gitcmd.capture(["git", "-C", path, "stash", "list", "--format=%gd"])
    if rc != 0:
        return False
    return index < len(out.splitlines())


def list_stashes(path: str = ".", limit: int = 20) -> None:
    """gitx stash —— 暂存列表."""
    gitcmd.require_repo(path)
    rc, out = gitcmd.capture(["git", "-C", path, "stash", "list",
                              f"--format={_STASH_FMT}"])
    lines = out.splitlines() if rc == 0 else []
    if not lines:
        console.info("没有暂存的改动")
        return
    table = console.table("序号", "时间", "说明", title=f"暂存 {len(lines)} 条")
    for line in lines[:limit]:
        parts = (line.split("\x00") + ["", "", ""])[:3]
        table.add_row(console.txt(parts[0]), console.txt(parts[1]), console.txt(parts[2]))
    console.print(table)
    console.hint("恢复用 gitx stash pop  (查看详情: gitx stash show [序号])")


def save(message: str = "", *, include_untracked: bool = False, path: str = ".") -> None:
    """gitx stash save —— 把当前改动暂存起来."""
    gitcmd.require_repo(path)
    rc, out = gitcmd.capture(["git", "-C", path, "status", "--porcelain"])
    if rc != 0 or not out:
        console.info("没有需要暂存的改动")
        return
    changed = len([line for line in out.splitlines() if line.strip()])
    note = message or "gitx 暂存"
    args = ["git", "-C", path, "stash", "push", "-m", note]
    if include_untracked:
        args.append("-u")
    rc, out = gitcmd.run_capture(args)
    if rc != 0:
        console.error(f"暂存失败: {out}" if out else "暂存失败")
    detail = f"已暂存改动: {note} (共 {changed} 处)"
    if include_untracked:
        detail += " [含未跟踪文件]"
    console.done(detail)
    console.hint("恢复用 gitx stash pop  (查看列表: gitx stash list)")


def pop(index: int = 0, path: str = ".") -> None:
    """gitx stash pop —— 弹出暂存并恢复, 成功后删除该条目."""
    _restore("pop", index, path)


def apply(index: int = 0, path: str = ".") -> None:
    """gitx stash apply —— 应用暂存, 保留条目."""
    _restore("apply", index, path)


def _restore(action: str, index: int, path: str = ".") -> None:
    gitcmd.require_repo(path)
    if not _exists(index, path):
        console.error(f"没有 stash@{{{index}}} (查看列表: gitx stash list)")
    rc, out = gitcmd.run_capture(["git", "-C", path, "stash", action, f"stash@{{{index}}}"])
    if rc != 0:
        console.error(f"恢复 stash@{{{index}}} 失败: {out}\n"
                      f"  可能有冲突, 解决后 gitx stash drop {index}\n"
                      f"  查看内容: gitx stash show -p stash@{{{index}}}")
    label = "已弹出并恢复" if action == "pop" else "已应用"
    console.done(f"{label}: stash@{{{index}}}")
    if action != "pop":
        console.hint(f"不再需要可删除: gitx stash drop {index}")


def drop(index: int = 0, *, yes: bool = False, path: str = ".") -> None:
    """gitx stash drop —— 删除某次暂存."""
    gitcmd.require_repo(path)
    if not _exists(index, path):
        console.error(f"没有 stash@{{{index}}} (查看列表: gitx stash list)")
    if not yes and not console.ask(f"删除 stash@{{{index}}}?", default=False):
        console.error("已取消")
    rc, out = gitcmd.run_capture(["git", "-C", path, "stash", "drop", f"stash@{{{index}}}"])
    if rc != 0:
        console.error(f"删除失败: {out}" if out else f"删除 stash@{{{index}}} 失败")
    console.done(f"已删除: stash@{{{index}}}")


def show(index: int = 0, *, patch: bool = False, path: str = ".") -> None:
    """gitx stash show —— 查看某次暂存的概览 (--patch 看具体 diff)."""
    gitcmd.require_repo(path)
    if not _exists(index, path):
        console.error(f"没有 stash@{{{index}}} (查看列表: gitx stash list)")
    if patch:
        rc, out = gitcmd.capture(["git", "-C", path, "stash", "show", "-p", "--color=never",
                                  f"stash@{{{index}}}"])
        if rc != 0 or not out:
            console.info(f"stash@{{{index}}} 没有可显示的改动")
            return
        from rich.syntax import Syntax
        console.print(Syntax(out, "diff", line_numbers=False))
        return
    rc, out = gitcmd.capture(["git", "-C", path, "stash", "show", "--stat",
                              f"stash@{{{index}}}"])
    if rc != 0 or not out:
        console.info(f"stash@{{{index}}} 没有可显示的改动")
        return
    console.print(console.txt(out))


def clear(*, yes: bool = False, path: str = ".") -> None:
    """gitx stash clear —— 清空全部暂存."""
    gitcmd.require_repo(path)
    if not _exists(0, path):
        console.info("没有暂存的改动")
        return
    if not yes and not console.ask("清空全部暂存?", default=False):
        console.error("已取消")
    rc, out = gitcmd.run_capture(["git", "-C", path, "stash", "clear"])
    if rc != 0:
        console.error(f"清空失败: {out}" if out else "清空暂存失败")
    console.done("已清空全部暂存")