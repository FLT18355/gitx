"""GitHub 加速: 镜像前缀重写与 git insteadOf 规则管理.

原理: 在 github.com / raw.githubusercontent.com / api.github.com 的 URL 前
拼上镜像前缀, 例如: https://v6.gh-proxy.org/https://github.com/owner/repo.git

镜像只代理拉取(克隆/下载/API), 不支持推送(git push 返回 405),
因此本工具的策略固定为: 拉取走加速, 推送直连.
"""

from __future__ import annotations

import subprocess

PROVIDERS: dict[str, str] = {
    "v6": "https://v6.gh-proxy.org",    # 本项目默认加速源 (IPv6 优先)
    "v4": "https://v4.gh-proxy.org",    # 同服务 IPv4 端点 (没有 IPv6 时用)
    "gh-proxy": "https://gh-proxy.com",  # 通用公共镜像(备用)
}

# 会被加速前缀重写的域名
TARGETS = (
    "https://github.com/",
    "https://raw.githubusercontent.com/",
    "https://api.github.com/",
)


def resolve(name: str) -> str | None:
    """把配置值解析成加速前缀 URL; None = 直连. 非法值抛 ValueError."""
    if not name or name == "off":
        return None
    if name in PROVIDERS:
        return PROVIDERS[name]
    if name.startswith(("http://", "https://")):
        return name.rstrip("/")
    raise ValueError(f"未知加速源: {name} (可选: {', '.join(PROVIDERS)}, off 或自定义 URL)")


def wrap(url: str, prefix: str | None) -> str:
    """给 GitHub 系 URL 套上加速前缀; 直连或非 GitHub URL 原样返回."""
    if not prefix:
        return url
    for target in TARGETS:
        if url.startswith(target):
            return f"{prefix}/{url}"
    return url


def _rule_key(prefix: str, target: str) -> str:
    return f'url."{prefix}/{target}".insteadOf'


def install_rewrite(prefix: str, scope: str = "--global") -> None:
    """写入 git insteadOf 规则: 所有指向 GitHub 的 git 命令自动走加速.

    scope: --global 或 --local.
    """
    for target in TARGETS:
        subprocess.run(["git", "config", scope, _rule_key(prefix, target), target], check=True)


def uninstall_rewrite(prefix: str, scope: str = "--global") -> None:
    """移除 install_rewrite 写入的规则(忽略不存在的 key)."""
    for target in TARGETS:
        subprocess.run(
            ["git", "config", scope, "--unset-all", _rule_key(prefix, target)],
            check=False,
            capture_output=True,
        )


def probe(prefix: str | None, timeout: int = 20) -> tuple[float, bool]:
    """探测加速源: 用 git ls-remote 实测克隆端点, 返回 (毫秒, 是否可达).

    prefix=None 表示直连; 用真实 git 请求而不是 HTTP 状态码, 结果才可信.
    """
    import os
    import time

    url = wrap("https://github.com/octocat/Hello-World.git", prefix)
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    start = time.perf_counter()
    ok = False
    try:
        r = subprocess.run(["git", "ls-remote", "--symref", url, "HEAD"],
                           capture_output=True, timeout=timeout, env=env)
        ok = r.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        ok = False
    return (time.perf_counter() - start) * 1000, ok


def installed_prefix(scope: str | None = None, path: str = "") -> str:
    """从 git 配置里探测 URL 重写规则中的加速前缀; 无则返回空串.

    scope=None 读取合并后的配置 (含仓库本地规则), "--global" 只读全局;
    path 非空时在该仓库内读取 (可发现 `gitx proxy install --local` 写的规则)。
    """
    args = ["git"]
    if path:
        args += ["-C", path]
    args += ["config"]
    if scope:
        args += [scope]
    args += ["--get-regexp", r"url\..*insteadOf"]
    r = subprocess.run(args, capture_output=True, text=True)
    out = (r.stdout or "").strip()
    if r.returncode != 0 or not out:
        return ""
    for line in out.splitlines():
        key = line.split()[0]
        inner = key[len("url."):]
        low = inner.lower()
        # key 形如: url.<prefix>/https://github.com/.insteadof (保留 prefix 原始大小写)
        for target in TARGETS:
            suffix = f"/{target.rstrip('/')}/.insteadof"
            if low.endswith(suffix.lower()):
                return inner[: -len(suffix)]
    return ""
