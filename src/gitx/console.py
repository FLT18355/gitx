"""终端输出: 基于 rich 的统一控制台 (语义化输出 / 表格 / 进度条 / 交互).

所有函数都会对动态文本做 markup 转义, 因此仓库名、文件名里的 `[]` 等字符不会
被 rich 当成样式标签; 需要自己写样式的场合请直接用 `console.print` 或 `txt()`.

启动速度: rich.progress / rich.prompt / questionary 都改为按需导入 —— 它们是
重依赖 (合计约 2.3 秒), 只有下载与交互挑选才用得上。
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator, NoReturn, Sequence

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

if TYPE_CHECKING:  # 仅供类型检查, 运行时不导入
    from rich.progress import Progress

THEME = Theme({
    "info": "green",
    "step": "cyan",
    "warn": "yellow",
    "err": "bold red",
    "ok": "bold green",
    "key": "bold cyan",
    "num": "bold yellow",
    "dim": "dim",
    "title": "bold cyan",
    "hash": "yellow",
    "graph": "green",
    "branch": "bold cyan",
    "tag": "magenta",
    "date": "dim cyan",
})

# 提示符: [+] 信息  [*] 进行中  [ok] 完成  [!] 警告  [-] 错误  [?] 询问
console = Console(theme=THEME, highlight=False)
err_console = Console(theme=THEME, stderr=True, highlight=False)


def txt(value: Any) -> Text:
    """把任意值变成不做 markup 解析的 Text (表格 / 面板里放动态内容时用)."""
    return Text(str(value))


def styled(markup: str) -> Text:
    """固定样式的 Text (内容由代码写死时用; 动态值请走 txt())."""
    return Text.from_markup(markup)


def link(value: Any, url: str) -> Text:
    """可点击的超链接 (终端不支持时退化为普通文本)."""
    return Text(str(value), style=f"link {url}")


def print(message: Any = "", **kwargs: Any) -> None:  # noqa: A001
    console.print(message, **kwargs)


def info(message: Any) -> None:
    console.print(f"[info]\\[+][/info] {escape(str(message))}")


def step(message: Any) -> None:
    console.print(f"[step]\\[*][/step] {escape(str(message))}")


def done(message: Any) -> None:
    console.print(f"[ok]\\[ok][/ok] {escape(str(message))}")


def warn(message: Any) -> None:
    err_console.print(f"[warn]\\[!][/warn] {escape(str(message))}")


def error(message: Any, code: int = 1) -> NoReturn:
    err_console.print(f"[err]\\[-][/err] {escape(str(message))}")
    raise SystemExit(code)


def rule(title: str = "") -> None:
    console.rule(f"[key]{escape(title)}[/key]" if title else "")


def panel(body: Any, title: str = "", border: str = "cyan") -> None:
    console.print(Panel(body, title=f"[key]{escape(title)}[/key]" if title else None,
                        border_style=border, expand=False))


def table(*columns: str, title: str = "") -> Table:
    """建一个统一样式的表格; 单元格请用 txt() / styled() 包住."""
    t = Table(title=title or None, title_justify="left", title_style="title",
              header_style="key", border_style="dim", pad_edge=False, expand=False)
    for name in columns:
        t.add_column(name, overflow="fold")
    return t


def hint(message: Any) -> None:
    """次要提示: 缩进 + 暗淡, 跟在错误/结果后面."""
    console.print(f"    [dim]{escape(str(message))}[/dim]")


def columns(items: Sequence[str], title: str = "", width: int = 26) -> None:
    """多列排布的清单 (模板名 / 标签等); rich.columns 按需导入."""
    from rich.columns import Columns

    if title:
        console.print(f"[title]{escape(title)}[/title]")
    console.print(Columns(sorted(items), width=width, padding=(0, 2), expand=False))


def human_size(n: float) -> str:
    """字节数 -> 人类可读大小."""
    units = ("B", "KB", "MB", "GB", "TB")
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{n:.0f} {units[i]}" if i == 0 else f"{n:.1f} {units[i]}"


def ask(question: str, default: bool | None = None) -> bool:
    """询问 y/n; 非交互环境使用 default(没有 default 视为 False)."""
    if not sys.stdin.isatty():
        return bool(default)
    hint_text = " [Y/n] " if default is True else " [y/N] " if default is False else " [y/n] "
    try:
        answer = console.input(f"[step]\\[?][/step] {escape(question)}{hint_text}").strip()
    except (EOFError, KeyboardInterrupt):
        console.print()
        return bool(default)
    if not answer and default is not None:
        return default
    return answer.lower() in ("y", "yes", "是", "对", "1")


def is_terminal() -> bool:
    """当前是否交互终端 (决定要不要画进度条 / 转圈)."""
    return console.is_terminal


PICKER_STYLE = (
    ("qmark", "fg:cyan bold"),
    ("question", "bold"),
    ("pointer", "fg:cyan bold"),
    ("highlighted", "fg:cyan bold"),
    ("selected", "fg:cyan"),
    ("answer", "fg:cyan bold"),
    ("instruction", "fg:#808080"),
    ("search_success", "fg:cyan"),
    ("search_none", "fg:red italic"),
    ("separator", "fg:#808080"),
    ("disabled", "fg:#808080 italic"),
)
MAX_VISIBLE = 5  # 交互列表最多同时渲染几行, 超出的部分靠上下键滚动


def _picker(multi: bool, message: str, labels: Sequence[str], instruction: str) -> Any:
    """建一个 questionary 选择器 (列表窗口压到 MAX_VISIBLE 行, 打字即筛选).

    questionary 会连带拉进 prompt_toolkit (导入约 2 秒), 所以只在这里延迟加载,
    普通命令不必付这份启动开销.
    """
    import questionary
    from prompt_toolkit.layout.dimension import LayoutDimension
    from questionary.prompts.common import InquirerControl

    build = questionary.checkbox if multi else questionary.select
    question = build(
        message,
        choices=[questionary.Choice(title=label, value=i) for i, label in enumerate(labels)],
        instruction=instruction or None,
        style=questionary.Style(PICKER_STYLE),
        use_search_filter=True,
        use_jk_keys=False,  # 搜索优先: j/k 让位给筛选输入
    )
    height = LayoutDimension.exact(min(len(labels), MAX_VISIBLE))
    for window in question.application.layout.find_all_windows():
        if isinstance(window.content, InquirerControl):
            window.height = height  # 超出部分由 prompt_toolkit 随光标滚动
    return question.ask()  # Ctrl+C -> None


def select(message: str, labels: Sequence[str], *, instruction: str = "") -> int | None:
    """上下键单选, 直接打字即筛选; 返回下标, 中断返回 None."""
    return _picker(False, message, labels, instruction)


def check(message: str, labels: Sequence[str], *, instruction: str = "") -> list[int] | None:
    """上下键多选 (空格勾选), 直接打字即筛选; 返回下标 (升序), 中断返回 None."""
    picked = _picker(True, message, labels, instruction)
    return None if picked is None else sorted(picked)


def progress() -> Progress:
    """带速率与剩余时间的下载进度条 (rich.progress 按需导入)."""
    from rich.progress import (BarColumn, DownloadColumn, Progress, SpinnerColumn,
                               TextColumn, TimeRemainingColumn, TransferSpeedColumn)

    return Progress(
        SpinnerColumn(style="step"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=None, complete_style="ok", finished_style="ok"),
        DownloadColumn(binary_units=True),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=True,
    )


@contextmanager
def spinner(message: str) -> Iterator[None]:
    """长时间子进程 (clone / ls-remote) 的转圈提示; 非交互环境退化为普通输出."""
    if console.is_terminal:
        with console.status(f"[step]{escape(message)}[/step]", spinner="dots"):
            yield
    else:
        step(message)
        yield


_CHUNK = 1 << 17  # 128 KiB: 减少读写循环次数


def save_stream(resp: Any, dest_path: str, label: str, total: int = 0, *,
                start: int = 0, append: bool = False) -> int:
    """把 HTTP 响应流写入文件, 交互终端显示进度条; 返回本次写入的字节数.

    start/append 用于断点续传: 文件已有 start 字节时以 "ab" 追加, 进度条从 start 起算。
    """
    size = total or _response_total(resp, start)
    mode = "ab" if append else "wb"
    if console.is_terminal:
        with progress() as bar:
            task = bar.add_task(escape(label), total=size or None, completed=start)
            return _copy(resp, dest_path, lambda n: bar.advance(task, n), mode)
    step(f"下载 {label}" + (f" ({human_size(size)})" if size else "")
         + (f" [续传 {human_size(start)}]" if start else ""))
    return _copy(resp, dest_path, None, mode)


def _response_total(resp: Any, start: int) -> int:
    """完整文件大小: Content-Range 的总量优先, 否则 start + Content-Length."""
    try:
        content_range = resp.headers.get("Content-Range") or ""
    except AttributeError:
        content_range = ""
    if "/" in content_range:
        try:
            return int(content_range.rsplit("/", 1)[1])
        except ValueError:
            pass
    return start + _content_length(resp)


def _content_length(resp: Any) -> int:
    try:
        return int(resp.headers.get("Content-Length") or 0)
    except (AttributeError, TypeError, ValueError):
        return 0


def _copy(resp: Any, dest_path: str, on_chunk: Any, mode: str = "wb") -> int:
    written = 0
    with open(dest_path, mode) as f:
        while chunk := resp.read(_CHUNK):
            f.write(chunk)
            written += len(chunk)
            if on_chunk:
                on_chunk(len(chunk))
    return written