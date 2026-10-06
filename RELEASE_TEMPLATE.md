# gitx v1.0.4 发布说明

## 🎉 新增

- 配置文件换成 **人类可读的 TOML** —— `~/.config/gitx/config.toml`
  - 逐项中文注释, 按终端显示宽度对齐; `gitx config set` 改写后注释不丢
  - 旧版 `config.json` 首次运行**自动迁移**为 TOML, 原文件保留为 `config.json.bak`
  - 新增 `gitx config edit`(用 `$EDITOR` 直接改)与 `gitx config path`
  - 手改坏了值会"警告一次 + 回退默认", 不再崩溃

- 新增命令 **`gitx upgrade`** —— 自更新, 查 Release 与下载 wheel 都走加速
  ```bash
  gitx upgrade            # 更新到最新版本
  gitx upgrade --check    # 只检查是否有新版本
  gitx upgrade --force    # 同版本 / 更旧也强制重装
  ```

- 新增命令 **`gitx remote`** —— 远程管理 (拉取加速 + 推送直连)
  ```bash
  gitx remote add upstream https://github.com/owner/repo
  gitx remote set-url origin https://github.com/owner/repo
  gitx remote show / rename / remove / list
  # 未知参数仍透传 git: gitx remote -v
  ```

- 新增命令 **`gitx submodule`** —— 子模组一条龙, 拉取同样走加速
  ```bash
  gitx submodule add https://github.com/owner/repo libs/x
  gitx submodule update [--remote]   # 默认 --init --recursive
  gitx submodule status / sync / remove
  ```

- 新增命令 **`gitx pr`** —— Pull Request 列表 / 详情 / 创建
  ```bash
  gitx pr / gitx pr list cli/cli --state all -n 30
  gitx pr view 1234 [--web]
  gitx pr create -t "标题" -b "正文" [--fill] [--draft]   # 交给已登录的 gh
  ```

- 新增命令 **`gitx cache`** —— 缓存查看与清理 (`~/.cache/gitx`, 可再生产数据)
  ```bash
  gitx cache          # 看占用
  gitx cache clear    # 清空 (下次自动重建)
  ```

- **`gitx download` 支持批量** —— 一次下多个链接, 失败的不影响其余
  ```bash
  gitx download url1 url2 -o 下载目录
  gitx download -f 链接.txt -o 下载目录     # 每行一个, # 注释, - 读标准输入
  ```

- **`gitx doctor --fix`** —— 一键修好 `core.quotepath`(中文文件名) / `pull.rebase` / 分支上游

- 新增 5 项配置键: `dest`(默认下载目录) / `resume`(断点续传) / `sync_rebase`(sync 变基或合并) /
  `color`(auto|never) / `assume_yes`(处处跳过确认)

## 🔧 修复

- `gitx pull` 与 `gitx sync --merge` 在分支已分歧时报"需要指定如何调和偏离的分支" ——
  现在显式传 `--no-rebase`(git 2.27+ 未配 `pull.rebase` 时会直接报错)
- `gitx proxy on <非法加速源>` 不再打印完整堆栈, 改为一行中文提示
- `gitx sync_rebase=false` 的合并路径此前实际不可用, 本次一并修好并验证

## 🔧 技术细节

- `config.py`: TOML 读写 + 自动迁移 + 类型校验/归一 + 显示宽度对齐的注释模板
- `upgrade.py` / `remote.py` / `submodule.py` / `pr.py` / `cache.py`: 5 个新模块
- `gitcmd.pull()`: 显式 `--rebase` / `--no-rebase`
- `dispatch.py`: `remote` / `submodule` 部分接管, 未知子命令仍透传 git
- 子模组加速复用 `git -c url.<镜像>.insteadOf`(规则不落盘); `gitx remote` 写 fetch=加速 / push=直连

## 📦 安装/升级

```bash
# 方式 1: 从源码安装
uv tool install .        # 或: uv tool install git@github.com:FLT18355/gitx.git

# 方式 2: 从 Release 附件安装 (wheel)
uv tool install gitx-1.0.4-py3-none-any.whl

# 验证
gitx --version           # 应输出 gitx 1.0.4
gitx doctor              # 环境自检
```

## 🔗 相关

- 源码: https://github.com/FLT18355/gitx/tree/v1.0.4
- 完整变更: `git log v1.0.3..v1.0.4 --oneline`

---

*发布于: 2026-10-06*

<!-- ================================================================
     以下是发布流程规范 (不随发布说明一起贴出), 每次发版必须遵守。
     ================================================================ -->

# 发布流程 (每次发版必做)

## 1. 版本与文档

- `pyproject.toml` 的 `version` 与 `src/gitx/__init__.py` 的 `__version__` 必须同时改成 `X.Y.Z`。
- README 顶部更新本版亮点; INSTALL.md 里的 `gitx --version` 期望值同步更新。

## 2. 构建两个发布附件 (缺一不可)

**每个 Release 必须上传恰好这两个文件** —— 一个源码包 + 一个 uv 构建的 wheel:

| 附件 | 来源 | 作用 |
| --- | --- | --- |
| `dist/gitx-X.Y.Z.tar.gz` | `uv build --sdist` (源代码包) | 无 wheel 环境 / 审计源码 / 国内镜像分发 |
| `dist/gitx-X.Y.Z-py3-none-any.whl` | `uv build --wheel` | `uv tool install <whl>` 一键安装 |

```bash
rm -rf dist
uv build --out-dir dist       # 一次产出 sdist + wheel (uv_build 后端)
ls dist/                      # 必须同时有 .tar.gz 和 .whl
```

> 注意: 必须写 `--out-dir dist`。本机实测不写时 uv 会把产物写到家目录的 `~/dist`,
> 容易和旧版本产物混在一起; 显式指定可保证 `dist/` 里只有本次版本的文件。

```bash
uv run python -m zipfile -l dist/gitx-X.Y.Z-py3-none-any.whl | head   # 抽查包装内容
gitx --version                # 应输出 gitx X.Y.Z
```

源码包也可用 `git archive` 生成 (与 sdist 二选一, 仍按上面的文件名上传):

```bash
git archive --format=tar.gz --prefix=gitx-X.Y.Z/ -o dist/gitx-X.Y.Z.tar.gz vX.Y.Z
```

实测 wheel (隔离环境, 不动全局):

```bash
uv venv -q /tmp/gitx-check
uv pip install -q --python /tmp/gitx-check/bin/python dist/gitx-X.Y.Z-py3-none-any.whl
/tmp/gitx-check/bin/gitx --version     # gitx X.Y.Z
```

## 3. 提交、打标签、上传

```bash
git add -A && git commit -m "vX.Y.Z: <一句话>"
git tag -a vX.Y.Z -m "gitx X.Y.Z"
git push origin main && git push origin vX.Y.Z
gh release create vX.Y.Z \
  dist/gitx-X.Y.Z.tar.gz \
  dist/gitx-X.Y.Z-py3-none-any.whl \
  --title "gitx X.Y.Z" --notes-file <(sed -n '1,/^---$/p' RELEASE_TEMPLATE.md)
```

## 4. 上传后自检

```bash
gh release view vX.Y.Z                      # 确认附件正好两个
gh release download vX.Y.Z -p '*.whl' -D /tmp/gitx-check-dl
uv venv -q /tmp/gitx-verify
uv pip install -q --python /tmp/gitx-verify/bin/python /tmp/gitx-check-dl/*.whl
/tmp/gitx-verify/bin/gitx --version
```