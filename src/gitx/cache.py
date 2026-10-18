"""缓存: 把"可再生的网络结果"记在 ~/.cache/gitx, 少跑一趟网络、少用一次 API 限额.

两类内容:
  1. 整文件型缓存 (如 github/gitignore 模板索引 `gitignore.json`), 由各自模块直接读写;
  2. 键值型缓存 (`entries/<哈希>.json`), 统一走本模块的 get/put —— 目前接入的是
     GitHub API 的 GET 响应、远端默认分支探测、最新版本查询。

为什么值得缓存: 这些数据的"贵"在往返而不在算 —— 匿名 API 只有 60 次/小时, 国内直连
`api.github.com` 又要几秒。缓存默认 TTL 5 分钟 (`cache_ttl`), 过期即重新抓, 因此看到
的内容最多旧 5 分钟; `gitx cache clear` 随时清空, `cache = false` 可整体关掉。

缓存都是可再生的: 删掉后下次使用会自动重建, 不影响任何功能。
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import shutil
import time
from pathlib import Path

from . import config, console

# 已知整文件缓存的用途说明 (未知文件按"可再生数据"处理)
_NOTES = {
    "gitignore.json": "github/gitignore 模板索引 (有效期 7 天)",
}
_ENTRY_DIR = "entries"  # 键值型缓存都放这个子目录, 便于区分与统计


# ---------------------------------------------------------------- 总开关

def usable() -> bool:
    """缓存是否启用 (配置 cache = false 时全部旁路)."""
    try:
        return bool(config.load().get("cache", True))
    except Exception:
        return True


def ttl() -> int:
    """默认存活秒数 (配置 cache_ttl; 0 = 不使用键值缓存)."""
    try:
        return max(0, int(config.load().get("cache_ttl", 300)))
    except Exception:
        return 300


# ---------------------------------------------------------------- 键值缓存

def _entry_path(key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return config.cache_dir() / _ENTRY_DIR / f"{digest}.json"


def get(key: str, *, ttl_seconds: int | None = None) -> object | None:
    """取一条缓存; 没有 / 过期 / 关掉缓存都返回 None."""
    if not usable():
        return None
    life = ttl() if ttl_seconds is None else ttl_seconds
    if life <= 0:
        return None
    path = _entry_path(key)
    try:
        raw = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict) or raw.get("key") != key:
        return None  # 哈希撞了 / 文件坏了: 当成没命中
    at = raw.get("at")
    if not isinstance(at, (int, float)) or time.time() - at > life:
        return None
    return raw.get("value")


def put(key: str, value: object, *, ttl_seconds: int | None = None) -> None:
    """写一条缓存; 关掉缓存 / TTL 为 0 时什么都不做 (不静默失败也不报错)."""
    if not usable():
        return
    life = ttl() if ttl_seconds is None else ttl_seconds
    if life <= 0:
        return
    path = _entry_path(key)
    payload = {"key": key, "at": time.time(), "ttl": life, "value": value}
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), "utf-8")
        tmp.replace(path)  # 原子替换: 半截文件不会被读到


def drop(key: str) -> None:
    with contextlib.suppress(OSError):
        _entry_path(key).unlink()


def entries() -> list[dict]:
    """列出所有键值缓存: [{key, at, ttl, age, alive, size}] (按新旧排序)."""
    root = config.cache_dir() / _ENTRY_DIR
    if not root.exists():
        return []
    out: list[dict] = []
    for path in root.glob("*.json"):
        try:
            raw = json.loads(path.read_text("utf-8"))
            size = path.stat().st_size
        except (OSError, ValueError):
            continue
        if not isinstance(raw, dict):
            continue
        at = float(raw.get("at") or 0)
        life = int(raw.get("ttl") or 0)
        out.append({"key": str(raw.get("key") or path.name), "at": at, "ttl": life,
                    "age": max(0, int(time.time() - at)), "alive": time.time() - at <= life,
                    "size": size})
    return sorted(out, key=lambda item: -item["at"])


def purge(*, expired_only: bool = True) -> int:
    """删掉过期 (或全部) 的键值缓存; 返回删掉的条数."""
    count = 0
    for item in entries():
        if expired_only and item["alive"]:
            continue
        path = _entry_path(str(item["key"]))
        if not path.exists():
            continue
        drop(str(item["key"]))
        count += 1
    return count


# ---------------------------------------------------------------- 查看 / 清理

def flush() -> int:
    """清掉全部键值缓存: 写操作 (如发/删发行版) 之后调用 —— 刚改过的数据不该再从缓存里读."""
    return purge(expired_only=False)


def _files() -> list[tuple[str, int]]:
    root = config.cache_dir()
    if not root.exists():
        return []
    out: list[tuple[str, int]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            with contextlib.suppress(OSError):
                out.append((str(path.relative_to(root)), path.stat().st_size))
    return out


def info() -> None:
    """查看缓存目录与占用 (整文件 + 键值缓存分开列)."""
    root = config.cache_dir()
    files = _files()
    kept = entries()
    console.info(f"缓存目录: {root}")
    table = console.table("文件", "大小", "说明", title="缓存内容")
    total = 0
    for name, size in files:
        if name.startswith(f"{_ENTRY_DIR}/"):
            continue  # 键值缓存单独汇总, 不然一屏全是哈希文件名
        total += size
        table.add_row(console.txt(name), console.txt(console.human_size(size)),
                      console.txt(_NOTES.get(name, "可再生数据, 删除后自动重建")))
    if kept:
        size = sum(item["size"] for item in kept)
        total += size
        alive = sum(1 for item in kept if item["alive"])
        table.add_row(console.txt(f"{_ENTRY_DIR}/ ({len(kept)} 条)"),
                      console.txt(console.human_size(size)),
                      console.txt(f"接口 / 网页结果的短期缓存, 未过期 {alive} 条 "
                                  f"(默认 {ttl()} 秒, 配置 cache_ttl)"))
    if not files:
        console.info("缓存是空的 (用到时自动生成)")
        return
    console.print(table)
    console.info(f"合计 {console.human_size(total)}   |   明细: gitx cache list"
                 "   |   清理: gitx cache clear")


def list_entries(*, all_: bool = False) -> None:
    """列出键值缓存的明细: 键 / 写于 / 有效期 / 状态."""
    kept = entries()
    if not kept:
        console.info("还没有键值缓存 (用过 gitx stat / search / release 之后就会有)")
        return
    table = console.table("缓存键", "写入", "有效期", "状态", title=f"缓存明细 ({len(kept)} 条)")
    now = time.time()
    for item in kept:
        if not all_ and not item["alive"]:
            continue
        written = time.strftime("%m-%d %H:%M", time.localtime(item["at"]))
        state = "有效" if item["alive"] else "已过期"
        table.add_row(console.txt(item["key"][:96]), console.txt(written),
                      console.txt(f"{item['ttl']} 秒"), console.txt(state))
    console.print(table)
    if not all_:
        console.info("已过期的没列出来 (加 --all 看全部; 清理: gitx cache prune)")


def prune() -> None:
    """清掉已过期的键值缓存 (留着的都还在有效期内)."""
    gone = purge(expired_only=True)
    if not gone:
        console.info("没有过期的缓存")
        return
    console.done(f"清掉 {gone} 条过期缓存")


def clear(*, yes: bool = False) -> None:
    """删除整个缓存目录 (下次使用自动重建)."""
    root = config.cache_dir()
    if not root.exists():
        console.info("缓存已经是空的, 无需清理")
        return
    files = _files()
    total = sum(size for _name, size in files)
    if not yes and not console.ask(f"删除缓存目录 {root} (共 {console.human_size(total)})?", default=False):
        console.error("已取消")
    shutil.rmtree(root, ignore_errors=True)
    console.done(f"缓存已清理 (释放 {console.human_size(total)}, 下次使用自动重建)")