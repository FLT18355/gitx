"""GitHub 加速: 镜像前缀重写与 git insteadOf 规则管理.

原理: 在 github.com / raw.githubusercontent.com / api.github.com 的 URL 前
拼上镜像前缀, 例如: https://v6.gh-proxy.org/https://github.com/owner/repo.git

镜像只代理拉取(克隆/下载/API), 不支持推送(git push 返回 405),
因此本工具的策略固定为: 拉取走加速, 推送直连.
"""

from __future__ import annotations

import subprocess

PROVIDERS: dict[str, str] = {
    "v6": "https://v6.gh-proxy.org",    # 本项目默认加速源
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


def installed_prefix() -> str:
    """从 git 全局配置探测已安装的加速前缀; 无则返回空串."""
    rc, out = _git_config_get_regexp(scope="--global", pattern=r"url\..*insteadOf")
    if rc != 0 or not out:
        return ""
    for line in out.splitlines():
        key = line.split()[0]
        if not key.lower().endswith(".insteadof"):
            continue
        # key 形如: url.<prefix>/https://github.com/.insteadof
        inner = key[len("url."):].lower()
        for target in TARGETS:
            marker = target.rstrip("/")
            suffix = f"/{marker}/.insteadof"
            if inner.endswith(suffix):
                return inner[: -len(suffix)]
    return ""


def _git_config_get_regexp(scope: str, pattern: str) -> tuple[int, str]:
    r = subprocess.run(["git", "config", scope, "--get-regexp", pattern], capture_output=True, text=True)
    return r.returncode, (r.stdout or "").strip()
