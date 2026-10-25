# 🚀 gitx

**给中国人用的 GitHub 加速与同步工具 —— 下载 / 同步 / 加速，一条命令搞定。**

[![GitHub last commit](https://img.shields.io/github/last-commit/FLT18355/gitx?style=flat-square&color=89b4fa&logo=github)](https://github.com/FLT18355/gitx)
[![GitHub repo size](https://img.shields.io/github/repo-size/FLT18355/gitx?style=flat-square&color=cba6f7)](https://github.com/FLT18355/gitx)
[![License: MIT](https://img.shields.io/badge/License-MIT-a6e3a1?style=flat-square)](LICENSE)

![Python](https://img.shields.io/badge/Python-3.11+-313244?style=flat-square&logo=python&logoColor=f9e2af)
![Typer](https://img.shields.io/badge/CLI-Typer_+_Rich-313244?style=flat-square)
![Theme](https://img.shields.io/badge/Theme-Catppuccin_Mocha-313244?style=flat-square&logo=palette&logoColor=f5c2e7)

**默认走加速镜像 `https://v6.gh-proxy.org` 拉取，推送直连 GitHub。**<br>
*基于 Typer + Rich 构建，全中文提示、彩色表格、进度条，统一 Catppuccin Mocha 配色。*

---

## ✨ 核心亮点

- ⚡ **下载提速**：默认加速拉取，支持源码包、单文件、只下子目录（部分克隆快 8 倍）、断点续传。
- 🔍 **交互探索**：`gitx search` 交互式搜仓库，上下键选择，挑完直接下载或看概览。
- 📦 **仓库管理**：`gitx repos` 终端内直接改仓库设置（描述/话题/可见性），支持批量操作。
- 🚀 **发版与 CI**：`gitx publish` 一条命令发布 Release，`gitx actions` 终端内盯 CI 进度。
- 🛠️ **全中文体验**：从帮助文档到报错提示全中文，解决中文文件名乱码问题。

---

## 📦 安装

推荐使用 `uv` 进行安装（需 Python 3.11+）。

**方式一：从 Release 附件安装（推荐，方便后续自更新）**
直接安装构建好的 wheel 包：`uv tool install gitx-X.Y.Z-py3-none-any.whl`

**方式二：从源码安装**
先克隆仓库，进入目录后执行：`uv tool install .`

**验证安装**
输入 `gitx --version` 查看版本，或输入 `gitx doctor` 进行环境自检（检查 git / gh / token / 加速源）。

---

## 🚀 快速上手 (Quick Start)

### 1. 下载仓库与文件
- **克隆仓库**：`gitx https://github.com/owner/repo` （默认浅克隆，走加速）
- **省略协议头**：`gitx owner/repo` （直接下载）
- **只下子目录**：`gitx https://github.com/owner/repo/tree/main/src` （极速，只拉取目标目录）
- **交互式下附件**：`gitx release owner/repo`

### 2. 搜索与探索
- **交互式搜索**：`gitx search` （输入关键词 -> 挑仓库 -> 选动作）
- **带关键词搜**：`gitx search "cli 工具" -n 10` （按 star 排序）
- **看仓库概览**：`gitx stat cli/cli` （查看 star / 语言 / 贡献者）

### 3. 日常同步与提交
- **推送**：`gitx push` （默认提交信息为“日常同步更新”）
- **拉取**：`gitx pull` （走加速）
- **先拉后推**：`gitx sync "今天的改动"` （一步到位）

### 4. 仓库与发版管理 (需登录 gh)
- **管理仓库**：`gitx repos` （交互式挑选并编辑我的仓库）
- **发布版本**：`gitx publish create v1.0.0 dist/* -T "v1.0.0" -F RELEASE.md`
- **盯 CI 进度**：`gitx actions watch 1234`

---

## 📖 详细文档

因为功能太多，我们把详细说明拆分了。**不要通读全部**，按需查看：

| 我想知道... | 去哪看 |
| :--- | :--- |
| 完整的命令参数与选项 | 👉 **[完整用法手册 (docs/USAGE.md)](./docs/USAGE.md)** |
| 工作区(ws)管理与进阶配置 | 👉 **[进阶指南 (docs/ADVANCED.md)](./docs/ADVANCED.md)** |
| 怎么安装、升级、卸载 | 👉 **[安装指南 (INSTALL.md)](./INSTALL.md)** |
| 发版流程清单 | 👉 **[发布流程 (doc/发布流程.md)](./doc/发布流程.md)** |
| 给 AI Agent 的使用指南 | 👉 **[AI 技能库 (skill/gitx/SKILL.md)](./skill/gitx/SKILL.md)** |

---

## 🛠️ 开发与构建

同步环境依赖使用 `uv sync`。
在本地直接运行源码使用 `uv run python -m gitx --help`。
代码静态检查使用 `uvx ruff check src/gitx`。
构建发布用的 wheel 和源码包使用 `uv build --out-dir dist`。

> **注意**：本仓库的版本管理与提交使用 `jj` (colocated: `.jj/` 与 `.git/` 并存)，写操作请勿直接使用 git 命令。

## 🙏 致谢与声明

- 本工具默认的 GitHub 下载加速服务基于开源项目 gh-proxy 提供的公共节点（如 v6.gh-proxy.org）。感谢原作者及节点维护者提供的公益服务。
- 免责声明：这些公共加速节点由第三方提供，并非本项目自建。本工具仅负责拼接 URL 进行请求，不对节点的稳定性、下载速度及数据安全作任何担保。如遇节点不可用，可通过 gitx proxy set <你的加速源> 切换为你信任的镜像源。
- 请勿将本工具用于下载任何违反当地法律法规或侵犯版权的内容。

## 📄 许可

本项目以 [MIT 许可](./LICENSE) 开源，版权归 `FLT18355` (2026)。