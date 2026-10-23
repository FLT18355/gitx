---
name: gitx
version: 1.1.0-pre1
description: 给中国人用的 GitHub 加速与同步工具 —— 下载 / 同步 / 加速 / 分支 / 暂存 / 标签 / 提交 / 改动 / 发行版 / Actions / 账号 / 我的仓库，一条命令搞定
author: FLT18355
repository: https://github.com/FLT18355/gitx
license: MIT
tags: [github, git, cli, download, sync, acceleration]
---

# gitx Skill — GitHub 加速同步工具

> 🇨🇳 专为国内用户设计：拉取走加速镜像，推送直连 GitHub，一条命令搞定所有操作。

## 快速上手 ⚡

```bash
# 1. 安装（两种方式，任选）
# ① wheel（推荐；要 gitx upgrade 自更新就用这个，文件名带版本号）
uv tool install gitx-X.Y.Z-py3-none-any.whl
# ② 源码
git clone https://github.com/FLT18355/gitx.git && cd gitx && uv tool install .

# 2. 环境自检
gitx doctor

# 3. 开始使用（示例）
gitx https://github.com/user/repo    # 加速克隆
gitx user/repo                       # 同上: owner/repo 简写, 不必打 https://github.com/
gitx release user/repo               # 加速下载 Release
gitx sync                            # 同步当前仓库
```

> 💡 **核心思路**：所有 `gitx` 命令默认走加速镜像，只有推送（push）和 API 调用直连 GitHub。

---

## 核心特性 🌟

| 特性 | 说明 |
|------|------|
| 🚀 **默认加速** | 克隆、下载、Release 附件全部走 `https://v6.gh-proxy.org` |
| 🔀 **源智能切换** | `gitx proxy auto` 自动选择最快节点 |
| 📦 **Release 独立加速** | `release_proxy` 可单独配置，不影响其他功能 |
| 🎨 **彩色 UI** | Typer + Rich + Catppuccin Mocha 主题 |
| 📊 **进度可视化** | 下载速率、剩余时间实时显示 |
| 🔍 **交互选择** | questionary 上下键选择，打字筛选 |
| ⚡ **git 透传** | `gitx status` 等同原生 git，瞬时响应 |
| 💾 **断点续传** | 中断后重跑自动续传，不浪费流量 |
| ⚡ **召唤守护进程** | `daemon = true`（默认关）：预热进程 + fork 执行，省掉每次重付的导入开销；`palette` 顺带改用终端配色 |
| 🗃️ **缓存** | 只读 API 响应 / 默认分支探测 / `repos` 的列表与详情记在 `~/.cache/gitx`（`cache_ttl` 默认 300 秒），写操作后自动作废，`--fresh` 强制回源 |
| 🌲 **部分克隆** | 文件夹下载快 8 倍（稀疏检出） |
| 🔁 **协作一条龙** | remote / submodule / pr 全部加速 |
| 🏷️ **发行版管理** | `gitx publish` 创建 / 上传附件 / 编辑 / 删除（交给已登录的 gh） |
| 📋 **Actions 运行** | `gitx actions` 运行列表 / 详情 / 日志 / 盯 / 重跑 / 产物下载 / 手动触发（交给 gh） |
| 🔑 **账号管理** | `gitx auth` 登录态 / 登录 / 切换 / 权限 / 令牌（`token --save` 提升 API 限额） |
| 🗂️ **我的仓库** | `gitx repos` 挑/搜仓库（`-q 关键词`）→ 编辑界面（描述 / 话题 / 可见性 / 功能开关 / 归档 / 删除，交给 gh）；列表与详情走缓存，`--fresh` 回源 |
| 🔎 **交互式搜索** | `gitx search` 不写关键词 = 问关键词 → 挑一个 → 下载 / 概览 / 网页；挑选器中文也能当筛选词 |
| 🔄 **自更新** | `gitx upgrade` 查 Release 下 wheel 都走加速 |

---

## 命令速查 📋

### 📥 下载

