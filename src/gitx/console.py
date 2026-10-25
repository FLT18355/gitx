"""终端输出: 基于 rich 的统一控制台 (语义化输出 / 表格 / 进度条 / 交互).

所有函数都会对动态文本做 markup 转义, 因此仓库名、文件名里的 `[]` 等字符不会
被 rich 当成样式标签; 需要自己写样式的场合请直接用 `console.print` 或 `txt()`.

启动速度: rich.progress / rich.prompt / questionary 都改为按需导入 —— 它们是
重依赖 (合计约 2.3 秒), 只有下载与交互挑选才用得上。
"""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any, NoReturn

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

if TYPE_CHECKING:  # 仅供类型检查, 运行时不导入
    from rich.progress import Progress

# Catppuccin Mocha 官方调色板 (https://catppuccin.com/palette) —— 全项目统一取色
MOCHA: dict[str, str] = {
    "base": "#1e1e2e", "mantle": "#181825", "crust": "#11111b",
    "text": "#cdd6f4", "subtext1": "#bac2de", "subtext0": "#a6adc8",
    "overlay2": "#9399b2", "overlay1": "#7f849c", "overlay0": "#6c7086",
    "surface2": "#585b70", "surface1": "#45475a", "surface0": "#313244",
    "rosewater": "#f5e0dc", "flamingo": "#f2cdcd", "pink": "#f5c2e7",
    "mauve": "#cba6f7", "red": "#f38ba8", "maroon": "#eba0ac",
    "peach": "#fab387", "yellow": "#f9e2af", "green": "#a6e3a1",
    "teal": "#94e2d5", "sky": "#89dceb", "sapphire": "#74c7ec",
    "blue": "#89b4fa", "lavender": "#b4befe",
}

# 语义命名 -> Catppuccin Mocha 颜色 (整个 CLI 只认语义名, 主题集中在这里换肤)
THEME = Theme({
    "info": MOCHA["green"],
    "step": MOCHA["sky"],
    "warn": MOCHA["yellow"],
    "err": f"bold {MOCHA['red']}",
    "ok": f"bold {MOCHA['green']}",
    "key": f"bold {MOCHA['blue']}",
    "num": f"bold {MOCHA['yellow']}",
    "option": f"bold {MOCHA['peach']}",
    "dim": MOCHA["overlay0"],
    "title": f"bold {MOCHA['mauve']}",
    "hash": MOCHA["peach"],
    "graph": MOCHA["green"],
    "branch": f"bold {MOCHA['sapphire']}",
    "tag": MOCHA["pink"],
    "head": f"bold {MOCHA['mauve']}",
    "date": MOCHA["overlay1"],
    "border": MOCHA["surface1"],
})

# 同样的语义名 -> 终端自己的 16 色调色板 (不带 hex): 颜色由用户终端主题决定。
# 低配终端 / 追求"和其他命令行工具一个色系"时用它 (gitx config set palette terminal)。
TERMINAL_THEME = Theme({
    "info": "green",
    "step": "cyan",
    "warn": "yellow",
    "err": "bold red",
    "ok": "bold green",
    "key": "bold blue",
    "num": "bold yellow",
    "option": "yellow",
    "dim": "bright_black",
    "title": "bold magenta",
    "hash": "yellow",
    "graph": "green",
    "branch": "bold cyan",
    "tag": "magenta",
    "head": "bold magenta",
    "date": "bright_black",
    "border": "bright_black",
})

# 当前配色 (mocha = 内置真彩色, terminal = 终端调色板); 供面板边框 / 选择器取色
_PALETTE = "mocha"

# 提示符: [+] 信息  [*] 进行中  [ok] 完成  [!] 警告  [-] 错误  [?] 询问
console = Console(theme=THEME, highlight=False)
err_console = Console(theme=THEME, stderr=True, highlight=False)


def apply_palette(mode: str) -> None:
    """切换配色: mocha = 内置 Catppuccin 真彩色, terminal = 用终端自己的调色板.

    只推一次 (每进程只会调用一次): 推过的主题会盖住构造时的 THEME, 语义名不变,
    因此所有调用点一行都不用改。
    """
    global _PALETTE

    if mode == "terminal":
        _PALETTE = "terminal"
        theme = TERMINAL_THEME
    else:
        _PALETTE = "mocha"
        theme = THEME
    for target in (console, err_console):
        with contextlib.suppress(Exception):  # 老的 stack 空时 pop 会报错, 无妨
            target.pop_theme()
        target.push_theme(theme)


