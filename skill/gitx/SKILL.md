---
name: gitx
version: 1.0.2
description: 给中国人用的 GitHub 加速与同步工具 —— 下载 / 同步 / 加速 / 分支 / 暂存 / 标签 / 提交 / 改动
author: FLT18355
repository: https://github.com/FLT18355/gitx
license: MIT
tags: [github, git, cli, download, sync, acceleration]
---

# gitx Skill

给中国人用的 GitHub 加速与同步工具 —— 下载 / 同步 / 加速 / 分支 / 暂存 / 标签 / 提交 / 改动，一条命令搞定。

## 安装

```bash
# 方式 1：从源码安装（推荐）
git clone https://github.com/FLT18355/gitx.git
cd gitx
uv tool install .

# 方式 2：从 Release 附件安装（wheel）
uv tool install gitx-1.0.2-py3-none-any.whl

# 验证
gitx --version      # 应输出 gitx 1.0.2
gitx doctor         # 环境自检
```

## 核心特性

- **默认走加速镜像** `https://v6.gh-proxy.org` 拉取（克隆 / 下载 / Release 附件 / API），推送直连 GitHub
- **Release 加速可独立设置**：`release_proxy` / `GITX_RELEASE_PROXY` 只影响 Release 附件与发布列表，
  克隆 / 同步 / 搜索等照旧走全局加速源（`gitx proxy release on v4|off|follow`）
- **四个加速源可选**：v6 / v4（IPv4 端点）/ gh-proxy / 自定义 URL，`gitx proxy auto` 实测选最快
- **Typer + Rich** 构建分组式 CLI：彩色表格、下载进度条（速率 / 剩余时间）
- **Catppuccin Mocha 主题**：表格 / 面板 / 进度条 / 选择器统一取自官方调色板
- **只输入 `gitx`** 显示版本 + 加速状态 + 常用命令速查（全量帮助见 `gitx -h`）
- **交互式挑选**用 questionary：上下键选择、最多渲染 5 行、打字即筛选
- **git 透传不加载 typer**：`gitx status` / `gitx log --oneline` 几乎瞬时完成
- **断点续传**：中断的下载留下 `.part`，重跑自动续传
- **部分克隆 + 稀疏检出**：文件夹下载快 8 倍（只拉取目标目录的 blob）

## 命令速查

### 下载（默认加速）
```bash
gitx https://github.com/owner/repo                    # 仓库 -> ./repo (浅克隆)
gitx https://github.com/owner/repo -x                 # 源码包 tar.gz (单流，不要历史时最快)
gitx https://github.com/owner/repo -X                 # 下载并直接解压
gitx https://github.com/owner/repo/tree/分支/路径      # 文件夹 (部分克隆 + 稀疏检出)
gitx https://github.com/owner/repo/blob/分支/路径/文件  # 单个文件
gitx release owner/repo                               # 交互式挑发布 + 挑附件
gitx release owner/repo --tag v1.0.0 -a '*linux*'     # 指定标签 + 通配附件
```

### 同步
```bash
gitx push                     # 提交并推送 (默认信息: 日常同步更新)
gitx push "修复了 bug"        # 带备注
gitx push to https://github.com/owner/repo  # 首次关联远程并推送
gitx pull [--rebase]          # 拉取 (走加速)
gitx sync ["备注"]            # 先拉(变基)后推，一步到位
gitx fetch [--prune]          # 只更新远端引用 (走加速，--prune 清理已删除的远端分支)
```

### 仓库
```bash
gitx init 我的项目 [--no-zh]          # 初始化: 分支 main + 中文友好配置
gitx info                             # 仓库概览: 状态/领先落后/最近提交/加速状态
gitx graph [-n 30] [--all]            # 带图形的提交历史 (git log --graph 上色版)
gitx tidy [--prune] [--gc [--aggressive]]  # 体检: 体积 / 已合并分支 / 打包瘦身
gitx url [accel|https|ssh] [-r 远程]  # 查看/切换远端地址形态
gitx undo [N] [--soft|--mixed|--hard] [-y]  # 撤销最近 N 次提交
```