| 命令 | 说明 |
|------|------|
| `gitx <URL>` | 仓库浅克隆到当前目录 |
| `gitx owner/repo` | 同上，链接可省成 `owner/repo`（`gitx cli/cli`） |
| `gitx <URL> -x` | 下载源码包 tar.gz（无历史，最快） |
| `gitx <URL> -X` | 下载并解压 |
| `gitx <URL>/tree/分支/路径` | 下载文件夹（部分克隆） |
| `gitx <URL>/blob/分支/路径/文件` | 下载单文件 |
| `gitx release <owner/repo>` | 交互式选择 Release 附件 |
| `gitx release <owner/repo> --tag v1.0 -a '*linux*'` | 指定标签 + 通配下载 |
| `gitx download url1 url2 -o 目录` | 批量下载多个链接 |
| `gitx download -f links.txt` | 从文件读取链接（`#` 注释，`-` 读 stdin） |

### 🏷️ 发行版管理 (发布方 · 全部交给已登录的 `gh`)

| 命令 | 说明 |
|------|------|
| `gitx publish [list]` | 列出发行版（含草稿与预发布）：标签/名称/状态/发布/创建 |
| `gitx publish --no-drafts --no-prereleases` | 只看正式版 |
| `gitx publish view [标签] [--web]` | 状态/时间/说明首行/附件清单（标签省略 = 最新） |
| `gitx publish create <标签> [附件...] -T 标题 -F 说明.md -p` | 创建发行版并上传附件（附件支持 `dist/*` 通配） |
| `gitx publish create <标签> dist/* -d` | 先建草稿（`edit --no-draft` 再正式发布） |
| `gitx publish upload <标签> <文件...> [--clobber]` | 给已有发行版补传附件 |
| `gitx publish edit <标签> [--title/--notes/--notes-file]` | 改标题与说明 |
| `gitx publish edit <标签> --no-prerelease --latest` | 预发布转正式并设为最新 |
| `gitx publish delete <标签> [--cleanup-tag] [-y]` | 删除发行版（`--cleanup-tag` 连标签一起删） |

> 写操作需要已安装并登录的 `gh`；只**下载**附件仍用 `gitx release`（只读 + 加速，不需要 gh）。
> `--repo/-R` 接受 `owner/repo` 或链接，可对任意仓库操作。

### 📋 工作流 (Actions · 全部交给已登录的 `gh`)

| 命令 | 说明 |
|------|------|
| `gitx actions [list] [-n 20]` | 最近运行：运行号 / 状态 / 工作流 / 标题 / 分支 / 触发 / 时间 |
| `gitx actions -w build.yml -b main -s failure` | 按工作流 / 分支 / 状态过滤（状态名同 gh：`queued`/`success`/`failure`…） |
| `gitx actions -e push -u 用户名 -R owner/repo` | 按触发事件 / 触发人过滤；`-R` 操作任意仓库 |
| `gitx actions view [运行号]` | 详情：标题 / 分支 / 耗时 + 作业表（留空由 gh 交互挑选） |
| `gitx actions view <运行号> --verbose` | 连每个步骤一起列出来（步骤名 + 状态 + 耗时） |
| `gitx actions view <运行号> --log-failed` | 只看失败步骤的日志（`--log` 全量，`--web` 打开网页） |
| `gitx actions watch <运行号> [--compact] [-i 5]` | 实时盯到结束（`--exit-status` 失败返回非 0） |
| `gitx actions rerun <运行号> [--failed]` | 重跑（`--failed` 只重跑失败的作业，`-j` 单个作业，`--debug`） |
| `gitx actions cancel <运行号> [--force]` | 取消运行 |
| `gitx actions download <运行号> [-D 目录] [-N 产物名] [-p 通配]` | 下载运行产物（每个产物一个子目录） |
| `gitx actions workflows [-a] [-n 50]` | 列工作流：名称 / 状态 / 路径 / 编号（`-a` 含已停用） |
| `gitx actions dispatch <工作流> [-r 分支] [-F 键=值]` | 手动触发 `workflow_dispatch`（`-F` 支持 `@文件`；`-f` 原样字符串） |

> 运行号省略时由 `gh` 弹出选择器让人挑（需要终端）；日志与 `watch` 的输出由 gh 原样打印（保留配色）。

### 🔑 账号 (gh 登录态)