def rebind() -> None:
    """按**当前**的文件描述符重建控制台 —— 守护进程 fork 出的子进程必须调它.

    rich 在 Console 构造时就把"是不是终端 / 多少列 / 支持几种颜色"定死了: 守护进程自己的
    stdout/stderr 指向日志文件, 于是它导入时建出来的 Console 记住的是"没有终端 + 80 列 +
    不带颜色"; fork 继承过来后**哪怕把 fd 换成客户端的终端**, rich 仍按老结论渲染 ——
    表现就是颜色掉光、表格按 80 列折行。重建对象才能让它重新检测。
    """
    global console, err_console

    console = Console(theme=THEME, highlight=False)
    err_console = Console(theme=THEME, stderr=True, highlight=False)
    apply_palette(_PALETTE)  # 保留当前配色, 并把主题推到新对象上


def accent() -> str:
    """主强调色 (面板边框 / 选择器指针): 跟随当前配色."""
    return "bright_blue" if _PALETTE == "terminal" else MOCHA["blue"]



def apply_color(mode: str) -> None:
    """按配置 color 调整彩色输出: never 关闭颜色 (auto = 用 Rich 的自动检测).

    影响的是 gitx 自己的输出; help / typer 的错误页由 typer 渲染, 不受此影响。
    想强制彩色可设环境变量 FORCE_COLOR=1 (Rich 原生支持); 关闭则 NO_COLOR=1。
    """
    if str(mode).strip().lower() == "never":
        console.no_color = True
        err_console.no_color = True
    elif str(mode).strip().lower() == "auto":
        console.no_color = False
        err_console.no_color = False


def _assume_yes() -> bool:
    """配置 assume_yes=true 时所有确认一律视为同意 (= 处处 -y)."""
    from . import config  # 延迟导入: config 依赖 console, 避免循环导入

    return bool(config.load().get("assume_yes"))

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


def panel(body: Any, title: str = "", border: str = "") -> None:
    console.print(Panel(body, title=f"[key]{escape(title)}[/key]" if title else None,
                        border_style=border or accent(), expand=False))


def table(*columns: str, title: str = "") -> Table:
    """建一个统一样式的表格; 单元格请用 txt() / styled() 包住."""
    t = Table(title=title or None, title_justify="left", title_style="title",
              header_style="key", border_style="border", pad_edge=False, expand=False)
    for name in columns:
        t.add_column(name, overflow="fold")
    return t


def hint(message: Any) -> None:
    """次要提示: 缩进 + 暗淡, 跟在错误/结果后面."""
    console.print(f"    [dim]{escape(str(message))}[/dim]")


def quicklist(rows: Sequence[tuple[str, str]], title: str = "") -> None:
    """速查清单: 左边命令 (key 色), 右边说明; 只有对齐, 没有边框.

    用 rich 的"无框表格"(box=None) 而不是手写对齐: 中文宽字符的列宽和窄终端里的
    折行都由 rich 算好, 折行后的续行会自动缩进到说明列, 不会回到第 0 列;
    但画面上没有一根竖线/横线, 因此读起来是一段说明而不是一张表。
    """
    grid = Table(box=None, show_header=False, pad_edge=False, expand=False, padding=(0, 2, 0, 0))
    grid.add_column(no_wrap=True)
    grid.add_column(overflow="fold")
    for cmd, desc in rows:
        grid.add_row(Text(f"  {cmd}", style="key"), Text(desc))
    if title:
        console.print(f"[title]{escape(title)}[/title]")
    console.print(grid)


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
    """询问 y/n; 非交互环境使用 default(没有 default 视为 False).

    配置 assume_yes=true 时一律视为同意 (= 处处 -y), 跳过所有确认;
    非交互(管道/脚本)且未开 assume_yes 时仍按 default 走。
    """
    if _assume_yes():
        return True
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
    ("qmark", f"fg:{MOCHA['mauve']} bold"),
    ("question", f"fg:{MOCHA['text']} bold"),
    ("pointer", f"fg:{MOCHA['mauve']} bold"),
    ("highlighted", f"fg:{MOCHA['mauve']} bold"),
    ("selected", f"fg:{MOCHA['green']}"),
    ("answer", f"fg:{MOCHA['blue']} bold"),
    ("instruction", f"fg:{MOCHA['overlay1']}"),
    ("search_success", f"fg:{MOCHA['green']}"),
    ("search_none", f"fg:{MOCHA['red']} italic"),
    ("separator", f"fg:{MOCHA['overlay1']}"),
    ("disabled", f"fg:{MOCHA['overlay0']} italic"),
)

