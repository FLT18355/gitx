# gitx v1.0.6 发布说明

## 🚀 新增: 召唤守护进程 (低配机提速, 默认关闭)

Python 每跑一条命令都要重新导入 typer / rich 那一大堆模块 (低配机上 1-2 秒, 占了短命令的大半耗时)。
`daemon = true` 打开后, 运行**任意** gitx 命令时若发现后台没有守护进程, 就顺手拉起一个: 它先把这些
模块导入好, 之后的命令把"参数 + 工作目录 + 环境变量 + 标准输入输出"交给它, 由它 **fork 一个已经
预热的子进程**执行 —— 省掉重复导入, 而每条命令仍跑在自己的进程里 (状态不互相污染, Ctrl+C 只影响当次)。

```bash
gitx config set daemon true    # 打开 (之后第一条命令会自动召唤)
gitx daemon                    # 看状态: 配置 / 进程 / 套接字 / 空闲退出 / 实际配色
gitx daemon start|stop|restart
```

细节: 走 `~/.cache/gitx/daemon.sock` (Unix 域套接字, 不占端口、不监听网络); 空闲 300 秒自己退出,
不留常驻进程; 升级后版本号变了会自动回退本地执行; 起不来或半路断掉都静默回退 —— 最坏只是没变快,
功能不受影响 (原因见 `~/.cache/gitx/daemon.log`)。**默认关闭**, 不开启时行为与上一版完全一致。

## 🎨 配色跟随终端 (`palette`)

开了守护进程后 `palette = auto` 会**改用终端自己的 16 色调色板** (ANSI 名而不是 24 位 hex),
低配终端不必为真彩色付渲染开销; 想固定就 `gitx config set palette mocha|terminal`。
所有交互选择器、表格、提示符都跟着换, 只是颜色来源不同。

## 💾 新增: 缓存 (`~/.cache/gitx`, 默认开)

把可再生的网络结果记在 `~/.cache/gitx`, 少跑一趟网络也少用一次 API 限额: 目前记的是 GitHub API 的
只读响应 (仓库概览 / 搜索 / 发布列表, 默认 5 分钟; `cache_ttl` 可调) 与远端默认分支探测 (1 小时)。
写操作 (如发布发行版) 之后缓存自动作废。

```bash
gitx cache             # 缓存目录 + 占用 + 条目数
gitx cache list        # 明细: 缓存键 / 写入时间 / 有效期 / 状态
gitx cache prune       # 只清已过期的      gitx cache clear   # 全清
```

## ⚙️ 更多常用配置

新增 8 项可直接改的配置 (都真的生效, 不是摆设):

| 键 | 默认 | 作用 |
| --- | --- | --- |
| `daemon` | `false` | 召唤守护进程 |
| `daemon_idle` | `300` | 守护进程空闲多少秒退出 |
| `palette` | `auto` | 配色: `auto` / `terminal` / `mocha` |
| `cache` | `true` | 启用 `~/.cache/gitx` 缓存 |
| `cache_ttl` | `300` | 接口结果缓存秒数 (`0` = 不缓存) |
| `remote` | `origin` | 默认远程名 (`info` / `url` / `web` / `push` 不带 `-r` 时用) |
| `search_limit` | `10` | `gitx search` 默认条数 |
| `repos_limit` | `30` | `gitx repos` 默认条数 |

## 🔎 `gitx search`: 交互式搜索

不给关键词 (或 `-i`) 就进交互界面: 问一次搜索词 -> 结果表 -> 上下键挑一个 ->
**下载 / 看仓库概览 / 打开网页**; 挑完能接着挑, 想换词就选「换个关键词再搜」。

## 🗂️ `gitx repos -q`: 仓库也能搜

`-q/--search` 走 `gh search repos`, **搜得到全部** (不再受 `-n` 的"只取前几个"限制);
挑选器底部也加了一条「用关键词搜全部仓库」。

## 🐛 修复

- **中文打不进选择器**: questionary 的"打字即筛选"只绑了 ASCII, 中文按键会被它自己的
  "Disallow inserting other text" 丢弃 —— 「归档 / 下载 / 搜索」这类中文项其实筛不了。现在中文也能当筛选词。
- **裸 `gitx` 欢迎页不再画表格**: 换成无边框对齐两列, 窄终端里说明折行缩进到命令列之后。

## 📚 文档

README 只留用户向内容; 实现要点 / 源码结构 / 开发约定移到 `doc/开发.md`, 发版步骤移到
`doc/发布流程.md`, 并在显眼处写明"**按需读, 不要通读**"。

## 📦 安装/升级

```bash
uv tool install gitx-1.0.6-py3-none-any.whl    # 方式 1: wheel (带 gitx upgrade 自更新)
uv tool install .                              # 方式 2: 源码
gitx upgrade                                   # 已经是 v1.0.5 及以后: 直接自更新

# 验证
gitx --version              # 应输出 gitx 1.0.6
gitx daemon                 # 守护进程状态 (默认未开启)
gitx config list            # 看新增的配置项
gitx search                  # 交互式搜索 (需要终端)
```

## 🔗 相关

- 源码: https://github.com/FLT18355/gitx/tree/v1.0.6
- 完整变更: `git log v1.0.6-pre3..v1.0.6 --oneline`

---

*发布于: 2026-10-18*

<!-- 发布流程 (版本号双改 -> 构建 -> tag -> 建发行版 -> 上传后自检) 见 doc/发布流程.md -->