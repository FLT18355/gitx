"""GitHub 链接解析, URL 构造与 REST API 客户端."""

from __future__ import annotations

import json
import re

from . import __version__, accel, config, console, gitcmd

_REPO_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")
_TREE_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/]+?)/tree/([^/]+)(?:/(.*))?/?$")
_BLOB_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/]+?)/(?:blob|raw)/([^/]+)/(.*?)/?$")
_SSH_RE = re.compile(r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?/?$")
_ASSET_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/]+?)/releases/download/([^/]+)/(.+?)/?$")
_RELEASE_RE = re.compile(
    r"^https?://github\.com/([^/]+)/([^/]+?)/releases(?:/(?:tag|latest|expanded_assets)/([^/]+))?/?$"
)


def parse_url(url: str) -> dict:
    """解析 GitHub 链接 -> {mode, owner, repo, branch, path[, tag]}.

    mode: repo | folder | file | release | asset
    仓库:     https://github.com/owner/repo
    文件夹:   https://github.com/owner/repo/tree/分支/路径
    文件:     https://github.com/owner/repo/blob|raw/分支/路径/文件
    发布页:   https://github.com/owner/repo/releases[/tag/标签]
    发布附件: https://github.com/owner/repo/releases/download/标签/文件名
    """
    url = url.strip().rstrip("/").split("?")[0]
    m = _SSH_RE.match(url)
    if m:
        return {"mode": "repo", "owner": m.group(1), "repo": m.group(2), "branch": "", "path": ""}
    m = _ASSET_RE.match(url)
    if m:
        return {
            "mode": "asset",
            "owner": m.group(1),
            "repo": m.group(2),
            "branch": "",
            "path": m.group(4).rstrip("/"),
            "tag": m.group(3),
        }
    m = _RELEASE_RE.match(url)
    if m:
        tag = m.group(3) or ""
        if tag == "latest":
            tag = ""
        return {"mode": "release", "owner": m.group(1), "repo": m.group(2), "branch": "", "path": "", "tag": tag}
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


def api_url(owner: str, repo: str, path: str) -> str:
    """GitHub REST API 地址; path 以 / 开头, 如 /releases/latest."""
    return f"https://api.github.com/repos/{owner}/{repo}{path}"


def github_url(owner: str, repo: str, path: str) -> str:
    return f"https://github.com/{owner}/{repo}{path}"


# ---------------------------------------------------------------- 仓库名解析

_REPO_ARG_RE = re.compile(r"^([\w.-]+)/([\w.-]+)$")
_REPO_TAIL_RE = re.compile(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?/?$")


def parse_repo(arg: str) -> tuple[str, str]:
    """'owner/repo' -> (owner, repo); 不合法抛 ValueError."""
    m = _REPO_ARG_RE.match(arg.strip())
    if not m:
        raise ValueError(f"无法识别仓库: {arg} (形如 owner/repo)")
    return m.group(1), m.group(2)


def owner_repo(url: str) -> tuple[str, str] | None:
    """从任意 GitHub 远端地址提取 owner/repo (兼容 https / SSH / 加速前缀)."""
    m = _REPO_TAIL_RE.search((url or "").strip())
    return (m.group(1), m.group(2)) if m else None


# ---------------------------------------------------------------- REST API

HEADERS = {"User-Agent": f"gitx/{__version__}", "Accept": "application/vnd.github+json"}
_TOKEN: str | None = None


def api_token() -> str:
    """API 认证: 配置的 token 优先, 否则复用已登录 gh 的 token (提高限额到 5000 次/小时)."""
    global _TOKEN
    if _TOKEN is None:
        _TOKEN = str(config.load().get("token") or "")
        if not _TOKEN:
            rc, out = gitcmd.capture(["gh", "auth", "token"])
            _TOKEN = out if rc == 0 else ""
    return _TOKEN


def api(url: str, prefix: str | None = None, *, timeout: int = 30) -> object:
    """请求 GitHub REST API (走加速); 失败时打印原因并退出."""
    import urllib.error  # noqa: PLC0415  仅网络命令需要, 避免拖慢其它命令的启动
    import urllib.request

    req = urllib.request.Request(accel.wrap(url, prefix), headers=dict(HEADERS))
    token = api_token()
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            console.error("未找到该资源\n提示: 检查 owner/repo 是否正确, 或用 --tags 查看可用标签")
        if exc.code in (403, 429):
            console.error(f"GitHub API 受限 HTTP {exc.code}: 匿名请求每小时 60 次\n"
                          "提示: 设置 token 可提高到 5000 次/小时 (gitx config set token <token>)")
        console.error(f"API 请求失败 HTTP {exc.code}: {url}")
    except (urllib.error.URLError, OSError) as exc:
        console.error(f"API 请求失败: {exc}\n提示: gitx proxy test 检查加速源, 或 --no-proxy 直连")
    return None


def get_text(url: str, prefix: str | None = None, *, timeout: int = 30) -> str:
    """取一段纯文本 (raw 文件 / 模板); 失败时打印原因并退出."""
    import urllib.error  # noqa: PLC0415
    import urllib.request

    req = urllib.request.Request(accel.wrap(url, prefix), headers=dict(HEADERS))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        console.error(f"获取失败 HTTP {exc.code}: {url}")
    except (urllib.error.URLError, OSError) as exc:
        console.error(f"获取失败: {exc}\n提示: gitx proxy on 开启加速后重试")
    return ""
