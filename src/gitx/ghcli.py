"""gh CLI 共用层: 定位 / 登录态 / 调用 / JSON 解析 / 仓库参数.

gitx 不自己实现 GitHub 的写操作与账号管理, 一律交给已安装并登录的 `gh`
(https://cli.github.com): 本工具只拼参数、不接触令牌, 权限由 gh 自己的登录态决定。
发行版 (publish) / 工作流 (actions) / 登录态 (auth) / 我的仓库 (repos) / 创建 PR 都走这一层。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time

from . import console, gitcmd, github


def find(feature: str) -> str:
    """已安装的 gh 绝对路径; 没装就给中文提示并退出."""
    path = shutil.which("gh")
    if not path:
        console.error(f"{feature}需要已安装的 gh CLI (https://cli.github.com)\n"
                      "提示: 装好 gh 并 gitx auth login 之后重试")
    return path


_LOGGED_IN: bool | None = None  # 进程内缓存: 一条命令里会查很多次登录态


def logged_in(path: str) -> bool:
    """gh 是否已登录; 结果在进程内缓存一次 (每次调用都是一趟网络, 2-6 秒).

    用 `gh auth token` 判断而不是 `gh auth status`: 两者结论一致, 但 token 只读本地
    hosts.yml (约 0.5 秒), status 要校验凭据 (约 3 秒), 而 repos 一条命令会问很多次。
    """
    global _LOGGED_IN
    if _LOGGED_IN is None:
        _LOGGED_IN = gitcmd.capture([path, "auth", "token"])[0] == 0
    return _LOGGED_IN


def require(feature: str, *, login: bool = True, hint: str = "") -> str:
    """已装 (默认还要求已登录) 的 gh 路径; 不满足就中文提示并退出."""
    path = shutil.which("gh")
    if not path:
        tail = f"; {hint}" if hint else ""
        console.error(f"{feature}需要已安装的 gh CLI (https://cli.github.com)\n"
                      f"提示: 安装并 gh auth login 之后重试{tail}")
    if login and not logged_in(path):
        console.error(f"gh 未登录, 无法{feature}\n"
                      "提示: 先执行 gitx auth login (写操作需要仓库写权限)")
    return path


def run(path: str, args: list[str], action: str) -> None:
    """跑一条 gh 命令并透传它自己的输出; 失败时补一句中文提示."""
    if subprocess.run([path, *args]).returncode != 0:
        console.error(f"{action}失败 (gh 已打印原因)")


def api(args: list[str]) -> None:
    """直通 gh api; 不带参数 / rate_limit 时渲染成中文限额表, --raw 看原始 JSON."""
    gh = require("调用 GitHub API")
    raw = "--raw" in args
    args = [arg for arg in args if arg != "--raw"]
    if not args:
        args = ["rate_limit"]
    if not raw and args in (["rate_limit"], ["/rate_limit"]):
        code, out, err = capture(gh, ["api", "rate_limit"])
        if code != 0:
            console.error(f"读取 API 限额失败\n{err}" if err else "读取 API 限额失败")
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and _render_rate_limit(data):
            return
        console.warn("限额数据格式不认识, 改为打印原始输出")
        console.print(out)
        return
    run(gh, ["api", *args], "调用 GitHub API")


# 限额资源的显示名 (GitHub 返回的 key -> 中文); 没列到的原样显示
_RATE_NAMES = {
    "core": "核心 REST",
    "search": "搜索",
    "graphql": "GraphQL",
    "integration_manifest": "集成清单",
    "source_import": "源码导入",
    "code_search": "代码搜索",
    "code_scanning_autofix": "代码扫描修复",
    "code_scanning_upload": "代码扫描上传",
    "actions_runner_registration": "Actions Runner 注册",
    "scim": "SCIM",
    "dependency_snapshots": "依赖快照",
    "dependency_sbom": "依赖 SBOM",
    "audit_log": "审计日志",
    "audit_log_streaming": "审计日志流",
}
_RATE_ORDER = ("core", "search", "graphql")


def _reset_text(timestamp: int, now: float) -> str:
    """epoch -> "10-25 15:30 (18 分钟后)" 这类人话."""
    if timestamp <= 0:
        return "-"
    when = time.strftime("%m-%d %H:%M", time.localtime(timestamp))
    left = int((timestamp - now) // 60)
    if timestamp <= now:
        return f"{when} (已重置)"
    if left <= 0:
        return f"{when} (即将重置)"
    if left < 60:
        return f"{when} ({left} 分钟后)"
    return f"{when} ({left // 60} 小时 {left % 60} 分后)"


def _render_rate_limit(data: dict) -> bool:
    """把 /rate_limit 的 JSON 画成用户看得懂的表格; 结构不对返回 False."""
    resources = data.get("resources")
    if not isinstance(resources, dict) or not resources:
        return False
    keys = [key for key in _RATE_ORDER if key in resources]
    keys += sorted(key for key in resources if key not in _RATE_ORDER)
    table = console.table("资源", "限额", "已用", "剩余", "重置时间", title="GitHub API 限额")
    now = time.time()
    for key in keys:
        info = resources.get(key)
        if not isinstance(info, dict):
            continue
        limit = int(info.get("limit") or 0)
        used = int(info.get("used") or 0)
        remaining = int(info.get("remaining") or 0)
        reset = int(info.get("reset") or 0)
        if limit < 0:  # GitHub 用 -1 表示不限
            limit_text, used_text, remain_text = "不限", "-", "-"
        else:
            pct = f" ({remaining * 100 // limit}%)" if limit else ""
            limit_text, used_text, remain_text = str(limit), str(used), f"{remaining}{pct}"
        table.add_row(
            console.txt(_RATE_NAMES.get(key, key)),
            console.txt(limit_text),
            console.txt(used_text),
            console.txt(remain_text),
            console.txt(_reset_text(reset, now)),
        )
    console.print(table)
    core = resources.get("core")
    if isinstance(core, dict) and 0 < int(core.get("limit") or 0) <= 60:
        console.info("当前是低限额 (60 次/小时): 运行 gitx auth token --save 可提升到 5000 次/小时")
    console.hint("原始 JSON: gitx api rate_limit --raw   |   单看某一块: gitx api rate_limit --jq .resources.core")
    return True


def capture(path: str, args: list[str]) -> tuple[int, str, str]:
    """跑 gh 并同时拿到 stdout / stderr (gh 的报错都写在 stderr)."""
    try:
        done = subprocess.run([path, *args], capture_output=True, text=True)
    except FileNotFoundError:
        return 127, "", "未找到 gh"
    return done.returncode, done.stdout or "", (done.stderr or "").strip()


def json_out(path: str, args: list[str], action: str) -> object:
    """跑一条 gh 命令并按 JSON 解析输出."""
    code, out, err = capture(path, args)
    if code != 0:
        console.error(f"{action}失败\n{err}" if err else f"{action}失败")
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        console.error(f"{action}失败: gh 的输出不是有效 JSON")


def repo_args(target: str) -> list[str]:
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
