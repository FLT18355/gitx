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

### 同步

```bash
gitx push                            # 提交并推送(默认信息: 日常同步更新)
gitx push "修复了 bug"               # 带备注
gitx push to https://github.com/owner/repo   # 首次关联远程并推送
gitx push -f                        # 强制推送
gitx pull                           # 拉取(走加速)
gitx pull --rebase
```

### 加速管理

```bash
gitx proxy            # 查看状态
gitx proxy on         # 开启加速(v6.gh-proxy.org)
gitx proxy off        # 关闭加速(直连)
gitx proxy default    # 恢复默认加速源
gitx proxy set https://gh-proxy.com   # 自定义加速源
gitx proxy install    # 写入 git 全局 insteadOf 规则, 让普通 git 命令也走加速
gitx proxy uninstall  # 移除上述规则
gitx proxy test       # 测试加速源连通性
```

### 其它

```bash
gitx config                 # 查看配置
gitx config set depth 0     # 默认完整克隆
gitx config set message 更新 # 默认提交信息
gitx doctor                 # 环境自检
gitx status / gitx log --oneline   # git 子命令直接透传
```

环境变量 `GITX_PROXY=off|v6|gh-proxy|https://...` 可设置全局默认加速源。

## 原理

- 加速 = 在 GitHub 域名 URL 前拼镜像前缀, 如 `https://v6.gh-proxy.org/https://github.com/...`
- 拉取(克隆 / 下载 / API)走加速; 推送走直连 —— 镜像对 `git push` 返回 405
- `gitx proxy install` 利用 git 自身的 `url.<镜像>/.insteadOf` 规则, 全局生效
- 分支自动探测:`git ls-remote --symref` 取默认分支(main/master)
- 文件夹下载: 稀疏检出(`git sparse-checkout --no-cone`), 只拉取目标目录

## 开发

```bash
uv run python -m gitx --help
```