| 命令 | 说明 |
|------|------|
| `gitx auth [status]` | 登录了哪些账号：主机 / 账号 / 状态 / git 协议（当前账号标出来） |
| `gitx auth --active` | 只看当前账号（`--show-token` 交给 gh 连令牌一起显示） |
| `gitx auth login [--web\|--with-token] [-p ssh\|https]` | 登录（不带选项交给 gh 交互询问；`-s` 追加权限） |
| `gitx auth logout [账号]` / `gitx auth switch [账号]` | 退出 / 切换当前账号 |
| `gitx auth refresh -s workflow` | 调整授权范围（`--remove-scopes` / `--reset-scopes`） |
| `gitx auth token [--save]` | 打印令牌；`--save` 写进 gitx 配置（API 限额 60 → 5000 次/小时） |
| `gitx auth setup-git` | 让 git 的 https 推送 / 拉取走 gh 的凭据 |

> 登录 / 退出 / 切换 / 刷新都由 `gh` 自己做交互（设备码 / 浏览器 / SSH 密钥），gitx 只透传输出；
> 没登录时 `gitx auth` 给中文提示。`--hostname` 供 GitHub Enterprise 使用。

### 🗂️ 我的仓库 (挑一个 → 编辑界面，交给 gh)

| 命令 | 说明 |
|------|------|
| `gitx repos` | ↑↓ 挑一个仓库（最多渲染 5 行，超出的随光标滚动，打字即筛选）→ 进**仓库编辑界面** |
| `gitx repos -q dotfile` | 按关键词**搜**仓库（`gh search repos`，搜得到全部，不受 `-n` 限制；挑选器底部也有一条「用关键词搜全部仓库」） |
| `gitx repos -n 5` | 只取最近 5 个仓库来挑（`-o` 看别人的仓库；`--visibility` / `-l` / `-t` / `--source` / `--fork` / `--no-archived` 过滤；`--fresh` 不吃缓存） |
| `gitx repos edit [owner/repo]` | 跳过挑选直接进编辑界面；非交互则给选项：`-d` 描述 / `-H` 主页 / `-t`·`--remove-topic` 话题 / `--visibility` / `-b` 默认分支 / `--template`+`--no-template` / `--issues`·`--wiki`·`--projects`·`--discussions` |
| `gitx repos list [-n 30]` | 表格列出仓库：仓库 / 描述 / 可见性 / ★ / 语言 / 更新 / 标记 |
| `gitx repos view [owner/repo] [--web]` | 看当前设置（描述 / 主页 / 话题 / 可见性 / 默认分支 / 功能 / 模板 / star） |
| `gitx repos clone [owner/repo] [-D 目录] [-d 深度]` | 克隆到本地（公开走加速，私有仓库交给 gh 克隆——加速镜像拉私有仓库会失败，推送仍直连） |
| `gitx repos create <名字> [--source . --push]` | 新建仓库（`-d` / `-H` / `--visibility` / `--readme` / `-g` / `--license` / `-p` 模板 / `--no-issues` / `--no-wiki` / `--team`） |
| `gitx repos fork [owner/repo] [-c]` | 复刻到自己的账号（`--org` / `--fork-name` / `--default-branch-only` / `--remote`） |
| `gitx repos rename [owner/repo] [新名字]` | 改名（新名字留空问一次） |
| `gitx repos archive\|unarchive [owner/repo]` | 归档 / 取消归档 |
| `gitx repos sync [owner/repo] [-s 源] [-b 分支] [--force]` | 与上游 / 源仓库对齐 |
| `gitx repos star\|unstar [owner/repo]` | 收藏 / 取消收藏 |
| `gitx repos set-default [owner/repo]` | 设为当前目录的默认仓库 |
| `gitx repos delete [owner/repo] [-y]` | 删除仓库（不可恢复，需要 delete_repo 权限） |

