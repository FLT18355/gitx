# gitx v1.0.5-pre2 发布说明

## 🎉 新增

- 新增命令 **`gitx publish`** —— 发行版管理, 全部交给已登录的 `gh`(本工具只拼参数, 不接触写入令牌)
  ```bash
  gitx publish                                  # 列出发行版 (含草稿与预发布)
  gitx publish view [标签] [--web]              # 状态 / 时间 / 说明首行 / 附件清单
  gitx publish create v1.0.5 dist/*.tar.gz dist/*.whl \
      -T "gitx 1.0.5" -F 发布说明.md -p         # 创建发行版并上传附件 (附件支持通配)
  gitx publish upload v1.0.5 dist/*.whl --clobber   # 给已有发行版补传附件
  gitx publish edit v1.0.5 --no-draft           # 改标题 / 说明 / 预发布 / 草稿 / 最新
  gitx publish delete v1.0.5 --cleanup-tag      # 删除发行版 (会确认, 可连标签一起删)
  ```

  - 附件直接给构建产物即可 (`dist/*.tar.gz dist/*.whl`), 通配由 gh 展开, 上传前本地先检查文件是否存在
  - 说明用 `-n` 写文本, 或 `-F 说明.md` 从文件读(`-F -` 读标准输入, 配合发布模板 `sed -n '1,/^---$/p'`)
  - 预发布 `-p`, 草稿 `-d`; 三态开关用 `--prerelease/--no-prerelease`、`--draft/--no-draft`、`--latest/--no-latest`
  - `--repo/-R` 接受 `owner/repo` 或 GitHub 链接, 可对任意仓库操作; 不给就用当前仓库
  - 未安装 / 未登录 gh 时给中文提示, 并指出**只下载附件仍用 `gitx release`(只读, 走加速, 不需要 gh)**

- 本版包含 v1.0.5-pre1 的 **skill 优化** (表格化命令速查 / 快速上手 / 常见问题)

## 🔧 技术细节

- `publish.py`: 新模块 —— 拼 `gh release list|view|create|upload|edit|delete` 参数并透传输出;
  `list` / `view` 取 `--json` 后用 Rich 表格渲染 (状态列区分 草稿 / 预发布 / 最新 / 正式);
  `_gh()` 统一检查 gh 是否安装且已登录, `_repo_args()` 解析 `owner/repo` 与链接
- `cli.py`: 新增 `publish` 命令组 (list / view / create / upload / edit / delete) 与面板「发行版管理」
- `dispatch.py`: `publish` 加入自有子命令表 (git 无同名命令, 不影响透传)
- 下载侧一行未动: `gitx release` 仍是 API + 加速的只读路径

## 📦 安装/升级

```bash
# 方式 1: 从源码安装
uv tool install .        # 或: uv tool install git@github.com:FLT18355/gitx.git

# 方式 2: 从 Release 附件安装 (wheel)
uv tool install gitx-1.0.5rc2-py3-none-any.whl

# 验证
gitx --version           # 应输出 gitx 1.0.5-pre2
gitx publish             # 列出发行版 (需要已安装并登录的 gh)
```

## 🔗 相关

- 源码: https://github.com/FLT18355/gitx/tree/v1.0.5-pre2
- 完整变更: `git log v1.0.5-pre1..v1.0.5-pre2 --oneline`

---

*发布于: 2026-10-07*

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

> 文件名注意: 预发布版本会被 uv 按 PEP 440 归一化, `1.0.5-pre2` 构建出的文件名是
> `gitx-1.0.5rc2.tar.gz` / `gitx-1.0.5rc2-py3-none-any.whl`(uv 的限制, 不是笔误), 上传实际文件名即可。

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

# 上传: gh 原生写法, 或本工具自己的发行版管理命令 (参数一一对应)
gh release create vX.Y.Z \
  dist/gitx-X.Y.Z.tar.gz \
  dist/gitx-X.Y.Z-py3-none-any.whl \
  --title "gitx X.Y.Z" --notes-file <(sed -n '1,/^---$/p' RELEASE_TEMPLATE.md)

gitx publish create vX.Y.Z dist/gitx-X.Y.Z.tar.gz dist/gitx-X.Y.Z-py3-none-any.whl \
  -T "gitx X.Y.Z" [-p 预发布] [-d 草稿] -F -
# 说明从标准输入给 (管道, 不是 <(进程替换) —— 进程替换的 fd 不会传给 gitx 拉起的 gh):
sed -n '1,/^---$/p' RELEASE_TEMPLATE.md | gitx publish create vX.Y.Z dist/*.tar.gz dist/*.whl -T "gitx X.Y.Z" [-p] -F -
```

## 4. 上传后自检

```bash
gh release view vX.Y.Z                      # 确认附件正好两个
gitx publish view vX.Y.Z                    # 同样能看到状态与附件清单
gh release download vX.Y.Z -p '*.whl' -D /tmp/gitx-check-dl
uv venv -q /tmp/gitx-verify
uv pip install -q --python /tmp/gitx-verify/bin/python /tmp/gitx-check-dl/*.whl
/tmp/gitx-verify/bin/gitx --version
```