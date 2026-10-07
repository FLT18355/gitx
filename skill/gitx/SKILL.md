---
name: gitx
version: 1.0.5
description: 给中国人用的 GitHub 加速与同步工具 —— 下载 / 同步 / 加速 / 分支 / 暂存 / 标签 / 提交 / 改动 / 发行版管理，一条命令搞定
author: FLT18355
repository: https://github.com/FLT18355/gitx
license: MIT
tags: [github, git, cli, download, sync, acceleration]
---

# gitx Skill — GitHub 加速同步工具

> 🇨🇳 专为国内用户设计：拉取走加速镜像，推送直连 GitHub，一条命令搞定所有操作。

## 快速上手 ⚡

```bash
# 1. 安装（三种方式，任选）
# ① 官方二进制（最快，不需要 Python/uv）
curl -L -o gitx https://github.com/FLT18355/gitx/releases/latest/download/gitx-linux-x86_64
chmod +x gitx && sudo install -m755 gitx /usr/local/bin/gitx
# ② wheel（要 gitx upgrade 自更新用这个）
uv tool install gitx-1.0.5-py3-none-any.whl
# ③ 源码
git clone https://github.com/FLT18355/gitx.git && cd gitx && uv tool install .

# 2. 环境自检
gitx doctor

# 3. 开始使用（示例）
gitx https://github.com/user/repo    # 加速克隆
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
| 🌲 **部分克隆** | 文件夹下载快 8 倍（稀疏检出） |
| 🔁 **协作一条龙** | remote / submodule / pr 全部加速 |
| 🏷️ **发行版管理** | `gitx publish` 创建 / 上传附件 / 编辑 / 删除（交给已登录的 gh） |
| 🔄 **自更新** | `gitx upgrade` 查 Release 下 wheel 都走加速 |

---

## 命令速查 📋

### 📥 下载

| 命令 | 说明 |
|------|------|
| `gitx <URL>` | 仓库浅克隆到当前目录 |
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
| `token` | 空 | GitHub API token（限额 60 → 5000 次/小时） |
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