> 编辑界面每轮都重画一遍当前设置：改描述 / 主页 / 话题 / 可见性 / 默认分支 / 功能开关 / 模板 /
> 归档 / 收藏 / 改名 / 克隆 / 打开网页 / 设为默认 / 删除，选「完成」退出。
> 每项都走 `gh repo edit` 且**只带变了的参数**（描述给原样不发请求，想清空就把内容删干净再回车）；
> 改可见性先提示副作用（掉 star / 断复刻关系）并要求确认。
> 所有子命令的仓库参数都可省略 —— 省略时先弹同一个挑选器，条数由 `-n` 决定（如 `gitx repos -n 5 delete`）。
> 过滤选项写在子命令前后都生效（`gitx repos -o cli list` ≡ `gitx repos list -o cli`）。
> 列表 / 搜索 / 详情 / 分支都走缓存（`cache_ttl` 默认 300 秒），写操作后自动作废；`--fresh` 强制回源。
> 仓库多到记不住名字时用 `-q` 搜（`gh search repos`，搜得到全部）；挑选器底部也有一条「用关键词搜全部仓库」，
> 选中即可现场搜一遍再接着挑。挑选器里中文/英文都能直接打字筛选（questionary 原生只认 ASCII，gitx 补了绑定）。

### 🔄 同步

| 命令 | 说明 |
|------|------|
| `gitx push` | 提交并推送（默认信息：日常同步更新） |
| `gitx push "修复了 bug"` | 带自定义提交信息 |
| `gitx push to <URL>` | 首次关联远程并推送 |
| `gitx pull [--rebase]` | 拉取（走加速） |
| `gitx sync ["备注"]` | 先拉（变基）后推，一步到位 |
| `gitx fetch [--prune]` | 仅更新远端引用（`--prune` 清理已删除分支） |

### 🗂️ 仓库管理

| 命令 | 说明 |
|------|------|
| `gitx init <项目名> [--no-zh]` | 初始化（main 分支 + 中文友好配置） |
| `gitx info` | 仓库概览：状态/领先落后/最近提交/加速状态 |
| `gitx graph [-n 30] [--all]` | 图形化提交历史（git log 上色版） |
| `gitx tidy [--prune] [--gc [--aggressive]]` | 体检：体积/已合并分支/打包瘦身 |
| `gitx url [accel\|https\|ssh] [-r 远程]` | 查看/切换远端地址形态 |
| `gitx undo [N] [--soft\|--mixed\|--hard] [-y]` | 撤销最近 N 次提交 |

### 🌿 分支

| 命令 | 说明 |
|------|------|
| `gitx branch [-a] [-n 20]` | 分支列表：上游/领先落后/最近提交 |
| `gitx branch new <名字> [--from <标签>] [--switch]` | 新建分支 |
| `gitx switch <分支>` | 切换分支 |
| `gitx switch -c <分支>` | 新建并切换（远端同名自动建跟踪） |
| `gitx branch rename <新名> [-o <旧名>]` | 重命名分支 |
| `gitx branch delete <分支> [--force] [-r]` | 删除本地或远端分支 |
| `gitx branch upstream [分支] [--set <上游>] [--unset]` | 查看/设置/取消上游 |
| `gitx merge <分支> [--no-ff] [--squash]` | 合并（冲突时给出解决提示） |
| `gitx rebase <分支> [-i] [--continue/--skip/--abort]` | 变基 |

### 💾 暂存与标签

| 命令 | 说明 |
|------|------|
| `gitx stash [list]` | 查看暂存列表 |
| `gitx stash save <备注> [-u]` | 保存暂存（`-u` 包含未跟踪文件） |
| `gitx stash show [-p]` | 查看暂存内容 |
| `gitx stash pop [N]` | 应用并删除最栈暂存 |
| `gitx stash apply [N]` | 仅应用暂存（不删除） |
| `gitx stash drop [N]` | 删除指定暂存 |
| `gitx stash clear` | 清空所有暂存 |
| `gitx tag [list]` | 查看标签 |
| `gitx tag new <标签> <备注>` | 创建标签 |
| `gitx tag push [<标签>]` | 推送标签到远端 |
| `gitx tag delete <标签> [-r]` | 删除本地或远端标签 |

### 📝 提交与改动

| 命令 | 说明 |
|------|------|
| `gitx commit -m <信息> [-a] [--amend] [--no-edit] [--allow-empty]` | 提交改动 |
| `gitx diff [路径...] [--staged] [--stat] [--name-only]` | 查看差异（上色渲染） |
| `gitx discard <路径...> [-y] [--staged]` | 丢弃工作区或暂存区改动 |
| `gitx clean [-d] [-x] [-y]` | 删除未跟踪文件（`-d` 含目录，`-x` 含忽略文件） |

### 🔍 探索

