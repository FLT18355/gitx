"""标签相关操作: 列表 / 新建 / 删除 / 推送.

对应命令:
  gitx tag               标签表: 标签 / 类型 / 时间 / 提交 / 说明
  gitx tag new           新建标签 (--annotated 附注标签, 可带 -m 说明)
  gitx tag delete        删除标签 (--remote 删远端, --yes 免确认)
  gitx tag push          推送标签 (缺省推送全部, 也可指定标签名)
"""

from __future__ import annotations

from typing import Sequence

from . import console, gitcmd


_TAG_FMT = "%00".join((
    "%(refname:short)", "%(objecttype)", "%(creatordate:relative)",
    "%(*objectname:short)", "%(objectname:short)", "%(subject)",
))


def _tag_exists(name: str, path: str = ".") -> bool:
    return gitcmd.capture(["git", "-C", path, "rev-parse", "-q", "--verify",
                           f"refs/tags/{name}"])[0] == 0


def list_tags(path: str = ".", *, pattern: str = "", limit: int = 30) -> None:
    """gitx tag —— 标签列表."""
    gitcmd.require_repo(path)
    args = ["git", "-C", path, "for-each-ref",
            "--sort=-creatordate", f"--format={_TAG_FMT}",
            f"refs/tags/{pattern}*" if pattern else "refs/tags"]
    rc, out = gitcmd.capture(args)
    lines = out.splitlines() if rc == 0 else []
    if not lines:
        console.info("还没有标签 (创建: gitx tag new v1.0.0)")
        return
    table = console.table("标签", "类型", "时间", "提交", "说明",
                          title=f"标签 {len(lines)} 个")
    for line in lines[:limit]:
        parts = (line.split("\x00") + [""] * 6)[:6]
        name, objtype, date, peeled, objname, subject = parts
        kind = console.styled("[ok]附注[/ok]") if objtype == "tag" else console.txt("轻量")
        commit = peeled or objname
        table.add_row(console.txt(name), kind, console.txt(date),
                      console.txt(commit), console.txt(subject))
    console.print(table)
    console.hint("推送: gitx tag push <标签>   |   删除: gitx tag delete <标签>")


def create(name: str, message: str = "", *, annotated: bool = False,
           path: str = ".") -> None:
    """gitx tag new —— 新建标签."""
    gitcmd.require_repo(path)
    if not name:
        console.error("用法: gitx tag new <名称> [-m 说明] [--annotated]")
    if _tag_exists(name, path):
        console.error(f"标签已存在: {name} (删除: gitx tag delete {name})")
    if message or annotated:
        note = message or name
        args = ["git", "-C", path, "tag", "-a", name, "-m", note]
    else:
        args = ["git", "-C", path, "tag", name]
    rc, out = gitcmd.run_capture(args)
    if rc != 0:
        console.error(f"新建标签失败: {out}" if out else f"新建标签失败: {name}")
    kind = "附注标签" if (message or annotated) else "轻量标签"
    console.done(f"已新建{kind}: {name}")
    console.hint(f"推送: gitx tag push {name}")


def delete(names: Sequence[str], *, remote: bool = False, yes: bool = False,
           path: str = ".") -> None:
    """gitx tag delete —— 删除标签 (本地或远端 origin)."""
    gitcmd.require_repo(path)
    if not names:
        console.error("用法: gitx tag delete <标签...> [--remote] [--yes]")
    if remote and not gitcmd.remote_url("origin", path):
        console.error("没有 origin 远程 (gitx push to <仓库地址> 关联)")

    existing = []
    for name in names:
        if _tag_exists(name, path):
            existing.append(name)
        else:
            console.warn(f"没有标签: {name}")
    if not existing:
        console.info("没有可删除的标签")
        return

    if not yes and not console.ask(
            f"删除 {len(existing)} 个{'远端' if remote else ''}标签: {', '.join(existing)}?",
            default=False):
        console.error("已取消")

    if remote:
        rc, out = gitcmd.refspec_push(path, "origin", delete_refs=existing)
        if rc != 0:
            console.error(f"删除远端标签失败: {out}" if out else "删除远端标签失败")
        console.done(f"已删除远端标签 {len(existing)} 个: {', '.join(existing)}")
        return

    removed = 0
    for name in existing:
        if gitcmd.ok(["git", "-C", path, "tag", "-d", name]):
            removed += 1
        else:
            console.warn(f"删除标签失败: {name}")
    console.done(f"已删除本地标签 {removed} 个: {', '.join(existing)}")


def push(names: Sequence[str] = (), *, remote: str = "origin", path: str = ".") -> None:
    """gitx tag push —— 推送标签 (缺省全部)."""
    gitcmd.require_repo(path)
    if not remote or not gitcmd.remote_url(remote, path):
        console.error(f"没有 {remote or 'origin'} 远程 (gitx push to <仓库地址> 关联)")
    if names:
        missing = [name for name in names if not _tag_exists(name, path)]
        for name in missing:
            console.warn(f"没有标签: {name}")
        valid = [name for name in names if name not in missing]
        if not valid:
            console.error("没有可推送的标签")
        rc, out = gitcmd.refspec_push(path, remote, refs=[f"refs/tags/{n}" for n in valid])
        label = ", ".join(valid)
    else:
        rc, out = gitcmd.refspec_push(path, remote, tags_all=True)
        label = "全部标签"
    if rc != 0:
        console.error(f"推送标签失败: {out}\n"
                      f"  推送直连, 请检查网络或 gitx doctor")
    console.done(f"已推送 {label} 到 {remote}")