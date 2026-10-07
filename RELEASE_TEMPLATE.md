# gitx v1.0.5 发布说明

## 🎉 新增

- **官方二进制 (免 Python 环境)** —— 从这一版起, 每个发行版提供 **4 个附件**:

  | 附件 | 说明 |
  | --- | --- |
  | `gitx-linux-x86_64` | Nuitka 编译的独立二进制 (x86_64, 单文件、免装 Python) |
  | `gitx-linux-arm64` | Nuitka 编译的独立二进制 (arm64) |
  | `gitx-1.0.5-py3-none-any.whl` | uv 构建的 wheel (`uv tool install <whl>`) |
  | `gitx-1.0.5.tar.gz` | 源码包 (审计源码 / 无 wheel 环境) |

  ```bash
  # 二进制: 下载即用 (URL 固定指向最新正式版, chmod 后直接 sudo install)
  curl -L -o gitx https://github.com/FLT18355/gitx/releases/latest/download/gitx-linux-x86_64
  chmod +x gitx && sudo install -m755 gitx /usr/local/bin/gitx
  gitx --version
  ```

- **新增命令 `gitx publish`** —— 发行版管理, 全部交给已登录的 gh (本工具只拼参数, 不接触写入令牌)
  ```bash
  gitx publish                                  # 列出发行版 (含草稿与预发布)
  gitx publish view [标签] [--web]              # 状态 / 时间 / 说明首行 / 附件清单
  gitx publish create v1.0.5 dist/* -T "gitx 1.0.5" -F 发布说明.md
  gitx publish upload v1.0.5 dist/* --clobber   # 补传附件
  gitx publish edit v1.0.5 --no-draft           # 改标题 / 说明 / 预发布 / 草稿 / 最新
  gitx publish delete v1.0.5 --cleanup-tag      # 删除 (会确认, 可连标签一起删)
  ```

- **发版全自动** —— 新增 GitHub Actions 工作流: 推一个 `v*` 标签就自动构建 4 个附件并创建发行版
  (Nuitka 二进制在 x86_64 与 arm64 原生 runner 上各编一份), 以后发版只走这一条路。

- 包含 1.0.5-pre1 / pre2 的内容: skill 优化 (表格化命令速查 / 快速上手 / 常见问题)、`gitx publish`

## 🔧 修复

- **`gitx merge` / `gitx pull` 的"致命错误：储藏失败"** —— git 在真正合并前会用
  `git stash create` 存一份工作区快照, 只要索引里有 "mtime/大小变了、内容没变" 的条目
  (别的程序正在改写被跟踪的文件, 比如日志/指标文件), 这次快照就会**静默**失败
  (退出码 1 且不打印任何东西), 合并随即只报一句 `致命错误：储藏失败` 而中止。
  现在合并 / 拉取前先 `git update-index -q --refresh` 把这类条目续成干净;
  万一仍在合并瞬间被改写, 会自动刷新重试 (最多 3 次), 最终失败也给中文原因而不是那句 "储藏失败"。
  实测: 一个后台进程每 5ms 用**同样内容**重写被跟踪文件时, 裸 `git merge --no-ff` 60 次里失败 8 次,
  而 `gitx merge` 60 次全部成功。

## 🔧 技术细节

- `publish.py`: 新模块 —— 拼 `gh release list|view|create|upload|edit|delete`, 读取用 `--json` + Rich 表格
- `cli.py`: 新 `publish` 命令组 (list / view / create / upload / edit / delete) 与面板「发行版管理」
- `gitcmd.refresh_index()` / `gitcmd.is_stash_failure()`: 索引 stat 刷新 + 识别 git 快照失败
- `branch.merge()`: 合并前刷新索引, 快照失败自动重试; `gitcmd.pull()`: 拉取前刷新索引
- `packaging/nuitka_main.py` + `.github/workflows/release.yml`: Nuitka
  (`--onefile --assume-yes-for-downloads --include-package=gitx`) 打包 linux x86_64 / arm64;
  uv 打包 wheel + sdist; `gh release create` 自动发布, 并自检"附件正好 4 个"

## 📦 安装/升级