| 命令 | 说明 |
|------|------|
| `gitx search <关键词> [-n 10] [--language go] [-d]` | 搜索 GitHub 仓库 |
| `gitx search` / `gitx search -i` | **交互式搜索**：问关键词 → 结果表 → ↑↓ 挑一个 → 下载 / 看概览 / 打开网页（挑完能接着挑，可选「换个关键词再搜」） |
| `gitx stat [owner/repo] [--json]` | 仓库概览：★/fork/topics/语言/许可证/贡献者/最新发布 |
| `gitx web [issues\|pulls\|releases\|...] [--print]` | 浏览器打开仓库页面 |
| `gitx ignore python node [--force]` | 拉取 .gitignore 模板 |

### 🤝 协作与进阶

| 命令 | 说明 |
|------|------|
| `gitx remote` | 列出远程（拉取/推送地址） |
| `gitx remote add <名> <地址>` | 添加远程（GitHub 地址自动：拉取加速 + 推送直连） |
| `gitx remote set-url\|rename\|remove\|show ...` | 改址/重命名/删除/查看 |
| `gitx submodule` | 子模组状态概览 |
| `gitx submodule add <地址> <路径>` | 添加子模组（拉取走加速） |
| `gitx submodule update [--remote]` | 更新子模组（`--init --recursive`，走加速） |
| `gitx submodule sync\|remove <路径>` | 同步地址或删除子模组 |
| `gitx pr` | 当前仓库的开放 PR |
| `gitx pr list [owner/repo] [--state open\|closed\|all] [-n 30]` | 列出 PR |
| `gitx pr view <编号> [--web]` | 查看 PR 详情（标题/状态/正文） |
| `gitx pr create [-t 标题 -b 正文] [--fill] [--draft]` | 创建 PR（依赖已登录的 gh CLI） |
| `gitx cache [info]` | 查看缓存占用（`~/.cache/gitx`） |
| `gitx cache clear [-y]` | 清空缓存（可再生产，下次自动重建） |
| `gitx cache list [-a]` / `gitx cache prune` | 看缓存明细（缓存键 / 有效期 / 状态） / 只清已过期的 |
| `gitx daemon [status]` | 守护进程状态：配置 / 进程 / 套接字 / 空闲退出 / 实际配色 |
| `gitx daemon start\|stop\|restart` | 立刻召唤 / 停掉 / 重启（默认由命令自动召唤，无需手动；走零依赖快速通道，毫秒级） |
| `gitx daemon bench [-n 3] [--cmd "repos list"]` | 实测本机"有 / 没有守护进程"的启动耗时差距（中位数） |

### ⚡ 加速管理

| 命令 | 说明 |
|------|------|
| `gitx proxy [status]` | 查看加速状态（含 Release 专用加速源） |
| `gitx proxy on\|off\|auto\|default\|set <源>` | 切换加速源（`v6`/`v4`/`gh-proxy`/自定义 URL） |
| `gitx proxy release` | 查看 Release 专用加速源 |
| `gitx proxy release on v4` | 仅 Release 使用加速（其他功能照旧） |
| `gitx proxy release off` | Release 直连（其他功能仍走加速） |
| `gitx proxy release follow` | Release 跟随全局设置（默认） |
| `gitx proxy http <代理地址> [--local]` | 设置 HTTP 代理 |
| `gitx proxy install\|uninstall [--local]` | 写入/移除 git insteadOf 规则 |
| `gitx proxy test` | 测试加速源连通性（Release 独立设置时一并测试） |

### ⚙️ 配置与自检

| 命令 | 说明 |
|------|------|
| `gitx config [list\|get\|set\|reset\|zh]` | 配置管理 |
| `gitx config edit` | 用 `$VISUAL`/`$EDITOR` 编辑配置文件 |
| `gitx config path` | 打印配置文件路径 |
| `gitx doctor [--fix]` | 环境自检；`--fix` 自动修复编码/pull 策略/上游 |
| `gitx upgrade [--check]` | 自更新到最新版本（走加速） |

---

## 常用场景示例 🎯

### 场景 1：新建仓库并推送

```bash
gitx init myproj
echo "Hello World" > README.md
gitx commit -a -m "首次提交"
gitx push to https://github.com/me/myproj
```

### 场景 2：只下载某个文件夹（部分克隆）

