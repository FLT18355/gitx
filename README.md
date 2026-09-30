# gitx

给中国人用的 GitHub 加速与同步工具 —— 下载 / 同步 / 加速, 一条命令搞定。

默认走加速镜像 `https://v6.gh-proxy.org` 拉取, 推送直连 GitHub(镜像不支持推送)。

## 安装

```bash
cd Gitx
uv sync          # 创建环境并安装
uv run gitx      # 或: uv run python -m gitx
```

## 用法

### 下载(默认加速)

```bash
gitx https://github.com/owner/repo                  # 仓库 -> ./repo
gitx https://github.com/owner/repo/tree/分支/路径   # 文件夹(稀疏检出)
gitx https://github.com/owner/repo/blob/分支/路径/文件  # 单个文件
gitx clone https://github.com/owner/repo 我的目录   # 等价下载
```

选项: `--no-proxy` 直连, `--proxy gh-proxy` 换加速源, `--branch <分支>`, `--depth <N>`(0 = 完整克隆)。

### 下载 Release 附件(加速)

```bash
gitx https://github.com/owner/repo/releases                     # 最新发布的全部附件
gitx https://github.com/owner/repo/releases/tag/v1.0.0          # 指定标签的附件
gitx https://github.com/owner/repo/releases/download/v1.0.0/文件名  # 单个附件
gitx release owner/repo --list                    # 只看附件清单
gitx release owner/repo --tag v1.0.0              # 指定标签
gitx release owner/repo --asset '*linux_amd64*'   # 只下匹配的附件(支持通配)
gitx release owner/repo --source                  # 额外下载源码包(tarball)
gitx release owner/repo -o ~/下载                 # 指定保存目录
```

API 会经加速访问; 已登录 `gh` 时自动复用其 token(限额 60 → 5000 次/小时)。

### 同步

```bash
gitx push                            # 提交并推送(默认信息: 日常同步更新)
gitx push "修复了 bug"               # 带备注
gitx push to https://github.com/owner/repo   # 首次关联远程并推送
gitx push -f                        # 强制推送
gitx pull                           # 拉取(走加速)
gitx pull --rebase
gitx sync                           # 先拉(变基)后推, 一步到位
gitx sync "今天的改动"               # 带上提交信息
```

推送被拒时若远端领先, 会提示先 `gitx pull --rebase`; `gitx sync` 自动完成这套流程。

### 仓库操作

```bash
gitx init 我的项目     # 初始化: 分支 main + 中文友好配置
gitx init --bare 裸仓  # 原生 git init 参数照常透传 (--no-zh 可跳过中文配置)
gitx info              # 仓库概览: 状态/领先落后/最近提交/加速状态
gitx undo              # 撤销最近 1 次提交, 改动保留在暂存区
gitx undo 3            # 撤销最近 3 次提交
gitx undo --mixed      # 改动回到工作区(未暂存)
gitx undo --hard -y    # 丢弃改动(默认会询问确认)
gitx config zh         # 当前仓库写入中文友好配置
gitx config zh --global  # 全局写入
```

中文友好配置解决两个老问题: `core.quotepath=false`(中文文件名不再显示为 `\344\270\255`)、
`i18n.*Encoding=utf-8`(提交信息与日志按 UTF-8 处理)。

### 加速管理

```bash
gitx proxy            # 查看状态
gitx proxy auto       # 自动测速(git 克隆端点), 选用最快的加速源
gitx proxy on         # 开启加速(v6.gh-proxy.org)
gitx proxy off        # 关闭加速(直连)
gitx proxy default    # 恢复默认加速源
gitx proxy set https://gh-proxy.com   # 自定义加速源
gitx proxy http http://127.0.0.1:7890 # 设置 git 的 HTTP(S) 代理(本地代理软件)
gitx proxy http off   # 取消 git 代理
gitx proxy install    # 写入 git 全局 insteadOf 规则, 让普通 git 命令也走加速
gitx proxy uninstall  # 移除上述规则
gitx proxy test       # 测试加速源连通性
```

### 其它

```bash
gitx config                 # 查看配置
gitx config set depth 0     # 默认完整克隆
gitx config set message 更新 # 默认提交信息
gitx doctor                 # 环境自检(git/gh/仓库/加速源/编码)
gitx status / gitx log --oneline   # git 子命令直接透传 (原生 init: gitx git init)
```

环境变量 `GITX_PROXY=off|v6|gh-proxy|https://...` 可设置全局默认加速源。

## 原理

- 加速 = 在 GitHub 域名 URL 前拼镜像前缀, 如 `https://v6.gh-proxy.org/https://github.com/...`
- 拉取(克隆 / 下载 / Release 附件 / API)走加速; 推送走直连 —— 镜像对 `git push` 返回 405
- 存在全局 insteadOf 规则时, 推送地址自动改用 SSH(gh 已配好密钥), 避免 https 推送被规则重写到镜像
- `gitx proxy install` 利用 git 自身的 `url.<镜像>/.insteadOf` 规则, 全局生效
- 分支自动探测:`git ls-remote --symref` 取默认分支(main/master)
- 文件夹下载: 稀疏检出(`git sparse-checkout --no-cone`), 只拉取目标目录
- `gitx proxy auto` 用 `git ls-remote` 实测各加速源(含直连)克隆端点耗时, 选最快的

## 源码结构

```
src/gitx/
  __init__.py   版本与入口        cli.py      命令分发 / 配置 / 加速管理 / 透传
  console.py    终端输出与交互    config.py   持久化配置 (~/.config/gitx/config.json)
  accel.py      加速源与测速      gitcmd.py   git 命令封装 (状态/领先落后/撤销原语)
  github.py     URL 解析         download.py 仓库/文件夹/文件下载
  release.py    Release 附件      repo.py     init / info / undo
  sync.py       push / pull / sync
```

## 开发

```bash
uv run python -m gitx --help
```
