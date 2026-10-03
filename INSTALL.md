# 安装 gitx

## 前置条件

- **git**（必需，仓库/同步功能的基础）
- **Python 3.14+**（`uv` 会自动下载对应的 CPython，无需系统预装）
- **uv**（安装器，未装时先执行下面命令）：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # Linux/macOS
# 或 winget install astral-sh.uv                # Windows
```

## 安装（推荐：全局命令）

```bash
git clone https://github.com/FLT18355/gitx.git
cd gitx
uv tool install .        # 构建并安装到 uv 的独立 venv, 提供全局 gitx 命令
gitx --version           # 验证: 应输出 gitx 1.0.0
```

安装后可在任意目录直接运行 `gitx`。升级时重新执行 `uv tool install .`（会先卸载旧版）。

> 中国大陆网络下 `git clone` 失败时, 先克隆加速镜像:
> `git clone https://v6.gh-proxy.org/https://github.com/FLT18355/gitx`

## 不装全局命令（项目内运行）

```bash
cd gitx
uv sync              # 创建 .venv 并安装依赖
uv run gitx -h
```

## 验证

```bash
gitx doctor          # 环境自检: git / gh / token / 仓库 / 加速源 / 编码
gitx https://github.com/git/git   # 实测下载 (默认走加速镜像, 浅克隆)
```

## 可选：加速源

默认拉取走 `https://v6.gh-proxy.org`，推送直连 GitHub。常用管理命令：

```bash
gitx proxy auto      # 实测测速, 自动选最快的加速源
gitx proxy off       # 关闭加速, 全部直连
gitx config set token ghp_xxx   # 设置 GitHub API token, 限额 60 -> 5000 次/小时
```

## 卸载

```bash
uv tool uninstall gitx
```

---

## For AI agents

Install as a global tool (verified, ~5s):

```bash
# 1. Install uv if missing
command -v uv || curl -LsSf https://astral.sh/uv/install.sh | sh
# 2. Clone and install
git clone https://github.com/FLT18355/gitx.git /tmp/gitx-install
uv tool install /tmp/gitx-install
# 3. Verify (expect "gitx 1.0.0" plus a config table from `gitx config`)
gitx --version && gitx doctor
```

Notes:
- Requires Python >= 3.14; uv downloads it automatically (project pins `.python-version` = 3.14).
- No compilation: the build backend is `uv_build`, pure wheel.
- Dependencies: `typer`, `prompt-toolkit`, `questionary` (pulled by uv).
- `uv tool install .` inside the cloned repo is equivalent; it uninstalls any prior gitx first.
- If plain `git clone` of GitHub fails (CN network), prefix the URL with the proxy: `https://v6.gh-proxy.org/https://github.com/FLT18355/gitx`.
- Runtime config lives at `~/.config/gitx/config.json`; cache at `~/.cache/gitx/`.
