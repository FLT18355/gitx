"""缓存管理: 查看 ~/.cache/gitx 的内容与占用, 按需清理.

缓存都是可再生的数据 (如 .gitignore 模板索引), 删掉后下次使用会自动重建,
因此 `gitx cache clear` 不会影响任何功能。
"""

from __future__ import annotations

import shutil

from . import config, console

# 已知缓存文件的用途说明 (未知文件按"可再生数据"处理)
_NOTES = {
    "gitignore.json": "github/gitignore 模板索引 (有效期 7 天)",
}


def _files() -> list[tuple[str, int]]:
    root = config.cache_dir()
    if not root.exists():
        return []
    out: list[tuple[str, int]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            try:
                out.append((str(path.relative_to(root)), path.stat().st_size))
            except OSError:
                pass
    return out


def info() -> None:
    """查看缓存目录与占用."""
    root = config.cache_dir()
    files = _files()
    console.info(f"缓存目录: {root}")
    if not files:
        console.info("缓存是空的 (用到时自动生成)")
        return
    table = console.table("文件", "大小", "说明", title="缓存内容")
    total = 0
    for name, size in files:
        total += size
        table.add_row(console.txt(name), console.txt(console.human_size(size)),
                      console.txt(_NOTES.get(name, "可再生数据, 删除后自动重建")))
    console.print(table)
    console.info(f"合计 {console.human_size(total)}   |   清理: gitx cache clear")


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
