# gitx 进阶指南

本文档介绍工作区管理、守护进程优化、以及进阶 API 操作。

## 工作区 (Workspace) 深度解析

`gitx ws` 允许你同时管理多个项目目录，甚至可以跨不同的根目录。

### 多工作区切换
你可以创建多个工作区，比如 `work` 和 `oss`：
- `gitx ws use work ~/code/work`：创建名为 work 的工作区并指定根目录
- `gitx ws use oss ~/code/oss`：创建另一个工作区

切换默认工作区：
- `gitx ws use work`：切换到 work，之后的命令都默认作用于此
- `gitx ws -s oss list`：临时查看 oss 工作区的仓库

### 移动工作区
如果你想把整个工作区搬家：
- `gitx ws move ~/new/path`：自动移动仓库并更新清单中的路径

### 批量同步与输出
- `gitx ws fetch`：逐个 fetch 后变基拉取；工作区有改动 / 没有上游的仓库只 fetch，不合并
- `gitx ws fetch --fetch-only`：只更新远端跟踪引用，表格里会标出每个仓库落后 / 领先多少
- `gitx ws fetch -j 4`：并行 4 个仓库（fork 子进程，结果仍按清单顺序输出）
- 结果表列出「名称 / 分支 / 结果 / 说明」，例如「拉取 2 个提交 (变基)」「仅 fetch（工作区有改动）」
- 单个仓库失败不影响其余仓库；失败原因（fetch / 拉取的 git 报错）直接写在说明列

## 性能优化：守护进程 (Daemon)

Python CLI 每次运行都需要重新导入大量模块（如 Typer、Rich），耗时约 1-2 秒。`gitx` 提供了一个后台守护进程来消除这个延迟。

### 开启与使用
```bash
gitx config set daemon true   # 开启守护进程
```
开启后，运行任意命令时会自动在后台拉起守护进程，之后的命令执行速度将大幅提升。

### 状态管理
- `gitx daemon`：查看守护进程状态（进程号、套接字、空闲退出时间）
- `gitx daemon stop`：手动停止守护进程
- `gitx config set daemon_idle 900`：设置空闲 15 分钟后自动退出

## 直通 GitHub API

如果你想执行某些高级操作，但 `gitx` 还没做封装，可以使用 `gitx api` 直通 `gh api`。

```bash
# 查看当前 API 限额
gitx api rate_limit

# 获取仓库的 star 数量
gitx api repos/cli/cli --jq .stargazers_count

# 发送 GraphQL 请求
gitx api graphql -f query='{viewer{login}}'
```

## 自动更新

`gitx` 内置了自更新机制：
- `gitx upgrade --check`：检查是否有新版本
- `gitx upgrade`：自动下载并安装最新版本（走加速）