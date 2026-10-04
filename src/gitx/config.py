"""持久化配置: ~/.config/gitx/config.json (或 $XDG_CONFIG_HOME/gitx/config.json)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import accel, console

DEFAULTS: dict[str, object] = {
    "proxy": "v6",        # 加速源: v6 / v4 / gh-proxy / off / 自定义 https://...
    "release_proxy": "",  # Release 专用加速源, 空 = 跟随 proxy (独立设置: gitx proxy release)
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


def release_source(cfg: dict | None = None) -> str:
    """Release 功能的独立加速源设置; 空串 = 跟随全局 proxy."""
    data = load() if cfg is None else cfg
    return str(data.get("release_proxy") or "")


def active_proxy(flag: str | None = None, no_proxy: bool = False, *, release: bool = False,
                 cfg: dict | None = None) -> str | None:
    """返回本次生效的加速前缀; None = 直连.

    优先级:
      普通操作: --proxy > GITX_PROXY > 配置 proxy
      Release:  --proxy > GITX_RELEASE_PROXY > 配置 release_proxy > GITX_PROXY > 配置 proxy
    release_proxy 为空 = 跟随全局, 因此不设置时行为与旧版完全一致.
    cfg 已加载时传入可省一次磁盘读取.
    """
    if no_proxy:
        return None
    data = load() if cfg is None else cfg
    if release:
        name = (flag or os.environ.get("GITX_RELEASE_PROXY")
                or release_source(data)
                or os.environ.get("GITX_PROXY") or str(data.get("proxy", "v6")))
    else:
        name = flag or os.environ.get("GITX_PROXY") or str(data.get("proxy", "v6"))
    try:
        return accel.resolve(name)
    except ValueError as exc:
        console.error(str(exc))
