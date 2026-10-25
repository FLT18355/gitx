# gitx

给中国人用的 GitHub 加速与同步工具 —— 下载 / 同步 / 加速, 一条命令搞定。

> **文档是按需读的, 别通读**: 本文件给用户 (装 / 用 / 配置), 实现要点在 `doc/开发.md`,
> 发版步骤在 `doc/发布流程.md`, 给 AI agent 的命令速查在 `skill/gitx/SKILL.md`。
> AI / 协作者请**只读当前任务相关的那一份**, 不要为了"了解全貌"把文档全读一遍。

> **v1.1.0-pre2: 收藏浏览 + 工作区拉取修正** ——
> ④ **`gitx repos starred`**: 浏览收藏的仓库, 每次只取 10 个, 光标越过最后一条时自动加载下一批;
> 挑中后可克隆 / 登记到工作区 / 看概览 / 打开网页 / 取消收藏 (表格与 `--json` 也支持);
> ⑤ **`gitx ws fetch` 改为逐个 `git pull`** (`--fetch-only` 保留旧的"只更新远端引用"),
> 并修正克隆把镜像地址烧进 origin、导致之后 fetch 换源失效 / 看起来"没有新提交"的问题;
> 另修 `gitx push` 重复追加 pushurl、导致同一次推送做两遍 / 分支跟踪提示打印两次的问题。
>
> **v1.1.0-pre1: 短链接 + repos 提速** ——
> ① **`gitx owner/repo` 直接下载**: 不用再打 `https://github.com/`, 形如 `gitx cli/cli` 即可
> (本地真有同名路径时仍按相对路径交给 git, 不会被截走);
> ② **`gitx repos` 提速**: 仓库列表 / 搜索 / 详情 / 分支都进 `~/.cache/gitx` 缓存
> (实测 `repos list -n 3` 7.9s → 1.4s), 写操作后自动作废, `--fresh` 可强制回源;
> 登录态判断从 `gh auth status` (每次 2-6 秒) 换成 `gh auth token` 并只查一次;
> ③ 修 `repos` 的两处 bug: `-q` 搜索时 `--archived` / `--fork` 被 gh 静默忽略 (布尔开关必须写成
> `--archived=true`), 以及 `gitx repos -o cli list` 这类**过滤项写在子命令前**时选项丢失。
>
> **v1.0.8: 热修 v1.0.7** —— v1.0.7 的 wheel 在 `publish create`/`edit` 后会因
> `NameError: cache` 崩 (源码导入漏了一行, 只在预热好的守护进程里才暴露), 这版只补它; 没升过的直接升 1.0.8。
>
> **v1.0.7: 修守护进程三处问题** ——
> ① 开了守护进程**掉色 / 表格按 80 列折行**: rich 的控制台在守护进程里是按"没有终端"建的,
> fork 出来也照旧 —— 现在子进程执行前按当前 fd 重建控制台, 颜色与宽度都对了;
> ② **`gitx daemon stop` 等三分钟**: stop/restart 被路由进守护进程后与它互相等成死锁 ——
> 现在这类命令一律本地跑, 且改走**不导入 typer/rich 的快速通道** (2.3 秒 → 1 秒内);
> ③ **感觉没效果**: 首条命令召唤成功后也走守护进程、预热清单连带 prompt_toolkit/questionary
> (选择器/进度条不再重付导入), 并新增 **`gitx daemon bench`** 在你机器上实测差距
> (本机示例: 1.9s → 1.4s)。
>

默认走加速镜像 `https://v6.gh-proxy.org` 拉取, 推送直连 GitHub(镜像不支持推送)。

命令行用 **Typer + Rich** 构建: 分组式帮助、彩色表格、下载进度条(速率 / 剩余时间),
配色统一为 **Catppuccin Mocha**; 直接运行 `gitx` 显示版本 + 加速状态 + 常用命令速查, `gitx -h` 才是完整帮助。
交互式挑选(Release 发布 / 附件 / 搜索结果)用 **questionary**: 上下键选择、最多渲染 5 行、打字即筛选。

## 安装

```bash
cd Gitx
uv sync          # 创建环境并安装 (依赖 typer / rich / questionary)
uv run gitx -h   # 或: uv run python -m gitx --help
```

或者从 Release 附件安装 (每个版本两个附件: **wheel** + **源码包**):

```bash
# 方式 1: wheel (要 gitx upgrade 自更新就用这个)
uv tool install gitx-X.Y.Z-py3-none-any.whl    # 或: uv tool install .

# 方式 2: 源码包
tar xf gitx-X.Y.Z.tar.gz && uv tool install ./gitx-X.Y.Z
```

> 两个附件由本机 `uv build --out-dir dist` 产出 (纯 Python, 不需要编译器),
> 再用 `gitx publish create` 上传; 安装后同样走加速镜像、同样能 `gitx merge` 等全套命令。

## 用法

### 下载(默认加速)

```bash
gitx https://github.com/owner/repo                  # 仓库 -> ./repo (浅克隆, 有 git 历史)
gitx https://github.com/owner/repo -x               # 源码包 tar.gz (单个流, 不要历史时最快)
gitx https://github.com/owner/repo -X               # 下载并直接解压
gitx https://github.com/owner/repo/tree/分支/路径   # 文件夹 (部分克隆 + 稀疏检出, 只取目标目录)
gitx https://github.com/owner/repo/blob/分支/路径/文件  # 单个文件
gitx github.com/owner/repo                          # 链接可省略 https://, 效果同上
gitx owner/repo                                     # 只剩 owner/repo 也行 (等价于 https://github.com/owner/repo)
gitx clone https://github.com/owner/repo 我的目录   # 等价 download
gitx download url1 url2 -o 下载目录                  # 批量: 一次下多个链接 (失败的不影响其余)
gitx download -f 链接.txt -o 下载目录                # 从文本文件读链接 (每行一个, # 注释; - 读标准输入)
```

