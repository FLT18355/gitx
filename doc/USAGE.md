# gitx 完整命令手册

> 本手册包含了 `gitx` 所有的子命令、参数选项与高级用法。如果你只是想快速上手，请返回阅读 [README.md](../README.md)。

## 目录
- [下载与工作区](#下载与工作区)
- [Release 与发行版](#release-与发行版)
- [仓库管理与探索](#仓库管理与探索)
- [日常同步与分支](#日常同步与分支)
- [加速与配置管理](#加速与配置管理)

---

## 下载与工作区

### `gitx download` / `gitx clone`
下载 GitHub 仓库、子目录或单个文件（默认走加速）。

- `gitx https://github.com/owner/repo`：克隆完整仓库（浅克隆）
- `gitx owner/repo -x`：下载源码包 tar.gz（最快，无 Git 历史）
- `gitx owner/repo -X`：下载源码包并直接解压
- `gitx owner/repo/tree/main/src`：只下载 `src` 子目录（部分克隆 + 稀疏检出）
- `gitx download url1 url2 -o 下载目录`：批量下载多个链接
- `gitx download -f 链接.txt -o 目录`：从文本文件读取链接批量下载

**选项：**
- `--no-proxy` / `--proxy <源>`：临时关闭加速或更换加速源
- `--branch <分支>`：指定分支
- `--depth <N>`：克隆深度（0 = 完整克隆）
- `--submodules`：同时拉取子模组
- `--fresh`：忽略断点续传，从头下载

### `gitx ws` (工作区)
管理多个本地仓库的集合，支持克隆、登记、批量同步。

- `gitx ws owner/repo`：克隆到默认工作区并登记
- `gitx ws add ~/code/已有克隆`：登记已有仓库
- `gitx ws list`：查看所有登记的仓库状态（分支/改动/领先落后）
- `gitx ws sync -j 4`：批量拉取所有仓库（并发 4；工作区有改动 / 无上游的仓库只 fetch）
- `gitx ws fetch`：逐个同步，表格里显示每个仓库的分支、结果与拉取的提交数
- `gitx ws fetch --fetch-only -j 4`：只更新远端跟踪引用，不合并（适合先看落后多少）
- `gitx ws each git status -s`：在每个仓库执行同一条命令
- `gitx ws use <名字> [目录]`：切换或创建新的工作区

---

## Release 与发行版

### `gitx release`
下载 Release 附件。

- `gitx release owner/repo`：交互式挑选发布和附件
- `gitx release owner/repo --tags`：列出最近的发布列表
- `gitx release owner/repo --tag v1.0.0 --list`：查看指定标签的附件清单
- `gitx release owner/repo -a '*linux_amd64*'`：使用通配符只下载特定附件

### `gitx publish`
创建、上传、编辑、删除 Release（需 `gh` 登录）。

- `gitx publish`：列出发行版
- `gitx publish create v1.0.0 dist/* -T "标题" -F 说明.md`：创建发行版并上传附件
- `gitx publish view v1.0.0`：状态 / 时间 / 说明 / 附件大小与下载数
- `gitx publish view v1.0.0 --notes`：显示完整发行说明（默认只显示首行）
- `gitx publish upload v1.0.0 dist/*.whl --clobber`：补传附件（覆盖同名）
- `gitx publish edit v1.0.0 --no-draft`：将草稿转为正式发布
- `gitx publish delete v1.0.0 --cleanup-tag`：删除发行版并连带删除标签

---

## 仓库管理与探索

### `gitx repos`
管理你的 GitHub 仓库。

- `gitx repos`：交互式挑选仓库并进入编辑界面
- `gitx repos -q dotfile`：搜索你的仓库
- `gitx repos starred`：浏览你收藏的仓库，支持交互式挑选或自动翻页
- `gitx repos create my-tool --public --push`：新建仓库
- `gitx repos delete owner/repo -y`：删除仓库（危险操作）

### `gitx info`
本地仓库概览。

- `gitx info`：分支（含分离 HEAD 的提交）/ 上游 / 远端 / 改动 / 领先落后 / 提交·分支·标签数 / 最近提交
- 检测到落后、领先、冲突或无上游时，在表格下方给出对应的下一步命令

### `gitx search` / `gitx stat`
- `gitx search`：交互式搜仓库并选择操作
- `gitx search "cli" -n 10 --language rust`：非交互式搜索
- `gitx stat owner/repo`：查看仓库详细概览（star/语言/贡献者等）
- `gitx stat owner/repo --json`：以 JSON 格式输出，方便脚本处理

---

## 日常同步与分支

### 提交与同步
- `gitx push`：提交并推送（默认信息“日常同步更新”）
- `gitx sync "说明"`：自动变基拉取后推送
- `gitx pull --rebase`：走加速的变基拉取

### 分支与标签
- `gitx branch`：查看本地分支状态
- `gitx switch -c 新分支`：新建并切换分支
- `gitx merge 分支名`：合并分支
- `gitx rebase -i main`：交互式变基
- `gitx tag new v1.0.0`：创建标签并推送

---

## 加速与配置管理

### `gitx proxy`
- `gitx proxy`：查看当前加速源状态
- `gitx proxy auto`：自动测速并选择最快的加速源
- `gitx proxy on v4`：切换到 IPv4 加速端点
- `gitx proxy off`：关闭加速（直连）
- `gitx proxy install`：写入 Git 全局配置，让普通 `git clone` 也走加速

### `gitx config`
- `gitx config`：以表格显示所有配置
- `gitx config set token <TOKEN>`：设置 GitHub Token，提高 API 限额
- `gitx config set daemon true`：开启守护进程，大幅提升命令启动速度