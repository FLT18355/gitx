"""HTTP 下载: 断点续传 + 进度条 (仓库文件 / Release 附件 / .gitignore 模板共用).

先写 `<目标>.part`, 全部收完再改名 —— 中途失败 (Ctrl+C / 断网) 时 .part 还在,
下次运行自动带 `Range: bytes=<已有字节>-` 续传, 不用从零再来一遍。
"""

from __future__ import annotations

import os

from . import __version__, accel, console

_UA = {"User-Agent": f"gitx/{__version__}"}


class _RangeUnsatisfied(Exception):
    """Range 起点超出文件大小 (一般是残留的 .part 比新文件还大), 需要从头重下."""


def fetch(url: str, dest: str, *, prefix: str | None = None, headers: dict | None = None,
          size: int = 0, resume: bool = True, timeout: int = 300, label: str = "") -> int:
    """下载 url 到 dest, 返回写入字节数; 出错时打印原因并退出.

    size 为已知的完整大小 (Release API 会给), 用于校验与续传进度; 0 表示未知。
    """
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    part = f"{dest}.part"
    while True:
        start = os.path.getsize(part) if resume and os.path.exists(part) else 0
        if size and start >= size:
            start = 0  # .part 残留与目标不符: 从头来
            os.remove(part)
        try:
            written = _request(url, part, prefix, headers, size, start, timeout,
                               label or os.path.basename(dest))
            break
        except _RangeUnsatisfied:
            os.remove(part)
            resume = False  # 服务器不支持/起点越界: 丢掉 .part 从头下

    got = os.path.getsize(part) if os.path.exists(part) else 0
    if size and got != size:
        if start:
            console.warn(f"续传结果不完整 ({console.human_size(got)} / {console.human_size(size)}), "
                         "已丢弃残留并重新下载")
            os.remove(part)
            return fetch(url, dest, prefix=prefix, headers=headers, size=size,
                         resume=False, timeout=timeout, label=label)
        console.error(f"下载不完整: {console.human_size(got)} / {console.human_size(size)}\n"
                      f"提示: 网络中断, 重跑本命令会从 .part 续传 ({part})")
    os.replace(part, dest)
    return written


def _request(url: str, part: str, prefix: str | None, headers: dict | None, size: int,
             start: int, timeout: int, label: str) -> int:
    import urllib.error  # noqa: PLC0415  只有真正下载时才需要
    import urllib.request

    merged = {**_UA, **(headers or {})}
    if start:
        merged["Range"] = f"bytes={start}-"
    req = urllib.request.Request(accel.wrap(url, prefix), headers=merged)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            # 镜像/服务器不支持 Range 时会回 200, 那就老老实实从头写
            append = start > 0 and getattr(resp, "status", 200) == 206
            return console.save_stream(resp, part, label, total=size,
                                       start=start if append else 0, append=append)
    except urllib.error.HTTPError as exc:
        if exc.code == 416:
            raise _RangeUnsatisfied() from None
        if exc.code == 404:
            console.error(f"下载失败 HTTP 404 (未找到): {url}\n提示: 检查分支名与路径是否正确")
        if exc.code in (403, 429):
            console.error(f"下载失败 HTTP {exc.code} (被限流): {url}\n"
                          "提示: 稍后重试, 或 gitx proxy on 换加速源")
        console.error(f"下载失败 HTTP {exc.code}: {url}")
    except (urllib.error.URLError, OSError) as exc:
        console.error(f"下载失败: {exc}\n提示: gitx proxy test 检查加速源, 或 gitx proxy on 开启加速")
    return 0