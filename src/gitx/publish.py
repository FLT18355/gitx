"""发行版管理 (发布方): 创建 / 上传附件 / 编辑 / 删除 / 查看 / 列表.

下载 Release 附件仍走 `gitx release`(只读, 走 API + 加速); 本模块负责"发布方"的
操作, 全部交给已安装并登录的 `gh`(https://cli.github.com):
本工具只拼参数、不接触写入令牌, 仓库写权限由 gh 自己的登录态决定。

  gitx publish                    列出发行版 (含草稿 / 预发布)
  gitx publish create <标签> ...   创建发行版并上传附件
  gitx publish upload <标签> ...   给已有发行版补传附件
  gitx publish edit <标签> ...     改标题 / 说明 / 预发布 / 草稿 / 最新
  gitx publish delete <标签>       删除发行版 (可连标签一起删)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

from . import console, gitcmd, github

LIST_FIELDS = "tagName,name,isDraft,isPrerelease,isLatest,createdAt,publishedAt"
# gh release view 的 JSON 字段集与 list 不同 (没有 isLatest)
VIEW_FIELDS = "tagName,name,isDraft,isPrerelease,publishedAt,createdAt,body,url,assets,targetCommitish"


# ---------------------------------------------------------------- 前置检查

def _gh() -> str:
    """已安装且已登录的 gh 路径; 不满足时给中文提示并退出."""
    path = shutil.which("gh")
    if not path:
        console.error("发行版管理需要已安装的 gh CLI (https://cli.github.com)\n"
                      "提示: 安装并 gh auth login 之后重试; 只下载附件用 gitx release, 不需要 gh")
    if gitcmd.capture([path, "auth", "status"])[0] != 0:
        console.error("gh 未登录, 无法管理发行版\n提示: 先执行 gh auth login (写操作需要仓库写权限)")
    return path


def _repo_args(target: str) -> list[str]:
    """--repo 参数: 接受 owner/repo 或 GitHub 链接; 留空表示当前仓库."""
    if not target:
        return []
    if "://" in target or "github.com" in target:
        parsed = github.owner_repo(target)
        if not parsed:
            console.error(f"无法识别仓库: {target} (形如 owner/repo)")
    else:
        try:
            parsed = github.parse_repo(target)
        except ValueError as exc:
            console.error(f"{exc}\n用法: --repo owner/repo")
    return ["--repo", f"{parsed[0]}/{parsed[1]}"]


def _run(gh: str, args: list[str], action: str) -> None:
    """跑一条 gh 命令并透传它自己的输出; 失败时补一句中文提示."""
    if subprocess.run([gh, *args]).returncode != 0:
        console.error(f"{action}失败 (gh 已打印原因)")


def _capture(gh: str, args: list[str]) -> tuple[int, str, str]:
    """跑 gh 并同时拿到 stdout / stderr (gh 的报错都写在 stderr)."""
    try:
        done = subprocess.run([gh, *args], capture_output=True, text=True)
    except FileNotFoundError:
        return 127, "", "未找到 gh"
    return done.returncode, done.stdout or "", (done.stderr or "").strip()


def _json(gh: str, args: list[str], action: str) -> object:
    """跑一条 gh 命令并按 JSON 解析输出."""
    code, out, err = _capture(gh, args)
    if code != 0:
        console.error(f"{action}失败\n{err}" if err else f"{action}失败")
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        console.error(f"{action}失败: gh 的输出不是有效 JSON")


def _bool_flag(name: str, value: bool | None) -> list[str]:
    """gh 的布尔开关: True/False -> --name=true|false, None 表示不改这一项."""
    return [] if value is None else [f"{name}={str(bool(value)).lower()}"]


def _check_files(files: list[str]) -> None:
    """上传前先确认附件存在 (交给 gh 的报错不如本地检查直白); 通配符交给 gh 展开."""
    for name in files:
        if not os.path.lexists(name) and not any(ch in name for ch in "*?["):
            console.error(f"附件不存在: {name}\n提示: 先构建产物 (uv build --out-dir dist) 再上传")


# ---------------------------------------------------------------- 列表 / 查看

def list_releases(target: str = "", *, limit: int = 30,
                  drafts: bool = True, prereleases: bool = True) -> None:
    """列出发行版 (含草稿与预发布): 标签 / 名称 / 状态 / 发布时间 / 创建时间."""
    gh = _gh()
    args = ["release", "list", "-L", str(max(1, limit)), "--json", LIST_FIELDS, *_repo_args(target)]
    if not drafts:
        args.append("--exclude-drafts")
    if not prereleases:
        args.append("--exclude-pre-releases")
    data = _json(gh, args, "列出发行版")
    if not isinstance(data, list):
        console.error("发行版数据异常, 请稍后重试")
    if not data:
        console.info("还没有任何发行版\n提示: gitx publish create <标签> --notes-file 说明.md 创建第一个")
        return
    table = console.table("标签", "名称", "状态", "发布", "创建", title=f"发行版 {len(data)} 个")
    for rel in data:
        table.add_row(
            console.txt(rel.get("tagName") or ""),
            console.txt(str(rel.get("name") or "")[:48]),
            console.txt(_state(rel)),
            console.txt(str(rel.get("publishedAt") or "")[:10] or "-"),
            console.txt(str(rel.get("createdAt") or "")[:10]),
        )
    console.print(table)
    console.info("看详情: gitx publish view <标签>   |   发布草稿: gitx publish edit <标签> --no-draft")


def _state(rel: dict) -> str:
    if rel.get("isDraft"):
        return "草稿"
    if rel.get("isPrerelease"):
        return "预发布" + ("|最新" if rel.get("isLatest") else "")
    return "最新" if rel.get("isLatest") else "正式"


def view(tag: str = "", target: str = "", *, browse: bool = False) -> None:
    """查看单个发行版: 状态 / 时间 / 说明首行 / 附件清单 (--web 交给 gh 打开网页)."""
    gh = _gh()
    args = ["release", "view", *([tag] if tag else []), *_repo_args(target)]
    if browse:
        _run(gh, [*args, "--web"], "打开发行版")
        return
    rel = _json(gh, [*args, "--json", VIEW_FIELDS], "查看发行版")
    if not isinstance(rel, dict):
        console.error("发行版数据异常, 请稍后重试")
    head = f"[key]{rel.get('tagName') or tag or '(最新)'}[/key]  {str(rel.get('name') or '')}".rstrip()
    console.print(console.styled(f"{head}  [dim]({_state(rel)})[/dim]"))
    console.print(console.txt(
        f"发布: {str(rel.get('publishedAt') or '')[:10] or '-'}    "
        f"目标: {rel.get('targetCommitish') or '-'}"))
    if rel.get("url"):
        console.print(console.link(str(rel["url"]), str(rel["url"])))
    body = str(rel.get("body") or "").strip()
    console.print(console.txt(body.splitlines()[0][:120] if body else "(没有说明)"))
    assets = list(rel.get("assets") or [])
    if assets:
        table = console.table("#", "附件", "大小", title=f"附件 {len(assets)} 个")
        for i, asset in enumerate(assets, 1):
            table.add_row(console.txt(i), console.txt(asset.get("name") or ""),
                          console.txt(console.human_size(int(asset.get("size") or 0))))
        console.print(table)
    else:
        console.warn("附件 0 个 (只有源码包)")
    console.info(f"下载附件: gitx release <仓库> --tag {rel.get('tagName') or tag}")


# ---------------------------------------------------------------- 写操作

def create(tag: str, files: list[str] | None = None, *, target: str = "", title: str = "",
           notes: str = "", notes_file: str = "", prerelease: bool = False, draft: bool = False,
           latest: bool | None = None, commitish: str = "", generate_notes: bool = False,
           verify_tag: bool = False) -> None:
    """创建发行版并上传附件 (附件支持 `dist/*.whl` 这类通配, 由 gh 展开)."""
    gh = _gh()
    args = ["release", "create", tag]
    args += _repo_args(target)
    if title:
        args += ["--title", title]
    if notes:
        args += ["--notes", notes]
    if notes_file:
        args += ["--notes-file", notes_file]
    if prerelease:
        args.append("--prerelease")
    if draft:
        args.append("--draft")
    args += _bool_flag("--latest", latest)
    if commitish:
        args += ["--target", commitish]
    if generate_notes:
        args.append("--generate-notes")
    if verify_tag:
        args.append("--verify-tag")
    _check_files(list(files or ()))
    args += list(files or ())
    console.step(f"创建发行版 {tag}" + (" (预发布)" if prerelease else "")
                 + (" (草稿)" if draft else "") + (f" 附件 {len(files)} 个" if files else ""))
    _run(gh, args, "创建发行版")
    console.done(f"发行版 {tag} 已创建   查看: gitx publish view {tag}")


def upload(tag: str, files: list[str], *, target: str = "", clobber: bool = False) -> None:
    """给已有发行版补传附件 (同名附件存在时需 --clobber, 会先删后传)."""
    gh = _gh()
    if not files:
        console.error("请给出要上传的附件: gitx publish upload <标签> <文件...> [--clobber]")
    _check_files(files)
    args = ["release", "upload", tag, *files, *_repo_args(target)]
    if clobber:
        args.append("--clobber")
    console.step(f"上传 {len(files)} 个附件到 {tag} ...")
    _run(gh, args, "上传附件")
    console.done(f"已上传到发行版 {tag}")


def edit(tag: str, *, new_tag: str = "", target: str = "", title: str = "", notes: str = "",
         notes_file: str = "", prerelease: bool | None = None, draft: bool | None = None,
         latest: bool | None = None) -> None:
    """改发行版: 标题 / 说明 / 预发布 / 草稿 / 最新 (给 --标签 即重命名标签)."""
    gh = _gh()
    args = ["release", "edit", tag]
    args += _repo_args(target)
    if new_tag:
        args += ["--tag", new_tag]
    if title:
        args += ["--title", title]
    if notes:
        args += ["--notes", notes]
    if notes_file:
        args += ["--notes-file", notes_file]
    args += _bool_flag("--prerelease", prerelease)
    args += _bool_flag("--draft", draft)
    args += _bool_flag("--latest", latest)
    console.step(f"更新发行版 {tag} ...")
    _run(gh, args, "更新发行版")
    console.done(f"发行版 {new_tag or tag} 已更新")


def delete(tag: str, *, target: str = "", cleanup_tag: bool = False, yes: bool = False) -> None:
    """删除发行版 (--cleanup-tag 连 git 标签一起删, 会先确认)."""
    gh = _gh()
    if not yes and not console.ask(f"删除发行版 {tag}" + (" 和它的 git 标签" if cleanup_tag else "")
                                   + "?", default=False):
        console.warn("已取消")
        return
    args = ["release", "delete", tag, "-y", *_repo_args(target)]
    if cleanup_tag:
        args.append("--cleanup-tag")
    _run(gh, args, "删除发行版")
    console.done(f"发行版 {tag} 已删除" + (" (标签一并删除)" if cleanup_tag else ""))