选项: `--no-proxy` 直连, `--proxy gh-proxy` 换加速源, `--branch <分支>`, `--depth <N>`(0 = 完整克隆),
`--submodules` 连同子模组一起拉取(也走加速), `--fresh` 忽略断点从零下载。
`-o` 默认是保存路径; 多个链接、或指向已存在的目录(以 `/` 结尾)时按目录处理, 每个仓库各建一个子目录。
不给 `--branch` 时, 分支按 **URL 内分支 > 配置项 `branch`(`gitx config set branch develop`) > 远端默认分支** 依次决定。

**断点续传**: 中断的下载会留下 `<文件>.part`, 重跑自动带 `Range` 续传, 不用重来。
下载整仓库后自动把推送地址指回直连 GitHub(存在全局加速规则时用 SSH), 保证 `gitx push` 不被镜像拒绝。

### 工作区: 克隆一次, 之后统一管理

```bash
gitx ws owner/repo                     # 克隆到 ~/gitx-workspaces/repo 并登记
gitx ws owner/repo ~/code/repo         # 克隆到指定目录 (目录已存在则视为父目录)
gitx ws /path/to/local.git             # 本地 / 任意 git 地址也能克隆并登记
gitx ws add ~/code/已有克隆             # 把已有仓库登记进来 (从 origin 识别 owner/repo)
gitx ws | gitx ws list                 # 总览: 分支 / 改动 / 领先落后 / 最近提交 / 路径
gitx ws status [名字...]                # 逐个看改动与上游
gitx ws sync [名字...] [-j 4]           # 逐个 fetch + 变基拉取 (有改动的仓库只 fetch)
gitx ws fetch [名字...] [-j 4]          # 同上: 逐个 git pull; --fetch-only 只更新远端引用
gitx ws each git status -s              # 每个仓库都跑一遍同一条命令
gitx ws path <名字> | gitx ws cd <名字>  # 取绝对路径 / 进入方法 (--shell 供 eval)
gitx ws find <关键词>                    # 按名字 / owner/repo / 路径找
gitx ws rm <名字...> [--delete] [-y]     # 移出清单 (--delete 连目录一起删)
gitx ws prune                           # 清理目录已不存在的清单项
gitx ws root [目录]                      # 查看 / 设置当前工作区的根目录
gitx ws use <名字> [目录]                # 切换默认工作区 (不存在就新建; 目录可放在任何位置)
gitx ws move <新目录>                    # 把当前工作区整个搬过去 (仓库一起搬, 清单路径同步改)
gitx ws spaces                          # 列出所有工作区 (默认的标出来)
gitx ws drop <名字> [--delete]           # 删除工作区 (--delete 连仓库目录一起删)
```

根目录**不限于** `~/gitx-workspaces`: 建的时候直接给目录, 例如 `gitx ws use work ~/code/work`
或 `gitx ws use work /data/repos`; 已有工作区用 `gitx ws move ~/code` 搬走 (登记在别处的外部仓库不搬)。

**默认工作区**: 可以同时有多个工作区 (比如 `work` / `oss`), 每个有自己的根目录和仓库清单;
`gitx ws use work` 之后, 不带 `-s` 的命令都作用在 `work` 上。临时换一个用 `-s 名字`:
`gitx ws -s oss list` / `gitx ws sync -s oss`; 脚本里还可以用环境变量 `GITX_WS_SPACE=oss`。
优先级: `-s/--space` > `GITX_WS_SPACE` > 清单里的默认工作区。

