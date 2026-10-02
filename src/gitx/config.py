"""持久化配置: ~/.config/gitx/config.json (或 $XDG_CONFIG_HOME/gitx/config.json)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import accel, console

DEFAULTS: dict[str, object] = {
    "proxy": "v6",        # 加速源: v6 / gh-proxy / off / 自定义 https://...
    "depth": 1,           # 克隆深度, 0 = 完整克隆
    "branch": "",         # 默认分支, 空 = 自动探测
    "message": "日常同步更新",  # push 默认提交信息
    "token": "",          # GitHub token: 提高 API 限额 (60 -> 5000 次/小时)
}


def config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    return Path(xdg) / "gitx" if xdg else Path.home() / ".config" / "gitx"


def config_path() -> Path:
    return config_dir() / "config.json"


def cache_dir() -> Path:
    """缓存目录 (~/.cache/gitx): 存放可再生的数据, 删掉也不影响使用."""
    xdg = os.environ.get("XDG_CACHE_HOME")
    return Path(xdg) / "gitx" if xdg else Path.home() / ".cache" / "gitx"


def load() -> dict:
    path = config_path()
    if path.exists():
        try:
            data = json.loads(path.read_text("utf-8"))
            return {**DEFAULTS, **data}
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULTS)


def save(data: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    merged = {**DEFAULTS, **data}
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", "utf-8")


def active_proxy(flag: str | None = None, no_proxy: bool = False) -> str | None:
    """返回本次生效的加速前缀; None = 直连.

    优先级: 命令行 --proxy > 环境变量 GITX_PROXY > 配置文件.
    """
    if no_proxy:
        return None
    name = flag or os.environ.get("GITX_PROXY") or str(load().get("proxy", "v6"))
    try:
        return accel.resolve(name)
    except ValueError as exc:
        console.error(str(exc))