```bash
gitx https://github.com/torvalds/linux/tree/master/drivers/gpu/drm/amd
```

### 场景 3：交互式挑选 Release 附件

```bash
gitx release cli/cli
```

### 场景 4：每日同步

```bash
gitx sync
```

### 场景 5：暂存当前工作，切换分支处理紧急任务

```bash
gitx stash save "改到一半的功能"
gitx switch hotfix
# ... 处理紧急修复 ...
gitx stash pop
```

### 场景 6：打标签并发布

```bash
gitx tag new v1.0.0 "首个正式版"
gitx tag push
```

### 场景 6b：发一个预发布（附件 + 说明）

```bash
uv build --out-dir dist                      # 产出 sdist + wheel
gitx publish create v1.0.5-pre2 dist/* -T "gitx 1.0.5-pre2" -F 发布说明.md -p
gitx publish view v1.0.5-pre2                # 确认附件与说明
gitx publish edit v1.0.5-pre2 --no-prerelease --latest   # 转正式版
```

### 场景 6c：CI 跑挂了，看日志、重跑、拿产物

```bash
gitx actions                          # 看最近运行（状态列直接显示 成功 / 失败 / 进行中）
gitx actions view --log-failed         # 交互式挑一次运行，只看失败步骤的日志
gitx actions rerun --failed            # 只重跑失败的作业
gitx actions download -D 产物目录      # 把运行产物（附件）下载下来
gitx actions dispatch release.yml      # 手动触发一次 workflow_dispatch
```

### 场景 6d：换个账号 / 把令牌喂给 gitx

```bash
gitx auth                     # 看当前是哪个账号
gitx auth switch              # 切换当前账号（多账号时）
gitx auth token --save        # 令牌写进 gitx 配置，只读 API 限额 60 -> 5000 次/小时
```

### 场景 6e：管理自己的仓库（挑一个 → 编辑界面）

```bash
gitx repos                 # ↑↓ 挑一个仓库（最多渲染 5 行，打字即筛选）→ 进编辑界面：
                           # 改描述 / 主页 / 话题 / 可见性 / 默认分支 / 功能开关 / 模板 /
                           # 归档 / 收藏 / 改名 / 克隆 / 打开网页 / 设为默认 / 删除，选「完成」退出
gitx repos -n 5            # 只取最近 5 个仓库来挑（仓库多时先缩范围）
gitx repos -q dotfile      # 仓库多、记不住名字？按关键词搜（搜得到全部，不受 -n 限制）
gitx repos --fresh         # 不吃缓存，重新向 GitHub 取一次（默认 5 分钟内复用缓存）
                           # 挑选器底部也有一条「用关键词搜全部仓库」，选中即可现场搜
gitx repos -n 5 delete     # 子命令也能省略仓库：只在前 5 个里挑一个删
gitx repos edit owner/repo -d "新描述" -t cli --no-wiki   # 非交互：直接给选项
gitx repos view owner/repo # 看当前设置（--web 打开网页）
```

### 场景 6f：交互式搜仓库（不写关键词）

```bash
gitx search                # 问一次关键词 -> 结果表 -> ↑↓ 挑一个 -> 下载 / 看概览 / 打开网页
gitx search -i "vim 插件"   # 带着关键词进交互界面（挑完能接着挑，或「换个关键词再搜」）
gitx search "vim 插件" -d   # 不想要交互：搜完直接挑一个下载
```

### 场景 7：查看仓库快速概览

```bash
gitx stat torvalds/linux
```

---

## 透传原生 git 🔄

**非 gitx 自身的词一律透传 git**：

```bash
gitx status          # 等价于 git status
gitx log --oneline   # 等价于 git log --oneline
gitx blame file.py   # 等价于 git blame file.py
```

需要**未经改写的行为**时用：

```bash
gitx git <任意命令>
gitx git push --force  # 强制推送
```

---

## 环境变量 🌍

```bash
# 全局默认加速源
GITX_PROXY=off|v6|v4|gh-proxy|https://...

# 仅覆盖 Release 功能的加速源
GITX_RELEASE_PROXY=off|v6|v4|gh-proxy|...
```

优先级：命令行 > 环境变量 > 配置文件

---

## 配置文件 📄

**路径**：`~/.config/gitx/config.toml`（或 `$XDG_CONFIG_HOME/gitx/config.toml`）