# 终端配色版: 用 prompt_toolkit 认的颜色名 (ansixxx / default), 颜色交给终端主题。
# 注意命名与 rich 不同 —— rich 的 bright_black 在这里叫 ansibrightblack, 写错了会直接抛
# "Wrong color format" (questionary 建 Style 时就会炸)。
PICKER_STYLE_TERMINAL = (
    ("qmark", "fg:ansimagenta bold"),
    ("question", "fg:default bold"),
    ("pointer", "fg:ansimagenta bold"),
    ("highlighted", "fg:ansimagenta bold"),
    ("selected", "fg:ansigreen"),
    ("answer", "fg:ansiblue bold"),
    ("instruction", "fg:ansibrightblack"),
    ("search_success", "fg:ansigreen"),
    ("search_none", "fg:ansired italic"),
    ("separator", "fg:ansibrightblack"),
    ("disabled", "fg:ansibrightblack italic"),
)
MAX_VISIBLE = 5  # 交互列表最多同时渲染几行, 超出的部分靠上下键滚动


def picker_style() -> tuple[tuple[str, str], ...]:
    """选择器的配色 (跟随当前 palette, 见 apply_palette)."""
    return PICKER_STYLE_TERMINAL if _PALETTE == "terminal" else PICKER_STYLE


def _any_char_bindings(control: Any) -> Any:
    """让中文也能当筛选输入 (questionary 只认 ASCII 的按键).

    questionary 的筛选只绑了 string.printable: 中文按键会落到它自己的 Keys.Any
    绑定("Disallow inserting other text")上被丢掉, 于是"打字即筛选"对中文其实无效
    (归档 / 下载 / 搜索 这些字打不进去)。这里补一份 Keys.Any 绑定并放在它前面 ——
    同优先级时先注册者先匹配, 因此字符会喂给同一个筛选逻辑。
    """
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.keys import Keys

    bindings = KeyBindings()

    @bindings.add(Keys.Any, eager=True)
    def _filter(event: Any) -> None:
        data = event.data
        if data and data.isprintable():  # 控制字符 (Ctrl+A 之类) 不进筛选词
            control.add_search_character(data)

    return bindings


def _picker(multi: bool, message: str, labels: Sequence[str], instruction: str,
            checked: Sequence[bool] | None = None) -> Any:
    """建一个 questionary 选择器 (列表窗口压到 MAX_VISIBLE 行, 打字即筛选).

    questionary 会连带拉进 prompt_toolkit (导入约 2 秒), 所以只在这里延迟加载,
    普通命令不必付这份启动开销. checked 给多选用, 决定各项初始是否已勾选.
    """
    import questionary
    from prompt_toolkit.key_binding import merge_key_bindings
    from prompt_toolkit.layout.dimension import LayoutDimension
    from questionary.prompts.common import InquirerControl

    build = questionary.checkbox if multi else questionary.select
    flags = list(checked or [])
    question = build(
        message,
        choices=[questionary.Choice(title=label, value=i,
                                    checked=bool(flags[i]) if i < len(flags) else False)
                 for i, label in enumerate(labels)],
        instruction=instruction or None,
        style=questionary.Style(picker_style()),
        use_search_filter=True,
        use_jk_keys=False,  # 搜索优先: j/k 让位给筛选输入
    )
    height = LayoutDimension.exact(min(len(labels), MAX_VISIBLE))
    control = None
    for window in question.application.layout.find_all_windows():
        if isinstance(window.content, InquirerControl):
            window.height = height  # 超出部分由 prompt_toolkit 随光标滚动
            control = window.content
    if control is not None:
        question.application.key_bindings = merge_key_bindings(
            [_any_char_bindings(control), question.application.key_bindings])
    return question.ask()  # Ctrl+C -> None


def select(message: str, labels: Sequence[str], *, instruction: str = "") -> int | None:
    """上下键单选, 直接打字即筛选; 返回下标, 中断返回 None."""
    return _picker(False, message, labels, instruction)


_STREAM_MORE = object()  # 翻页选择器末尾的"继续加载"占位项


