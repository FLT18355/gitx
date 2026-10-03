# gitx

给中国人用的 GitHub 加速与同步工具 —— 下载 / 同步 / 加速, 一条命令搞定。

> v0.6.1: 新增 `gitx stat` —— 一条命令看仓库的 star / fork / topics / 语言 / 许可证 /
> 贡献者 / 最新发布 (表格展示, `--json` 供脚本)。
> v0.6.0: 新增图表 / 分支 / 体检 / 远端切换 / 搜索 / 网页 / .gitignore 模板,
> 文件夹下载改用部分克隆 (实测快 8 倍), 下载支持断点续传, git 透传不再加载 typer (启动快 ~4 倍)。

默认走加速镜像 `https://v6.gh-proxy.org` 拉取, 推送直连 GitHub(镜像不支持推送)。

命令行用 **Typer + Rich** 构建: 分组式帮助、彩色表格、下载进度条(速率 / 剩余时间);
交互式挑选(Release 发布 / 附件 / 搜索结果)用 **questionary**: 上下键选择、最多渲染 5 行、打字即筛选。

## 安装

```bash
cd Gitx
uv sync          # 创建环境并安装 (依赖 typer / rich / questionary)
uv run gitx -h   # 或: uv run python -m gitx --help
```

## 用法

### 下载(默认加速)

```bash
gitx https://github.com/owner/repo                  # 仓库 -> ./repo (浅克隆, 有 git 历史)
gitx https://github.com/owner/repo -x               # 源码包 tar.gz (单个流, 不要历史时最快)
gitx https://github.com/owner/repo -X               # 下载并直接解压
gitx https://github.com/owner/repo/tree/分支/路径   # 文件夹 (部分克隆 + 稀疏检出, 只取目标目录)
gitx https://github.com/owner/repo/blob/分支/路径/文件  # 单个文件
gitx clone https://github.com/owner/repo 我的目录   # 等价 download
```

选项: `--no-proxy` 直连, `--proxy gh-proxy` 换加速源, `--branch <分支>`, `--depth <N>`(0 = 完整克隆),
`--submodules` 连同子模组一起拉取(也走加速), `--fresh` 忽略断点从零下载。

**断点续传**: 中断的下载会留下 `<文件>.part`, 重跑自动带 `Range` 续传, 不用重来。
下载整仓库后自动把推送地址指回直连 GitHub(存在全局加速规则时用 SSH), 保证 `gitx push` 不被镜像拒绝。

### 下载 Release 附件(通过 API, 默认加速)

```bash
gitx release owner/repo                     # 交互式: 先挑发布(含预发布, 默认最近 10 个), 再挑要下载的附件
gitx release owner/repo -n 30               # 挑选范围改成最近 30 个 (最多 100)
gitx release owner/repo --tags              # 非交互: 列出最近 10 个发布(含预发布)
gitx release owner/repo --tag v1.0.0        # 指定标签(不询问发布)
gitx release owner/repo --list              # 只看附件清单(表格: 名称 + 大小)
gitx release owner/repo --pick              # 强制交互: 挑选发布 + 附件
gitx release owner/repo -a '*linux_amd64*'  # 只下匹配的附件(通配, 可重复传 -a)
gitx release owner/repo --source            # 额外下载源码包(tarball)
gitx release owner/repo -o ~/下载           # 指定保存目录
gitx release owner/repo --fresh             # 忽略 .part 断点
```

终端里直接 `gitx release owner/repo` 进入**上下键交互**: 先用 ↑↓ 挑发布(直接打字即筛选), 回车确认(默认最新);
再挑附件: ↑↓ 移动、空格勾选、打字筛选, 回车确认 —— 一个都没勾就下全部。Ctrl+C 随时取消。
给了 `--tag` / `--asset` 或不在终端(管道/脚本)时完全非交互, 行为与旧版一致(最新发布 + 全部附件)。

链接形式同样可用:

```bash
gitx https://github.com/owner/repo/releases/tag/v1.0.0          # 指定标签的附件
gitx https://github.com/owner/repo/releases/download/v1.0.0/文件名  # 单个附件
gitx https://github.com/owner/repo/releases --list              # 只看清单
```