**格式**：TOML，带中文注释，人类可读可改，改完即生效。

**可配置键**：

| 键 | 默认值 | 说明 |
|----|--------|------|
| `proxy` | `v6` | 全局加速源 |
| `release_proxy` | 跟随 `proxy` | Release 专用加速源 |
| `depth` | `1` | 克隆深度（`0` = 完整克隆） |
| `branch` | 远端默认分支 | 下载时 URL 未带分支的默认分支 |
| `dest` | 当前目录 | 默认下载目录（支持 `~`） |
| `resume` | `true` | 断点续传开关 |
| `message` | `"日常同步更新"` | push 默认提交信息 |
| `sync_rebase` | `true` | `gitx sync` 用变基（`false` = 合并） |
| `token` | 空 | GitHub API token（限额 60 → 5000 次/小时；`gitx auth token --save` 一键写入） |
| `cache` | `true` | 把可再生的结果记到 `~/.cache/gitx`（接口响应 / 默认分支 / 版本查询） |
| `cache_ttl` | `300` | 接口结果的缓存秒数（`0` = 不缓存） |
| `daemon` | `false` | **召唤守护进程**：开启后运行任意 gitx 命令会自动拉起预热进程，后续命令由它 fork 执行 |
| `daemon_idle` | `300` | 守护进程空闲多少秒后自己退出 |
| `palette` | `auto` | 配色：`auto`（开了守护进程就用终端配色）/ `terminal` / `mocha` |
| `remote` | `origin` | 默认远程名（`info` / `url` / `web` / `push` 等不带 `-r` 时用） |
| `search_limit` | `10` | `gitx search` 不带 `-n` 时的条数 |
| `repos_limit` | `30` | `gitx repos` / `repos list` 不带 `-n` 时的条数 |
| `color` | `auto` | 彩色输出开关 |
| `assume_yes` | `false` | 跳过所有确认（相当于全局 `-y`） |

**旧版兼容**：首次运行会自动将 `config.json` 迁移为 `config.toml`（原文件保留为 `config.json.bak`）。

---

## 常见问题 🔧

### Q1: 下载速度很慢怎么办？

```bash
gitx proxy auto          # 自动选择最快节点
gitx proxy test          # 测试各节点连通性
gitx proxy set https://your-mirror.com  # 换用自定义镜像
```

### Q2: 只想加速 Release 下载，其他功能直连？

```bash
gitx proxy release on    # Release 走加速
gitx proxy off           # 其他功能直连
```

### Q3: 环境配置有问题？

```bash
gitx doctor              # 检查问题
gitx doctor --fix        # 自动修复（编码/pull 策略/上游）
```

### Q4: 如何完全禁用加速？

```bash
gitx proxy off
# 或
GITX_PROXY=off
```

### Q5: 想恢复纯净 git 行为？

```bash
gitx git <命令>          # 显式透传
# 例如：gitx git push --force
```

---

## 安装方式 📦

### 方式 1：从源码安装（推荐）

```bash
git clone https://github.com/FLT18355/gitx.git
cd gitx
uv tool install .
```

### 方式 2：从 Release 附件安装（wheel）

```bash
uv tool install gitx-x.x.x-py3-none-any.whl
```

### 验证安装

```bash
gitx --version    # 查看版本
gitx doctor       # 环境自检
```

---

## 技术栈 🛠️

- **CLI 框架**：Typer
- **富文本渲染**：Rich（表格/进度条/面板）
- **交互选择**：questionary
- **主题**：Catppuccin Mocha
- **配置格式**：TOML
- **缓存目录**：`~/.cache/gitx`

---

## 贡献指南 🤝

欢迎提交 Issue 和 Pull Request！

- 报告 bug 请附上 `gitx doctor` 输出
- 新功能建议先开 Issue 讨论
- 文档改进直接提 PR

---

## 许可证 📜

MIT License — 自由使用、修改、分发。

---

## 相关链接 🔗

- **源码仓库**：https://github.com/FLT18355/gitx
- **问题反馈**：https://github.com/FLT18355/gitx/issues
- **发布版本**：https://github.com/FLT18355/gitx/releases

---

*让 GitHub 访问不再受限，一条命令回归流畅体验 🚀*