```bash
# 方式 1: 二进制 (最快, 不需要 Python / uv)
curl -L -o gitx https://github.com/FLT18355/gitx/releases/latest/download/gitx-linux-x86_64
chmod +x gitx && sudo install -m755 gitx /usr/local/bin/gitx

# 方式 2: wheel (uv tool, 带自更新 gitx upgrade)
uv tool install gitx-1.0.5-py3-none-any.whl

# 方式 3: 源码
uv tool install .        # 或: uv tool install git@github.com:FLT18355/gitx.git

# 验证
gitx --version           # 应输出 gitx 1.0.5
gitx doctor              # 环境自检
```

## 🔗 相关

- 源码: https://github.com/FLT18355/gitx/tree/v1.0.5
- 完整变更: `git log v1.0.4..v1.0.5 --oneline`
- 发版工作流: `.github/workflows/release.yml`

---

*发布于: 2026-10-07*

<!-- ================================================================
     以下是发布流程规范 (不随发布说明一起贴出), 每次发版必须遵守。
     ================================================================ -->

# 发布流程 (每次发版必做)

> 现在**发版只走 GitHub Actions**: `.github/workflows/release.yml` 会在 `v*` 标签推上去之后
> 自动构建并创建发行版 (4 个附件: 两个 Nuitka 二进制 + wheel + 源码包)。下面的手工步骤是兜底。

## 1. 版本与文档

- `pyproject.toml` 的 `version` 与 `src/gitx/__init__.py` 的 `__version__` 必须同时改成 `X.Y.Z`。
- 改写本文件顶部 (第一个 `---` 之前) 的发布说明; README 顶部更新本版亮点;
  INSTALL.md 的 `gitx --version` 期望值、`skill/gitx/SKILL.md` 的 `version` 同步更新。
- 预发布版本号写成 `X.Y.Z-preN` (uv 会按 PEP 440 归一化成 `rcN`, 构建出的附件名是 `gitx-X.Y.ZrcN*`, 不是笔误)。

## 2. 提交、打标签、推送 (推完就自动发版)

```bash
git add -A && git commit -m "vX.Y.Z: <一句话>"
git tag -a vX.Y.Z -m "gitx X.Y.Z"
git push origin <当前分支> && git push origin vX.Y.Z
```

推送标签后到 Actions 页面看 `发布发行版` 工作流 (三个 job: 读版本 / wheel+源码包 / 两个二进制, 最后创建发行版)。
标签里带 `-` 会自动标记为预发布; 工作流也会校验 `pyproject.toml` 的版本与标签一致, 不一致直接失败。

也可以手动触发 (标签已存在时):

```bash
gh workflow run release.yml -f tag=vX.Y.Z            # 可选 -f prerelease=true/false
gh run watch $(gh run list --workflow=release.yml -L1 --json databaseId --jq '.[0].databaseId')
```

## 3. 手工兜底 (工作流挂了 / 只想本地构建)

```bash
rm -rf dist
uv build --out-dir dist                  # ① wheel + 源码包
uv venv /tmp/nuitka && uv pip install --python /tmp/nuitka/bin/python . nuitka
/tmp/nuitka/bin/python -m nuitka --onefile --assume-yes-for-downloads \
  --include-package=gitx --output-dir=dist \
  --output-filename=gitx-linux-$(uname -m | sed 's/aarch64/arm64/') packaging/nuitka_main.py
ls dist/                                 # 每次恰好 4 个文件
```

```bash
gh release create vX.Y.Z \
  dist/gitx-linux-x86_64 dist/gitx-linux-arm64 dist/*.whl dist/*.tar.gz \
  --title "gitx X.Y.Z" --notes-file <(sed -n '1,/^---$/p' RELEASE_TEMPLATE.md)

# 或者用本工具自己的发行版管理命令 (参数一一对应)
gitx publish create vX.Y.Z dist/* -T "gitx X.Y.Z" -F <(sed -n '1,/^---$/p' RELEASE_TEMPLATE.md)
```

## 4. 上传后自检

```bash
gh release view vX.Y.Z                            # 确认附件正好 4 个
gh release download vX.Y.Z -p 'gitx-linux-*' -D /tmp/gitx-bin
/tmp/gitx-bin/gitx-linux-$(uname -m | sed 's/aarch64/arm64/;s/x86_64/x86_64/') --version
gh release download vX.Y.Z -p '*.whl' -D /tmp/gitx-check-dl
uv venv -q /tmp/gitx-verify && uv pip install -q --python /tmp/gitx-verify/bin/python /tmp/gitx-check-dl/*.whl
/tmp/gitx-verify/bin/gitx --version
```