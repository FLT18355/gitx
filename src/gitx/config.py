"""持久化配置: ~/.config/gitx/config.toml (或 $XDG_CONFIG_HOME/gitx/config.toml).

用 TOML 是为了让人能直接拿文本编辑器改 —— 带注释、可读、改完即生效。
旧的 config.json 首次加载时自动迁移为带注释的 TOML, 原文件改名 .json.bak 保留。
"""

from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path

from . import accel, console

# 默认值即类型模板: str / int / bool。新增键时在这里登记, 注释在 _COMMENTS 里写。
DEFAULTS: dict[str, object] = {
    "proxy": "v6",            # 加速源
    "release_proxy": "",      # Release 专用加速源
    "depth": 1,               # 克隆深度
    "branch": "",             # 默认分支
    "dest": "",               # 默认下载目录
    "resume": True,           # 断点续传
    "message": "日常同步更新",  # push 默认提交信息
    "sync_rebase": True,      # gitx sync 默认变基
    "token": "",              # GitHub API token
    "color": "auto",          # 彩色输出
    "assume_yes": False,      # 处处跳过确认 (= -y)
}

# 写入 TOML 时的逐行注释 (人性化的关键: 一眼看懂每项是干嘛的)
_COMMENTS: dict[str, str] = {
    "proxy": "加速源: v6 / v4 / gh-proxy / off / 自定义 https://... (拉取走它, 推送直连 GitHub)",
    "release_proxy": "Release 专用加速源; 留空 = 跟随上面的 proxy (gitx proxy release 单独管理)",
    "depth": "克隆深度: 1 = 浅克隆(快), 0 = 完整克隆(带全部历史)",
    "branch": "下载时未指定分支则用它; 留空 = 探测远端默认分支(main/master)",
    "dest": "默认下载目录 (支持 ~ ); 留空 = 当前目录",
    "resume": "断点续传: true 时中断的下载留下 .part, 重跑接着下",
    "message": "gitx push / sync 不带备注时用的提交信息",
    "sync_rebase": "gitx sync 先拉再推时用变基(true)还是合并(false)",
    "token": "GitHub API token, 把限额从 60 提到 5000 次/小时 (显示时自动打码)",
    "color": "彩色输出: auto(自动检测) / never(关闭颜色)",
    "assume_yes": "处处跳过确认, 相当于每条命令都带 -y (危险操作仍建议人工确认)",
}

# 类型校验用的元数据
_BOOL_KEYS = frozenset(k for k, v in DEFAULTS.items() if isinstance(v, bool))
_INT_KEYS = frozenset(k for k, v in DEFAULTS.items() if isinstance(v, int) and not isinstance(v, bool))
_CHOICES: dict[str, tuple[str, ...]] = {"color": ("auto", "never")}

_BOOL_WORDS: dict[str, bool] = {
    "true": True, "yes": True, "on": True, "1": True, "y": True, "是": True, "对": True,
    "false": False, "no": False, "off": False, "0": False, "n": False, "否": False, "不": False,
}

# 同一个键的"配置非法"警告在一次进程里只说一遍, 避免反复刷屏
_WARNED: set[str] = set()


def config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    return Path(xdg) / "gitx" if xdg else Path.home() / ".config" / "gitx"


def config_path() -> Path:
    return config_dir() / "config.toml"


def legacy_path() -> Path:
    """旧版 JSON 配置 (用于自动迁移)."""
    return config_dir() / "config.json"


def cache_dir() -> Path:
    """缓存目录 (~/.cache/gitx): 存放可再生的数据, 删掉也不影响使用."""
    xdg = os.environ.get("XDG_CACHE_HOME")
    return Path(xdg) / "gitx" if xdg else Path.home() / ".cache" / "gitx"


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    word = str(value).strip().lower()
    if word in _BOOL_WORDS:
        return _BOOL_WORDS[word]
    raise ValueError(f"不是布尔值: {value} (用 true / false, 或 yes / no)")


def normalize(key: str, value: object) -> object:
    """校验并转换一个配置值 (命令行 gitx config set 用); 非法值抛 ValueError.

    bool 键接受 true/false/yes/no/1/0/是/否; int 键接受整数;
    proxy / release_proxy 顺便用 accel.resolve 验证是不是合法加速源。
    """
    if key not in DEFAULTS:
        raise ValueError(f"未知配置键: {key} (可用: {', '.join(DEFAULTS)})")
    default = DEFAULTS[key]
    if isinstance(default, bool):
        return _to_bool(value)
    if isinstance(default, int):
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{key} 必须是整数") from None
    text = str(value)
    if key in _CHOICES and text not in _CHOICES[key]:
        raise ValueError(f"{key} 只能是 {' / '.join(_CHOICES[key])}")
    if key in ("proxy", "release_proxy") and text:
        accel.resolve(text)  # 非法加速源在这里抛 ValueError
    return text


