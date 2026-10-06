"""Pull Request: 列表 / 详情 / 创建.

列表与详情走 GitHub API (默认加速, 只读); 创建交给已登录的 `gh`
(分支推送与写入鉴权由 gh 处理, 本工具不接触写入令牌)。
"""

from __future__ import annotations

import shutil
import subprocess

from . import config, console, gitcmd, github

STATES = ("open", "closed", "all")


def _resolve(target: str, path: str = ".") -> tuple[str, str]:
    """目标仓库: owner/repo 或链接; 缺省读当前仓库 origin."""
    if target:
        if "://" not in target and "github.com" not in target:
            return github.parse_repo(target)
        parsed = github.owner_repo(target)
        if parsed:
            return parsed
        console.error(f"无法识别仓库: {target} (形如 owner/repo)")
    parsed = github.owner_repo(gitcmd.remote_url("origin", path))
    if not parsed:
        console.error("当前仓库没有 GitHub origin\n提示: 用 gitx pr list owner/repo, 或在仓库目录里运行")
    return parsed


def list_pulls(target: str = "", *, state: str = "open", limit: int = 20,
               prefix: str | None = None, path: str = ".") -> None:
    """列出 Pull Request."""
    owner, repo = _resolve(target, path)
    data = github.api(github.api_url(owner, repo, f"/pulls?state={state}&per_page={max(1, min(limit, 100))}"),
                      prefix)
    if not isinstance(data, list):
        console.error("PR 数据异常, 请稍后重试")
    if not data:
        console.info(f"{owner}/{repo} 没有 {state} 状态的 Pull Request")
        return
    table = console.table("#", "标题", "作者", "来源 -> 目标", "更新", "状态", title=f"{owner}/{repo} 的 PR")
    for pr in data:
        head = str((pr.get("head") or {}).get("ref") or "")
        base = str((pr.get("base") or {}).get("ref") or "")
        mark = "草稿" if pr.get("draft") else ("已合并" if pr.get("merged_at") else str(pr.get("state") or state))
        table.add_row(
            console.txt(pr.get("number")),
            console.txt(str(pr.get("title") or "")[:60]),
            console.txt(str((pr.get("user") or {}).get("login") or "")),
            console.txt(f"{head} -> {base}"),
            console.txt(str(pr.get("updated_at") or "")[:10]),
            console.txt(mark),
        )
    console.print(table)
    console.info(f"看详情: gitx pr view <编号>   |   其它状态: --state all / closed")


def view(number: int, target: str = "", *, prefix: str | None = None,
         browse: bool = False, path: str = ".") -> None:
    """查看单个 PR 的标题 / 状态 / 作者 / 正文."""
    owner, repo = _resolve(target, path)
    pr = github.api(github.api_url(owner, repo, f"/pulls/{int(number)}"), prefix)
    if not isinstance(pr, dict):
        console.error(f"没有找到 PR #{number}")
    url = str(pr.get("html_url") or "")
    state = "已合并" if pr.get("merged_at") else str(pr.get("state") or "")
    body = str(pr.get("body") or "").strip() or "(没有正文)"
    console.print(console.styled(
        f"[key]#{pr.get('number')}[/key] {str(pr.get('title') or '')}  [dim]({state})[/dim]"))
    console.print(console.txt(f"作者: {(pr.get('user') or {}).get('login') or ''}    "
                              f"分支: {(pr.get('head') or {}).get('ref') or ''} -> "
                              f"{(pr.get('base') or {}).get('ref') or ''}"))
    if url:
        console.print(console.link(url, url))
    console.print()
    console.print(console.txt(body))
    if browse and url:
        _open(url)


def create(title: str = "", body: str = "", *, base: str = "", head: str = "",
           fill: bool = False, draft: bool = False, path: str = ".") -> None:
    """用已登录的 gh 创建 Pull Request."""
    gitcmd.require_repo(path)
    if not shutil.which("gh"):
        console.error("创建 PR 需要已安装并登录 gh (https://cli.github.com)\n"
                      "提示: gh auth login 之后重试; 也可以直接 gitx web pulls 去网页创建")
    args = ["gh", "pr", "create"]
    if title:
        args += ["--title", title]
    if body:
        args += ["--body", body]
    if fill:
        args.append("--fill")
    if base:
        args += ["--base", base]
    if head:
        args += ["--head", head]
    if draft:
        args.append("--draft")
    console.step("创建 Pull Request...")
    if subprocess.run(args, cwd=path).returncode != 0:
        console.error("创建 PR 失败\n提示: 确认分支已推送 (gitx push), 或改用 gitx web pulls 在网页创建")


def _open(url: str) -> None:
    import webbrowser  # noqa: PLC0415  只打开浏览器时才需要

    if not webbrowser.open(url):
        console.info("未能自动打开浏览器, 请手动访问上面的链接")