实现要点: 走 `api.github.com/repos/{owner}/{repo}/releases`(经加速镜像访问), 已登录 `gh` 或配置
`token` 时自动带上认证(限额 60 → 5000 次/小时); 附件按 `browser_download_url` 直下并显示进度条,
支持断点续传; 该 Release 没有附件时自动回退到源码包。

### 探索 (新)

```bash
gitx search "cli 工具" -n 10                # 搜 GitHub 仓库 (按 ★ 排序, 默认加速)
gitx search "neovim" --language go          # 限定语言
gitx search "neovim" -d                     # 搜完直接下载 (多个结果时上下键挑)
gitx web                                    # 浏览器打开当前仓库主页
gitx web issues / pulls / releases / actions / wiki
gitx web branch / commit                    # 打开当前分支 / HEAD 提交页
gitx web --print                            # 只打印地址, 不打开浏览器
gitx stat cli/cli                           # 仓库概览: ★ star / fork / topics / 语言 / 许可证 / 贡献者 / 最新发布
gitx stat                                   # 不写参数 = 当前仓库 origin 的概览
gitx stat cli/cli --json                    # 输出 JSON (脚本友好, 含 languages / contributors)
gitx ignore --list java                     # 列出可用 .gitignore 模板 (模糊匹配)
gitx ignore python node macos               # 从 github/gitignore 拉取模板写入 .gitignore
```

`gitx ignore` 的模板索引缓存一周 (`~/.cache/gitx/gitignore.json`), 删掉会自动重建。

`gitx stat` 走 GitHub API (默认加速, 也可 `--no-proxy` 直连), 一次可看: ★ star / fork / watcher /
开放 issue / 贡献者 / 网络仓库数、topics 标签、语言构成与占比、许可证、创建/更新/推送时间线、
默认分支与体积、归档/复刻/模板等状态, 以及最新发布 (标签 / 日期 / 附件数)。数据取自
`/repos/{owner}/{repo}` 与 `languages` / `contributors` / `releases/latest`; 后面几个接口
失败 (如无发布) 会被忽略而非报错。匿名限额 60 次/小时, 配 `token` 可到 5000 (`gitx config set token`)。

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
gitx init 裸仓 --bare  # 原生 git init 参数照常透传 (--no-zh 可跳过中文配置)
gitx info              # 仓库概览(表格): 状态/领先落后/最近提交/加速状态
gitx graph -n 30       # 带图形的提交历史 (git log --graph 上色版)
gitx branches -a       # 分支表: 上游 / 领先落后 / 最近提交 (单次 for-each-ref, 很快)
gitx tidy              # 体检: 体积 / 已合并分支数
gitx tidy --prune      # 删除已合并分支 (会确认, -y 跳过)
gitx tidy --gc         # git gc 打包瘦身 (--aggressive 更彻底)
gitx url               # 查看 origin 的拉取/推送地址与形态
gitx url ssh           # 切换为 SSH 传输
gitx url https         # 切换为直连 https
gitx url accel         # 切换为拉取加速 + 推送直连
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
gitx proxy            # 查看状态(表格: 加速源 / insteadOf / 配置文件)
gitx proxy auto       # 自动测速(git 克隆端点), 选用最快的加速源
gitx proxy on         # 开启加速(v6.gh-proxy.org)
gitx proxy off        # 关闭加速(直连)
gitx proxy default    # 恢复默认加速源
gitx proxy set https://gh-proxy.com   # 自定义加速源
gitx proxy http http://127.0.0.1:7890 # 设置 git 的 HTTP(S) 代理(本地代理软件)
gitx proxy http off   # 取消 git 代理
gitx proxy install    # 写入 git 全局 insteadOf 规则, 让普通 git 命令也走加速
gitx proxy uninstall  # 移除上述规则
gitx proxy test       # 测试加速源连通性(git 克隆 / raw / API)
```

### 其它

```bash
gitx config                 # 查看配置
gitx config set depth 0     # 默认完整克隆
gitx config set message 更新 # 默认提交信息
gitx config set token ghp_xxx   # 设置 API token (提高限额到 5000 次/小时, 显示时自动打码)
gitx doctor                 # 环境自检(git/gh/token/仓库/加速源/编码)
gitx status / gitx log --oneline   # git 子命令直接透传 (原生 init: gitx git init)
gitx dowload ...            # 子命令笔误会给出形近提示
```

环境变量 `GITX_PROXY=off|v6|gh-proxy|https://...` 可设置全局默认加速源。