def _sanitize_loaded(key: str, value: object) -> object:
    """读到的值按声明类型归一; 手改坏了不崩, 回退默认值并警告一次."""
    default = DEFAULTS[key]
    try:
        if isinstance(default, bool):
            return _to_bool(value)
        if isinstance(default, int):
            return int(value)
        return str(value)
    except (TypeError, ValueError):
        if key not in _WARNED:
            _WARNED.add(key)
            console.warn(f"配置里的 {key} 值非法 ({value!r}), 已回退默认 {default!r}")
        return default


def _validate_proxy_keys(data: dict) -> None:
    """proxy / release_proxy 是非法加速源时, 警告一次并回退默认 (不影响其余功能)."""
    for key in ("proxy", "release_proxy"):
        value = str(data.get(key) or "")
        if not value:
            continue
        try:
            accel.resolve(value)
        except ValueError:
            if key not in _WARNED:
                _WARNED.add(key)
                console.warn(f"配置里的 {key}={value!r} 不是有效加速源, 已回退默认 {DEFAULTS[key]!r}")
            data[key] = DEFAULTS[key]


def _migrate_legacy() -> None:
    """旧版 config.json 自动迁移成带注释的 config.toml (原文件改名 .json.bak)."""
    legacy = legacy_path()
    if not legacy.exists():
        return
    try:
        data = json.loads(legacy.read_text("utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}
    if isinstance(data, dict):
        save(data)
    try:
        legacy.replace(legacy.with_name("config.json.bak"))
    except OSError:
        pass  # 旧文件动不了也不影响 (TOML 已经写好了)


def _read_toml(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text("utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return {}


def load() -> dict:
    """读配置 -> 合并默认值。TOML 不存在但旧 JSON 在时会自动迁移。"""
    path = config_path()
    if not path.exists():
        _migrate_legacy()
    raw = _read_toml(path)
    data: dict = {**DEFAULTS}
    for key in DEFAULTS:
        if key in raw:
            data[key] = _sanitize_loaded(key, raw[key])
    # 用户多写的键 (如 proxy install 记的 installed_prefix) 原样保留
    for key, value in raw.items():
        if key not in DEFAULTS:
            data[key] = value
    _validate_proxy_keys(data)
    return data


def toml_value(value: object) -> str:
    """把单个值序列化成 TOML 片段 (str/int/bool 足够覆盖本项目)。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    # 用 json.dumps 产出合法的 TOML 基本字符串 (双引号 + 转义)
    return json.dumps(str(value), ensure_ascii=False)


def _display_width(text: str) -> int:
    """终端显示宽度: 中文/全角算 2 列 —— 注释对齐要按它算, 不按字符数。"""
    import unicodedata  # noqa: PLC0415  只在写配置时用

    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _dump(data: dict) -> str:
    """带注释、按组分段的 TOML 文本 —— 注释是给人看的, 改完即生效。"""
    path = config_path()
    lines = [
        "# gitx 配置 (TOML) —— 可直接用文本编辑器修改, 改完即生效; 注释不会丢。",
        f"# 文件: {path}",
        "# 查看: gitx config   |   编辑: gitx config edit   |   路径: gitx config path",
        "",
    ]
    groups = [
        ("加速", ("proxy", "release_proxy")),
        ("下载", ("depth", "branch", "dest", "resume")),
        ("同步", ("message", "sync_rebase")),
        ("API", ("token",)),
        ("界面", ("color", "assume_yes")),
    ]
    keys_done: set[str] = set()
    for title, keys in groups:
        lines.append(f"# ── {title} ──")
        for key in keys:
            keys_done.add(key)
            line = f"{key} = {toml_value(data.get(key, DEFAULTS[key]))}"
            comment = _COMMENTS.get(key)
            if comment:
                pad = max(1, 30 - _display_width(line))
                line = f"{line}{' ' * pad}# {comment}"
            lines.append(line)
        lines.append("")
    extra = [(k, v) for k, v in data.items() if k not in keys_done]
    if extra:
        lines.append("# ── 内部记录 (一般不要手改) ──")
        for key, value in extra:
            lines.append(f"{key} = {toml_value(value)}")
        lines.append("")
    return "\n".join(lines)


def save(data: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    merged = {**DEFAULTS, **{k: v for k, v in data.items()}}
    path.write_text(_dump(merged), "utf-8")


def ensure_file() -> None:
    """配置文件不存在就生成带注释的模板 (首次运行 gitx config 时让用户有东西可看)。"""
    if not config_path().exists():
        save(load())


def default_dest() -> str:
    """配置的默认下载目录 (展开 ~); 未设置返回空串 (= 当前目录)。"""
    dest = str(load().get("dest") or "").strip()
    return os.path.expanduser(dest) if dest else ""


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