def select_stream(message: str, fetch: Callable[[int, int], Sequence[Any]], *,
                  page_size: int = 10, label: Callable[[Any], str] = str,
                  instruction: str = "") -> Any | None:
    """上下键单选 + 按需翻页: 光标越过已加载的最后一条时自动再取一页.

    fetch(offset, count) 返回下一批 (返回空 / 不足一批 = 到底了). 列表末尾会多一条
    "↓ 继续加载更多": 选中它 (= 继续按下键) 就调用 fetch 取下一批, 因此列表很大时
    不必一次拉完, 也不会为了"看看后面是什么"而多等一趟网络。
    """
    import questionary
    from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.layout.dimension import LayoutDimension
    from questionary.prompts.common import Choice, InquirerControl

    items: list[Any] = []
    exhausted = False

    def fetch_page() -> int:
        nonlocal exhausted
        batch = list(fetch(len(items), page_size))
        if not batch:
            exhausted = True
            return 0
        items.extend(batch)
        if len(batch) < page_size:
            exhausted = True
        return len(batch)

    if not fetch_page():
        return None

    def choice(index: int) -> Any:
        return Choice(title=label(items[index]), value=index)

    choices = [choice(i) for i in range(len(items))]
    if not exhausted:
        choices.append(Choice(title="↓ 继续加载更多 ...", value=_STREAM_MORE))

    question = questionary.select(
        message, choices=choices, instruction=instruction or "[↑↓] 选择  [回车] 确认",
        style=questionary.Style(picker_style()),
        use_search_filter=False, use_jk_keys=False, show_description=False,
    )
    control = window = None
    for win in question.application.layout.find_all_windows():
        if isinstance(win.content, InquirerControl):
            control, window = win.content, win
            break
    if control is None:  # 理论上不会发生; 退化成一次性选择
        index = question.ask()
        return None if index is None else items[index]

    def resize() -> None:
        window.height = LayoutDimension.exact(min(len(control.choices), MAX_VISIBLE))

    def load_more(event: Any) -> None:
        old = len(items)
        if fetch_page():
            new = [choice(i) for i in range(old, len(items))]
            if control.choices and control.choices[-1].value is _STREAM_MORE:
                control.choices[-1:-1] = new
            else:
                control.choices.extend(new)
            control.pointed_at = old
        if exhausted and control.choices and control.choices[-1].value is _STREAM_MORE:
            control.choices.pop()
        control.pointed_at = max(0, min(control.pointed_at, len(control.choices) - 1))
        resize()
        event.app.invalidate()

    def move(step: int) -> None:
        control.pointed_at = max(0, min(len(control.choices) - 1, control.pointed_at + step))

    bindings = KeyBindings()

    @bindings.add(Keys.Down, eager=True)
    @bindings.add(Keys.ControlN, eager=True)
    def _down(event: Any) -> None:
        move(1)
        if control.choices[control.pointed_at].value is _STREAM_MORE:
            load_more(event)

    @bindings.add(Keys.Up, eager=True)
    @bindings.add(Keys.ControlP, eager=True)
    def _up(_event: Any) -> None:
        move(-1)

    @bindings.add(Keys.ControlM, eager=True)
    def _enter(event: Any) -> None:
        value = control.choices[control.pointed_at].value
        if value is _STREAM_MORE:
            load_more(event)
            return
        control.is_answered = True
        event.app.exit(result=value)

    resize()
    question.application.key_bindings = merge_key_bindings(
        [question.application.key_bindings, bindings])  # 后注册者优先 (prompt_toolkit 取 matches[-1])
    index = question.ask()  # Ctrl+C -> None
    return None if index is None else items[index]


def check(message: str, labels: Sequence[str], *, instruction: str = "",
          checked: Sequence[bool] | None = None) -> list[int] | None:
    """上下键多选 (空格勾选), 直接打字即筛选; checked 决定初始勾选; 返回下标 (升序), 中断返回 None."""
    picked = _picker(True, message, labels, instruction, checked)
    return None if picked is None else sorted(picked)


def text(message: str, *, default: str = "", instruction: str = "") -> str | None:
    """单行输入 (questionary, 与选择器同一套配色); 中断返回 None.

    default 表现为光标前已填好的文本 (回车即采用), 因此"改哪一项就用当前值当默认"。
    """
    import questionary

    return questionary.text(message, default=default, instruction=instruction or None,
                            style=questionary.Style(picker_style())).ask()


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
