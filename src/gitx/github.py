"""GitHub 链接解析与 URL 构造."""

from __future__ import annotations

import re

_REPO_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")
_TREE_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/]+?)/tree/([^/]+)(?:/(.*))?/?$")
_BLOB_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/]+?)/(?:blob|raw)/([^/]+)/(.*?)/?$")
_SSH_RE = re.compile(r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?/?$")


def parse_url(url: str) -> dict:
    """解析 GitHub 链接 -> {mode, owner, repo, branch, path}.

    mode: repo | folder | file
    仓库:   https://github.com/owner/repo
    文件夹: https://github.com/owner/repo/tree/分支/路径
    文件:   https://github.com/owner/repo/blob|raw/分支/路径/文件
    """
    url = url.strip().rstrip("/").split("?")[0]
    m = _SSH_RE.match(url)
    if m:
        return {"mode": "repo", "owner": m.group(1), "repo": m.group(2), "branch": "", "path": ""}
    m = _TREE_RE.match(url)
    if m:
        owner, repo, branch, path = m.group(1), m.group(2), m.group(3), (m.group(4) or "").strip("/")
        if not path:
            # /tree/分支 无路径 -> 等价整仓库(锁定分支)
            return {"mode": "repo", "owner": owner, "repo": repo, "branch": branch, "path": ""}
        return {"mode": "folder", "owner": owner, "repo": repo, "branch": branch, "path": path}
    m = _BLOB_RE.match(url)
    if m:
        return {
            "mode": "file",
            "owner": m.group(1),
            "repo": m.group(2),
            "branch": m.group(3),
            "path": m.group(4).rstrip("/"),
        }
    m = _REPO_RE.match(url)
    if m:
        return {"mode": "repo", "owner": m.group(1), "repo": m.group(2), "branch": "", "path": ""}
    raise ValueError(f"无法识别 GitHub 链接: {url}")


def repo_clone_url(owner: str, repo: str) -> str:
    return f"https://github.com/{owner}/{repo}.git"


def raw_url(owner: str, repo: str, branch: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