名字默认取仓库名, 重名自动加后缀 (`repo-2`) 不会互相覆盖; 清单在 `~/.config/gitx/workspaces.json`,
纯本地状态 —— 删掉只丢清单, 不动任何仓库; 旧版单工作区清单读取时自动升级。
新工作区的根目录默认是 `~/gitx-workspaces/<名字>` (默认工作区是 `~/gitx-workspaces`);
`gitx ws use <名字> <目录>` / `gitx ws root <目录>` / `gitx config set workspace <目录>` 都能改,
单次克隆还可以 `--root` 临时指定。
克隆同样走加速, 失败会自动清掉半截目录。

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
gitx https://github.com/owner/repo/releases/latest              # 最新发布(等价 .../releases)
gitx https://github.com/owner/repo/releases/download/v1.0.0/文件名  # 单个附件
gitx https://github.com/owner/repo/releases --list              # 只看清单
```

实现要点: 走 `api.github.com/repos/{owner}/{repo}/releases`(经加速镜像访问), 已登录 `gh` 或配置
`token` 时自动带上认证(限额 60 → 5000 次/小时); 附件按 `browser_download_url` 直下并显示进度条,
支持断点续传; 该 Release 没有附件时自动回退到源码包。

Release 的加速源可以**单独设置**(不影响克隆 / 同步 / 搜索等其它功能):

```bash
gitx proxy release              # 查看 Release 当前用的加速源 (与全局对比)
gitx proxy release on v4        # Release 走 v4; 其它功能仍走全局 (默认 v6)
gitx proxy release off          # Release 直连; 其它功能照旧走加速
gitx proxy release follow       # 取消独立设置, 跟随全局加速源 (默认)
```

一次性的 `--proxy <源>` / `--no-proxy` 仍然优先级最高, 对单条命令生效。

### 发行版管理 (创建 / 上传 / 编辑 / 删除, 交给已登录的 gh)

发布方的一条龙: 上面 `gitx release` 只管**下载**, 这里只管**发布**。写操作全部交给已登录的
`gh`, 本工具只拼参数、不接触写入令牌(仓库写权限由 gh 自己的登录态决定);
没装 / 没登录 gh 会给出中文提示 (只下载附件不需要 gh)。

```bash
gitx publish                            # 列出发行版 (含草稿与预发布): 标签 / 名称 / 状态 / 发布 / 创建
gitx publish --no-drafts --no-prereleases -n 50   # 只列正式版, 最多 50 条
gitx publish view                       # 看最新发行版: 状态 / 时间 / 说明首行 / 附件清单
gitx publish view v1.0.5 --web          # 指定标签, 并顺手打开网页
gitx publish create v1.0.5 dist/*.tar.gz dist/*.whl -T "gitx 1.0.5" -F 发布说明.md
gitx publish create v1.0.5-pre2 dist/* -T "gitx 1.0.5-pre2 (预发布)" -F 说明.md -p
gitx publish create v1.0.5 dist/*.whl -d     # 先建草稿, 检查无误后再发布
gitx publish upload v1.0.5 dist/*.whl --clobber   # 给已有发行版补传附件 (同名先删后传)
gitx publish edit v1.0.5 --no-draft          # 把草稿正式发布
gitx publish edit v1.0.5 --no-prerelease --latest   # 预发布转正式, 并标记为最新
gitx publish edit v1.0.5 -n "$(cat 新说明.md)"       # 改说明 (或 -F 新说明.md, -F - 读标准输入)
gitx publish delete v1.0.5-pre1 --cleanup-tag       # 删除发行版(会确认), --cleanup-tag 连标签一起删
gitx publish list --repo cli/cli -n 10       # 看别人的发行版 (owner/repo 或链接都行)
```

| 子命令 | 作用 | 常用选项 |
| --- | --- | --- |
| `publish` / `publish list` | 列出发行版 | `-n` 条数, `--no-drafts` / `--no-prereleases` 过滤, `-R` 目标仓库 |
| `publish view` | 发行版详情 + 附件清单 | `--web` 打开网页, 标签留空 = 最新 |
| `publish create` | 创建发行版并上传附件 | `-T` 标题, `-n` / `-F` 说明, `-p` 预发布, `-d` 草稿, `--target` / `--verify-tag` / `--generate-notes` / `--latest`+`--no-latest` |
| `publish upload` | 补传附件 | `--clobber` 同名先删后传 |
| `publish edit` | 改标题 / 说明 / 预发布 / 草稿 / 最新 | `--prerelease`+`--no-prerelease`, `--draft`+`--no-draft`, `--latest`+`--no-latest`, `--tag` 改标签名 |
| `publish delete` | 删除发行版 | `--cleanup-tag` 连标签一起删, `-y` 跳过确认 |

附件参数直接给构建产物 (`dist/*.tar.gz dist/*.whl`), 通配符由 gh 展开, 上传前本地先检查文件是否存在;
说明可用 `-F -` 从标准输入读, 于是能和 `RELEASE_TEMPLATE.md` 的"取到第一个 `---` 为止"配合
(用管道, 别用 `<(...)` 进程替换 —— 进程替换的 fd 不会传给 gitx 拉起的 gh, gh 会报
`open /dev/fd/63: no such file or directory`):

```bash
sed -n '1,/^---$/p' RELEASE_TEMPLATE.md | gitx publish create v1.0.5 dist/*.tar.gz dist/*.whl -T "gitx 1.0.5" -F -
```

> 发版就是这个命令: `uv build --out-dir dist` 产出 wheel + 源码包, 再
> `sed -n '1,/^---$/p' RELEASE_TEMPLATE.md | gitx publish create <标签> dist/* -T "gitx X.Y.Z" -F -`
> 一把建好发行版; 补传附件 / 改说明 / 删草稿 / 看列表同样交给 `gitx publish`。

### 工作流 Actions (交给已登录的 gh)

CI 跑得怎么样、日志在哪、产物怎么拿, 一条命令看完。工作流本身跑在 GitHub 上,
`gitx` 只负责"看与操作", 同样不接触令牌 (权限由 `gh` 的登录态决定):

```bash
gitx actions                              # 最近 20 次运行: 运行号 / 状态 / 工作流 / 标题 / 分支 / 触发 / 时间
gitx actions -n 50 -b main -s failure      # 只看 main 分支失败的 (状态名用 gh 的: queued / success / failure ...)
gitx actions -w build.yml -e workflow_dispatch   # 按工作流文件与触发事件过滤
gitx actions view                         # 交互式挑一次运行看详情 (作业表: 状态 + 耗时)
gitx actions view 1234 --verbose           # 连每个步骤一起列出来
gitx actions view 1234 --log-failed        # 只看失败步骤的日志 (交给 gh 打印, 保留它的配色)
gitx actions view 1234 --web              # 在浏览器打开这次运行
gitx actions watch 1234 --compact          # 实时盯到结束 (只显示相关 / 失败的步骤)
gitx actions rerun 1234 --failed           # 只重跑失败的作业 (含它们的依赖)
gitx actions cancel 1234                  # 取消 (卡住不动时加 --force)
gitx actions download 1234 -D 产物目录      # 下载运行产物 (每个产物一个子目录)
gitx actions workflows -a                  # 列工作流: 名称 / 状态 / 路径 / 编号 (含已停用)
gitx actions dispatch build.yml -F version=1.0.6 -r main   # 手动触发 workflow_dispatch
```

| 子命令 | 作用 | 常用选项 |
| --- | --- | --- |
| `actions` / `actions list` | 列出最近的运行 | `-n` 条数, `-w` 工作流, `-b` 分支, `-s` 状态, `-e` 事件, `-u` 触发人, `-R` 仓库, `-a` 含停用工作流 |
| `actions view` | 运行详情 + 作业表 | `--verbose` 连步骤, `--job` 单看某个作业, `--attempt` 第几次尝试, `--log` / `--log-failed` / `--web`, `--exit-status` |
| `actions watch` | 实时盯到结束 | `-i` 刷新间隔, `--compact`, `--exit-status` |
| `actions rerun` | 重跑 | `--failed` 只重跑失败的作业, `-j` 单个作业, `--debug` |
| `actions cancel` | 取消运行 | `--force` |
| `actions download` | 下载运行产物 | `-D` 目录, `-N` 产物名 (可重复), `-p` 通配 |
| `actions workflows` | 列工作流 | `-n` 条数, `-a` 含已停用 |
| `actions dispatch` | 手动触发 | `-r` 分支/标签, `-F 键=值` (支持 `@文件`), `-f 键=值` (原样字符串), `--json` 读标准输入 |

运行号可以省略: 那时由 `gh` 弹出交互式选择器让人挑 (需要终端), 直接从列表里选。

### 账号 (gh 登录态)

`gitx` 自己的只读 API (`search` / `stat` / `pr` 列表 / `release`) 本来就是复用 `gh` 的令牌,
这里把登录态本身也管起来, 顺带给个把令牌喂进配置的快捷方式:

```bash
gitx auth                                # 看登录了哪些账号: 主机 / 账号 / 状态 / git 协议
gitx auth --active                       # 只看当前账号
gitx auth login --web                    # 浏览器登录 (不带选项则交给 gh 交互询问方式)
echo <令牌> | gitx auth login --with-token          # 用令牌登录 (不进命令行历史)
gitx auth logout                          # 退出登录 (多账号时由 gh 列出来挑)
gitx auth switch                          # 切换当前账号
gitx auth refresh -s workflow             # 补权限 (加 workflow 才能操作 Actions)
gitx auth token                           # 打印当前令牌 (可直接接管道)
gitx auth token --save                    # 顺手写进 gitx 配置: API 限额 60 -> 5000 次/小时
gitx auth setup-git                       # 让 git 的 https 推送 / 拉取走 gh 的凭据
```

| 子命令 | 作用 | 常用选项 |
| --- | --- | --- |
| `auth` / `auth status` | 登录状态表 | `--active` 只看当前账号, `--show-token` 交给 gh 连令牌一起显示, `--hostname` (企业版) |
| `auth login` | 登录 | `--web`, `--with-token`, `-p ssh\|https`, `-s` 额外权限, `--clipboard`, `--skip-ssh-key`, `--insecure-storage` |
| `auth logout` | 退出登录 | 位置参数给账号名可跳过交互 |
| `auth switch` | 切换当前账号 | 位置参数给账号名可跳过交互 |
| `auth refresh` | 调整授权范围 | `-s` 补权限, `--remove-scopes` 收回, `--reset-scopes` 重置 |
| `auth token` | 打印令牌 | `--save` 写进 gitx 配置, `-u` 指定账号 |
| `auth setup-git` | 配置 git 凭据 | `--force` |

登录 / 退出 / 切换 / 刷新都由 `gh` 自己做交互 (设备码、浏览器、SSH 密钥), gitx 原样透传它的输出;
没登录时 `gitx auth` 给的是中文提示, 而不是 gh 的英文原文。

### 我的仓库 (挑一个 -> 编辑界面, 交给已登录的 gh)

`gitx repos` 是"自己的仓库"面板: 先用 ↑↓ 挑一个仓库(最多同时渲染 5 行, 超出的随光标滚动),
回车就进**仓库编辑界面** —— 界面上先摊开这个仓库的当前设置(描述 / 主页 / 话题 / 可见性 / 默认分支 /
功能开关 / 模板 / star), 再让你一项一项地改, 改完自动刷新一遍, 选"完成"退出。

挑选器里**直接打字即筛选**; 仓库多到记不住名字时用 `-q` 按关键词搜 (`gh search repos`, 搜得到全部,
不受"只取前 `-n` 个"的限制); 挑选器底部也有一条「用关键词搜全部仓库」, 挑着挑着想起关键词, 选中它
就能现场搜一遍再接着挑 (中文也能打进去筛, 不必切成英文关键词)。

**结果会缓存**: 仓库列表 / 搜索 / 详情 / 分支都记在 `~/.cache/gitx` (默认 5 分钟, 走 `cache_ttl`),
所以同一批仓库反复挑、反复看设置时不再每次都等 gh 的几秒往返 (`repos list -n 3` 实测 7.9s → 1.4s);
任何写操作(改设置 / 收藏 / 改名 / 归档 / 删除 / 新建 / 复刻 / 同步)之后自动作废, 不会看到旧数据;
想立刻要 GitHub 上的最新状态就加 `--fresh` (想整体关掉缓存: `gitx config set cache false`)。

```bash
gitx repos                     # 挑仓库 -> 编辑界面 (改描述 / 话题 / 可见性 / 默认分支 / 功能开关 ...)
gitx repos -n 5                # 只取最近 5 个仓库来挑 (只想看前几个就给个小数字)
gitx repos -q dotfile          # 按关键词搜我的仓库 (搜得到全部, 不受 -n 限制)
gitx repos -o cli -n 20        # 看别人的仓库 (还能按 --visibility / -l 语言 / -t 话题 / --source 过滤)
gitx repos -o cli list         # 过滤项写在子命令前后都行 (等价于 repos list -o cli)
gitx repos -q pet list         # 列出搜索命中的仓库 (子命令与 -q 可组合)
gitx repos --fresh             # 不吃缓存, 重新向 GitHub 取一次列表
gitx repos edit owner/repo     # 跳过挑选, 直接进这个仓库的编辑界面
gitx repos edit owner/repo -d "新描述" -t cli -t 工具 --no-wiki   # 非交互: 直接给选项
gitx repos list                # 表格形式列出我的仓库: 仓库 / 描述 / 可见性 / ★ / 语言 / 更新 / 标记
gitx repos view owner/repo     # 看当前设置 (--web 打开网页)
gitx repos clone owner/repo    # 克隆到本地 (和 gitx download 一样走加速, 推送仍直连)
gitx repos create my-tool --source . --push --public -d "一句话介绍"   # 新建 (交给 gh)
gitx repos fork cli/cli --clone       # 复刻到自己的账号 (--org 到组织, --fork-name 改名)
gitx repos rename owner/repo 新名字    # 改名 (新名字留空会问一次)
gitx repos archive owner/repo         # 归档 (unarchive 取消归档)
gitx repos sync owner/repo -s 上游/仓库  # 与上游 / 源仓库对齐 (--force 硬对齐)
gitx repos star cli/cli               # 收藏 (unstar 取消收藏)
gitx repos starred                   # 浏览收藏: ↑↓ 挑, 跨过第 10 条才向 GitHub 取下一批 10 条
gitx repos starred -l -n 30          # 表格列出前 30 个收藏 (--all 一直翻页到取完)
gitx repos starred -o cli            # 看别人公开的收藏
gitx repos starred --sort updated --json   # 按更新时间排序, 输出 JSON 给脚本
gitx repos set-default owner/repo     # 设为当前目录的默认仓库 (之后少写 -R)
gitx repos delete owner/repo -y       # 删除 (不可恢复, 需要 delete_repo 权限)
```

| 子命令 | 作用 | 常用选项 |
| --- | --- | --- |
| `repos` | 挑仓库 -> 进编辑界面 | `-q` 关键词搜 (全量, 不受 `-n` 限制), `-n` 一次取几个仓库来挑, `-o` 谁的仓库, `--visibility` / `-l` / `-t` / `--source` / `--fork` / `--archived` / `--no-archived` 过滤 |
| `repos list` | 仓库表格 (给 `-q` 就是搜索结果) | 同上 |
| `repos edit` | 改设置 (不给选项 = 进编辑界面) | `-d` 描述, `-H` 主页, `-t` / `--remove-topic` 话题, `--visibility` (会确认), `-b` 默认分支, `--template`+`--no-template`, `--issues`+`--no-issues` / `--wiki` / `--projects` / `--discussions`, `-y` 跳过可见性确认 |
| `repos view` | 看当前设置 | `--web` 打开网页; 结果走缓存, 要最新状态先在 `repos` 前加 `--fresh` |
| `repos clone` | 克隆 (公开走加速, 私有交给 gh) | `-D` 目录, `-d` 深度 (0 = 完整克隆) |
| `repos create` | 新建仓库 | `-d` 描述, `-H` 主页, `--visibility`, `--readme`, `-g` gitignore 模板, `--license`, `-p` 模板仓库, `-s` 本地目录当源, `--push` / `-c` / `--no-issues` / `--no-wiki` / `--team` |
| `repos fork` | 复刻 | `-c` 顺手克隆, `--remote`, `--org`, `--fork-name`, `--default-branch-only` |
| `repos rename` | 改名 | 位置参数给新名字, 留空会问一次 |
| `repos archive` / `repos unarchive` | 归档 / 取消归档 | |
| `repos sync` | 与源仓库对齐 | `-s` 源仓库, `-b` 分支, `--force` |
| `repos star` / `repos unstar` | 收藏 / 取消收藏 | |
| `repos starred` | 浏览收藏的仓库: ↑↓ 挑一个, 越过已加载的最后一条自动取下一页 | `-n` 每页条数 (默认 10), `-o` 看别人公开收藏, `--sort created\|updated`, `--order asc\|desc`, `-l` 表格, `--all` 全部, `--json`, `--fresh` |
| `repos set-default` | 设为当前目录的默认仓库 | |
| `repos delete` | 删除仓库 | `-y` 跳过确认 |

**收藏浏览** (`gitx repos starred`) 默认每次只向 GitHub 取 `-n` 个 (10 个),
用 ↑↓ 挑; 光标继续向下越过已加载的最后一条时会自动再取下一批, 所以收藏几千个也能立刻打开。
挑中后可克隆 / 登记到工作区 / 看概览 / 打开网页 / 取消收藏 (取消后立刻从列表消失, 可接着浏览)。
`-l` 直接出表格, `--all` 一直翻页到取完, `--json` 给脚本, `-o` 看别人公开的收藏。

编辑界面里的每一次修改都走 `gh repo edit`, 而且**只把变了的项组成参数**(描述改成原样不发请求,
想清空就把那一项删干净再回车); 改可见性会先提示副作用(掉 star / 断掉复刻关系)并要求确认。
所有子命令的仓库参数都能省略 —— 省略时先弹出同一个上下键挑选器, 所以 `gitx repos view` /
`gitx repos star` / `gitx repos delete` 都能一路选下来; 挑选器的条数由 `gitx repos` 的 `-n` 决定
(例: `gitx repos -n 5 delete` 只在前 5 个仓库里挑)。

### 探索 (新)

```bash
gitx search                                 # 交互式搜索: 问关键词 -> 结果表 -> ↑↓ 挑一个 -> 再选动作
gitx search "cli 工具" -n 10                # 搜 GitHub 仓库 (按 ★ 排序, 默认加速)
gitx search "neovim" --language go          # 限定语言
gitx search "neovim" -i                     # 带关键词进交互界面 (挑完还能接着挑)
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

`gitx search` 不给关键词就是**交互式搜索**: 先问一次搜索词(回车用上一次的词), 结果照常列成表,
然后用 ↑↓ 挑一个仓库(直接打字即筛选), 再选对它做什么 —— 下载到本地(走加速) / 看仓库概览(`gitx stat`
同一套输出) / 打开网页; 挑完能接着挑下一个, 想换关键词就选「换个关键词再搜」, 因此一轮搜索里
可以连着挑好几个仓库。`-i` 是给带了关键词也想进这个界面的场合; `-d` 则是"搜完直接挑一个下载"的
快捷方式, 适合只想下载的时候。

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
gitx fetch --prune                  # 只更新远端引用 (不动工作区), 清理远端已删除的分支
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

### 分支

```bash
gitx branch                            # 分支表: 上游 / 领先落后 / 最近提交
gitx branch -a                         # 含远端跟踪分支 (等价 gitx branches -a)
gitx branch new 新功能                  # 从当前 HEAD 新建分支
gitx branch new 修复 --from v0.6.1 -s   # 从标签/提交新建并立即切换 (-s)
gitx switch 修复                        # 切换 (远端有同名分支时自动建立跟踪)
gitx switch -c 实验                     # 新建并切换
gitx switch -                           # 回到上一个分支
gitx switch --detach 3f1a2b             # 切到某次提交 / 标签 (游离 HEAD)
gitx branch rename 新名字                # 重命名当前分支
gitx branch rename 新名字 -o 旧名字       # 重命名指定分支
gitx branch delete 旧分支                # 删除已合并的本地分支 (未合并会提示)
gitx branch delete 实验 --force          # 强制删除 (未合并也会先确认一次)
gitx branch delete 旧分支 -r             # 删 origin 上的远端分支
gitx branch upstream                    # 看当前分支的上游与领先/落后
gitx branch upstream --set origin/main  # 关联上游
gitx branch upstream --unset            # 取消上游关联
gitx merge 新功能                        # 合并进当前分支 (冲突时给出继续/放弃提示)
gitx merge --abort                      # 放弃正在进行的合并
gitx rebase main                        # 变基到 main (冲突: --continue / --skip / --abort)
gitx rebase -i main                     # 交互式变基 (压缩 / 改写 / 丢弃提交)
```

`gitx branch` 的一次性数据来自单次 `for-each-ref`(比逐个分支起进程快一个数量级);
`gitx fetch` 走加速, `--prune` 会顺手清掉远端已删除的跟踪分支。

### 提交与改动

```bash
gitx commit -m "修复登录超时"      # 提交已暂存的改动
gitx commit -a -m "顺手改个错字"    # 提交所有已跟踪文件的改动
gitx commit --amend --no-edit     # 修订上一次提交 (沿用原信息)
gitx diff                         # 上色渲染的工作区改动 (rich.syntax 高亮)
gitx diff --staged                # 暂存区 vs HEAD
gitx diff --stat / --name-only    # 只看统计 / 只看文件名
gitx discard 文件1 目录/ 文件2      # 丢弃工作区改动 (会确认, 不可恢复)
gitx discard --staged 文件         # 只取消暂存, 保留文件内容
gitx clean                        # 先预览未跟踪文件, 确认后删除
gitx clean -d -y                  # 连未跟踪的目录一起删, 跳过确认
gitx clean -x                     # 连 .gitignore 忽略的文件也删 (危险, 会确认)
```

### 暂存与标签

```bash
gitx stash                        # 列出暂存的改动 (stash@{N} / 时间 / 说明)
gitx stash save "改到一半"          # 暂存当前改动 (工作区恢复干净; -u 连未跟踪文件)
gitx stash show -p                # 看某条暂存的具体 diff (序号: gitx stash show 1 -p)
gitx stash pop                    # 恢复并删除 (gitx stash pop 1 指定序号)
gitx stash apply 1                # 恢复但保留该条暂存
gitx stash drop 1                 # 删除一条 (会确认)
gitx stash clear                  # 清空所有暂存 (会确认)

gitx tag                          # 标签列表: 类型 / 时间 / 提交 / 说明
gitx tag new v1.0.0 "首个正式版"    # 附注标签 (无说明 = 轻量标签)
gitx tag push v1.0.0              # 推送指定标签 (推送直连, 镜像不支持推送)
gitx tag push                     # 推送全部标签
gitx tag delete v1.0.0            # 删本地标签
gitx tag delete v1.0.0 -r         # 连 origin 上的标签一起删
```

### 协作与进阶 (远程 / 子模组 / PR / 缓存 / 自更新)

```bash
gitx remote                             # 列出全部远程 (拉取 / 推送地址)
gitx remote add upstream https://github.com/owner/repo   # 加远程: 拉取走加速, 推送直连
gitx remote set-url origin https://github.com/owner/repo # 改地址 (自动同步推送地址)
gitx remote show upstream / rename / remove             # 查看 / 重命名 / 删除
# 未知参数仍透传 git: gitx remote -v / gitx remote prune origin

gitx submodule                          # 子模组状态 (提交是否对齐 / 未初始化 / 冲突)
gitx submodule add https://github.com/owner/repo libs/x  # 添加 (拉取走加速)
gitx submodule update                   # 拉取子模组 (默认 --init --recursive, 走加速)
gitx submodule update --remote          # 跟踪子模组远端最新提交
gitx submodule sync                     # 地址同步成 .gitmodules 的配置
gitx submodule remove libs/x            # 删除 (含 .gitmodules 条目与本地缓存)

gitx pr                                 # 当前仓库的开放 PR
gitx pr list cli/cli --state all -n 30  # 任意仓库, 各种状态
gitx pr view 1234                       # 看某个 PR 的标题 / 状态 / 正文 (--web 顺手打开)
gitx pr create -t "标题" -b "正文"      # 用已登录的 gh 创建 (--fill 用提交信息, --draft 草稿)

gitx cache                              # 看 ~/.cache/gitx 的内容与占用
gitx cache clear                        # 清空缓存 (可再生的数据, 下次自动重建)

gitx upgrade                            # 自更新到最新版本 (查 Release 与下 wheel 都走加速)
gitx upgrade --check                    # 只检查是否有新版本
```

子模组加速的原理与下载一致: 用 `git -c url.<镜像>/.insteadOf=<原地址>` 让本次命令
把 github.com 重写到镜像 (规则不落盘)。远程管理则反过来 —— 拉取写加速地址、推送写直连
(存在 insteadOf 规则时用 SSH), 这样 `gitx remote add` 出来的远程开箱即可用。
`gitx pr` 的读取走加速 API, 创建交给 `gh` (写入鉴权不经过本工具)。

### 加速管理

```bash
gitx proxy            # 查看状态(表格: 加速源 / Release 加速源 / insteadOf / 配置文件)
gitx proxy auto       # 自动测速(git 克隆端点: v6 / v4 / gh-proxy / 直连), 选用最快的
gitx proxy on         # 开启加速(v6.gh-proxy.org)
gitx proxy on v4      # 换用 IPv4 端点(v4.gh-proxy.org)
gitx proxy off        # 关闭加速(直连)
gitx proxy default    # 恢复默认加速源
gitx proxy set https://gh-proxy.com   # 自定义加速源
gitx proxy release    # 查看 Release 专用加速源
gitx proxy release on v4              # 只给 Release 换加速源(其它功能照旧)
gitx proxy release off                # Release 直连(其它功能仍走加速)
gitx proxy release follow             # 取消独立设置, 跟随全局
gitx proxy http http://127.0.0.1:7890 # 设置 git 的 HTTP(S) 代理(本地代理软件)
gitx proxy http off   # 取消 git 代理
gitx proxy install    # 写入 git 全局 insteadOf 规则, 让普通 git 命令也走加速
gitx proxy uninstall  # 移除上述规则
gitx proxy test       # 测试加速源连通性(git 克隆 / raw / API; Release 独立设置时会一并测试)
```

### 性能: 守护进程与缓存 (默认关闭 / 默认开启)

**缓存** (`cache = true`, 默认开): 可再生的网络结果记在 `~/.cache/gitx`, 少跑一趟网络也少用一次
API 限额 —— 目前记的是 GitHub API 的只读响应 (仓库概览 / 搜索 / 发布列表, 默认 5 分钟)、远端默认
分支探测 (1 小时)。写操作 (如发布发行版) 之后缓存自动作废, 所以不会看到刚改完的旧数据。

```bash
gitx cache             # 缓存目录 + 占用 + 条目数
gitx cache list        # 明细: 缓存键 / 写入时间 / 有效期 / 状态
gitx cache prune       # 只清已过期的
gitx cache clear       # 全清 (下次使用自动重建)
```

**召唤守护进程** (`daemon = false`, 默认关): 低配机上 Python 每次都要重新导入 typer / rich
那一大堆模块 (约 1-2 秒), 占了 `gitx status` 这类命令的大半耗时。打开之后, 运行**任意** gitx
命令时若发现后台没有守护进程, 就顺手拉起一个: 它先把这些模块导入好, 之后的命令把"参数 + 工作
目录 + 环境变量 + 标准输入输出"交给它, 由它 **fork 一个已经预热的子进程**来执行 —— 省掉重复导入,
每条命令仍跑在自己的进程里 (状态不互相污染, Ctrl+C 只影响当次)。附带的改动是配色: 开了守护进程
后 `palette = auto` 会**用终端自己的调色板**而不是内置真彩色, 因此低配终端也不会因为 24 位色而卡顿;
想固定用某一种就 `gitx config set palette mocha|terminal`。

```bash
gitx config set daemon true   # 打开 (之后第一条命令会自动召唤)
gitx daemon                   # 看状态: 配置 / 进程 / 套接字 / 空闲退出 / 实际配色
gitx daemon start|stop|restart
```

细节: 守护进程走 `~/.cache/gitx/daemon.sock` (Unix 域套接字, 不占端口、不监听网络), 空闲
`daemon_idle` 秒 (默认 300) 自己退出, 不留常驻进程; 升级后版本号变了会自动让客户端回退本地执行;
它起不来或半路断掉, 命令照常本地跑 —— 最坏只是没变快, 功能不受影响。

### 配置

配置文件是 **TOML**（带中文注释, 人类可读可改）: `~/.config/gitx/config.toml`
（或 `$XDG_CONFIG_HOME/gitx/config.toml`）。改完即生效, 用 `gitx config set` 改写时注释也不会丢。
旧版的 `config.json` 首次运行会自动迁移成 `config.toml`（原文件保留为 `config.json.bak`）。

```bash
gitx config                 # 查看配置(表格)
gitx config edit            # 用 $VISUAL / $EDITOR 直接编辑配置文件
gitx config path            # 只打印配置文件路径
gitx config set depth 0     # 默认完整克隆
gitx config set branch develop   # 默认分支 (下载时 URL 未带分支则用它, 空 = 远端默认)
gitx config set dest ~/下载  # 默认下载目录 (支持 ~; 命令行给的路径优先)
gitx config set resume false     # 关掉断点续传
gitx config set sync_rebase false  # gitx sync 用合并而非变基 (--merge 仍可临时覆盖)
gitx config set cache true       # 开启 ~/.cache/gitx 缓存 (接口响应 / 默认分支 / 版本查询)
gitx config set cache_ttl 600    # 缓存有效期改成 10 分钟 (0 = 不缓存)
gitx config set daemon true      # 召唤守护进程: 低配机上省掉每条命令的启动开销
gitx config set daemon_idle 900  # 守护进程空闲 15 分钟后自己退出
gitx config set palette terminal # 配色改用终端自己的调色板 (mocha = 内置真彩色)
gitx config set remote upstream  # 默认远程名 (info / url / web / push 不带 -r 时用)
gitx config set search_limit 20  # gitx search 的默认条数
gitx config set repos_limit 50   # gitx repos 的默认条数
gitx config set color never      # 关闭彩色输出 (auto / never)
gitx config set assume_yes true  # 处处跳过确认, 相当于每条命令都带 -y
gitx config set message 更新 # 默认提交信息
gitx config set token ghp_xxx   # 设置 API token (提高限额到 5000 次/小时, 显示时自动打码)
gitx config set release_proxy v4       # 等价于 gitx proxy release set v4 (空值 = 跟随全局)
gitx config reset           # 恢复默认配置
gitx doctor                 # 环境自检(git/gh/token/仓库/加速源/编码)
gitx status / gitx log --oneline   # git 子命令直接透传 (原生 init: gitx git init)
gitx dowload ...            # 子命令笔误会给出形近提示
```

透传规则: `branch` / `switch` / `merge` / `rebase` / `fetch` / `stash` / `tag` / `commit` /
`diff` / `discard` / `clean` 现在都是 gitx 自己的命令 (有中文提示、确认与加速支持);
其余词仍原样交给 git (`gitx status` / `gitx log --oneline` / `gitx blame ...`),
需要未经改写的行为时用 `gitx git <任意命令>` 显式透传。

环境变量 `GITX_PROXY=off|v6|v4|gh-proxy|https://...` 可设置全局默认加速源,
`GITX_RELEASE_PROXY=...` 单独覆盖 Release 功能的加速源。

## 开发与文档

文档按"谁看"分册, **不要通读全部** (尤其 AI: 只读跟当前任务相关的那一份):

| 要看什么 | 去哪看 |
| --- | --- |
| 装 / 升级 / 卸载 | [INSTALL.md](./INSTALL.md) |
| 命令怎么用、有哪些配置 | 本文件 (上面那些章节) |
| 实现要点 / 实测数字 / 源码结构 / 开发约定 | [doc/开发.md](./doc/开发.md) |
| 怎么发版 (步骤清单) | [doc/发布流程.md](./doc/发布流程.md) |
| 发布说明正文 (每版改写) | [RELEASE_TEMPLATE.md](./RELEASE_TEMPLATE.md) |
| 给 AI agent 的命令速查与配置表 | [skill/gitx/SKILL.md](./skill/gitx/SKILL.md) |

快速开始开发:

```bash
uv run python -m gitx --help               # 跑源码 (不用先安装)
uv run python -m gitx doctor               # 环境自检
uv build --out-dir dist                    # 构建 wheel + 源码包 (发布用)
uvx ruff check src/gitx                    # 静态检查 (规则见 pyproject.toml)
```

本仓库的版本管理与提交用 `jj` (colocated: `.jj/` 与 `.git/` 并存), 写操作别用 git 命令。

## 许可

本项目以 [MIT 许可](./LICENSE) 开源, 版权归 `FLT18355` (2026)。