## 为什么快 (实测数字, 2026-10 经 v6.gh-proxy.org)

- **git 透传不加载 typer**: `gitx status` / `gitx --version` 由只依赖标准库的快速分发处理,
  从 ~2.5s 降到 ~0.6s(含 uv 与 python 启动, 低配机器上); 加速源列表也不再靠多语言输出的
  `git help -a` 猜测, 直接交给 git 自己执行。
- **文件夹下载快 8 倍**: `git/git` 的一个子目录, 纯稀疏检出 30.7s / 14 MB → 部分克隆
  (`--filter=blob:none --sparse`) 3.8s / 4.2 MB。只拉取目标目录的 blob。
- **源码包路线**: `-x` 走 API 的 `/tarball/<ref>`, 单个 HTTP 流, 不要 git 历史时比克隆省一整个
  git 握手与对象协商。
- **断点续传**: 大附件中断不再从头下; `.part` 与目标不符(416 / 大小对不上)时自动丢弃重来。
- **按需加载**: rich.progress / rich.prompt / urllib / shutil / questionary 全部用到才导入。
- 并行下载实测**没有收益**(镜像按连接限速, 4 路并发比单路还慢), 故不做 —— 有证据才动刀。

## 原理

- 加速 = 在 GitHub 域名 URL 前拼镜像前缀, 如 `https://v6.gh-proxy.org/https://github.com/...`
- 拉取(克隆 / 下载 / Release 附件 / API)走加速; 推送走直连 —— 镜像对 `git push` 返回 405
- 存在全局 insteadOf 规则时, 推送地址自动改用 SSH(gh 已配好密钥), 避免 https 推送被规则重写到镜像
- `gitx proxy install` 利用 git 自身的 `url.<镜像>/.insteadOf` 规则, 全局生效
- 分支自动探测:`git ls-remote --symref` 取默认分支(main/master)
- 文件夹下载: 部分克隆 + 稀疏检出(`--filter=blob:none --sparse`), 检出时按需拉取目标目录的 blob
- `gitx proxy auto` 用 `git ls-remote` 实测各加速源(含直连)克隆端点耗时, 选最快的
- 命令分发: `gitx` 入口先走快速通道(git 透传 / --version), 其余交给 Typer 子命令;
  首词像链接(https:// / git@ )就自动补 `download`
- `gitx ignore` 复用 github/gitignore 官方模板库, 索引缓存 7 天, 按名拉取 (raw 也走加速)

## 源码结构

```
src/gitx/
  __init__.py   入口: 快速分发先行, 需要时才加载 typer    dispatch.py   git 透传 / --version 快速通道 (仅标准库)
  console.py    rich 控制台 (进度条/questionary 交互选择)  config.py     持久化配置 (~/.config/gitx/config.json)
  accel.py      加速源与测速                              gitcmd.py     git 命令封装 (分支/领先落后/维护原语)
  github.py     URL 解析 + REST API 客户端 (token 复用)   net.py        HTTP 下载: 断点续传 + 进度条
  download.py   仓库/文件夹/源码包下载                    release.py    Release 附件(API)
  repo.py       init / info / undo / graph / branches / tidy / url
  hub.py        search / stat / web / ignore
  sync.py       push / pull / sync
```

## 开发

```bash
uv run python -m gitx --help
uv run python -m gitx release cli/cli --list   # API + 加速 的实测例子
```

## 许可

本项目以 [MIT 许可](./LICENSE) 开源, 版权归 `FLT18355` (2026)。