### 分支（新增）
```bash
gitx branch [-a] [-n 20]              # 分支表: 上游 / 领先落后 / 最近提交
gitx branch new 新功能 [--from 标签] [--switch]  # 新建分支
gitx switch 修复 / gitx switch -c 实验           # 切换 / 新建并切换 (远端同名自动建跟踪)
gitx branch rename 新名字 [-o 旧名字]           # 重命名
gitx branch delete 旧分支 [--force] [-r]        # 删除本地 / origin 上的远端分支
gitx branch upstream [分支] [--set origin/main] [--unset]  # 上游查看/设置/取消
gitx merge 新功能 [--no-ff] [--squash]          # 合并 (冲突给出解决/放弃提示)
gitx rebase main [-i] [--continue/--skip/--abort]  # 变基
```

### 暂存与标签（新增）
```bash
gitx stash [list] / gitx stash save "备注" [-u] / gitx stash show [-p] / gitx stash pop [N] / apply [N] / drop [N] / clear
gitx tag [list] / gitx tag new v1.0.0 "说明" / gitx tag push [v1.0.0] / gitx tag delete v1.0.0 [-r]
```

### 提交与改动（新增）
```bash
gitx commit -m "信息" [-a] [--amend] [--no-edit] [--allow-empty]
gitx diff [路径...] [--staged] [--stat] [--name-only]  # 上色渲染
gitx discard <路径...> [-y] [--staged]                 # 丢弃工作区/暂存区改动
gitx clean [-d] [-x] [-y]                              # 删除未跟踪文件
```

### 探索
```bash
gitx search "关键词" [-n 10] [--language go] [-d]  # 搜 GitHub 仓库
gitx stat [owner/repo] [--json]                     # 仓库概览: ★/fork/topics/语言/许可证/贡献者/最新发布
gitx web [issues|pulls|releases|...] [--print]      # 浏览器打开当前仓库页面
gitx ignore python node [--force]                   # 拉取 .gitignore 模板
```

### 加速管理
```bash
gitx proxy [status]          # 查看状态（含 Release 专用加速源）
gitx proxy on|off|auto|default|set <源>   # 源: v6 / v4 / gh-proxy / https://...
gitx proxy release           # 查看 Release 专用加速源
gitx proxy release on v4     # 只给 Release 换加速源（克隆等其它功能照旧）
gitx proxy release off       # Release 直连（其它功能仍走加速）
gitx proxy release follow    # 取消独立设置，跟随全局（默认）
gitx proxy http http://127.0.0.1:7890 [--local]  # 设置 HTTP 代理
gitx proxy install|uninstall [--local]         # 写入/移除 git insteadOf 规则
gitx proxy test                # 测试加速源连通性（Release 独立设置时会一并测试）
```

### 配置与自检
```bash
gitx config [list|get|set|reset|zh]
gitx doctor                    # 环境自检: git/gh/token/仓库/加速源/编码
```

## 常用场景示例

```bash
# 新建仓库并推送
gitx init myproj
echo hello > README.md
gitx commit -a -m "首次提交"
gitx push to https://github.com/me/myproj

# 只下某个文件夹（部分克隆，极快）
gitx https://github.com/torvalds/linux/tree/master/drivers/gpu/drm/amd

# 交互式挑 Release 附件
gitx release cli/cli

# 每日同步
gitx sync

# 查看仓库概览
gitx stat torvalds/linux

# 暂存当前改动，切分支处理别的事
gitx stash save "改到一半"
gitx switch hotfix
gitx stash pop

# 打标签并推送
gitx tag new v1.0.0 "首个正式版" && gitx tag push
```

## 透传原生 git

非 gitx 自身的词一律透传 git（如 `gitx status`、`gitx log --oneline`、`gitx blame file`）；
需要未经改写的行为时用 `gitx git <任意命令>` 显式透传。

## 环境变量

```bash
GITX_PROXY=off|v6|v4|gh-proxy|https://...  # 全局默认加速源
GITX_RELEASE_PROXY=off|v6|v4|gh-proxy|... # 只覆盖 Release 功能的加速源
```

## 配置文件

`~/.config/gitx/config.json`（或 `$XDG_CONFIG_HOME/gitx/config.json`）

可配置键：
- `proxy` = v6 / v4 / gh-proxy / off / 自定义 URL
- `release_proxy` = Release 专用加速源（空 = 跟随 proxy，`gitx proxy release` 管理）
- `depth` = 克隆深度 (默认 1，0 = 完整克隆)
- `branch` = 默认分支 (空 = 自动探测)
- `message` = push 默认提交信息
- `token` = GitHub API token (限额 60 → 5000 次/小时)