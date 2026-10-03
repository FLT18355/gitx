# gitx vX.Y.Z 发布说明

## 🎉 新增

- 新增命令 **`gitx <command>`** —— 一句话描述功能
  ```bash
  gitx <command> <示例>   # 说明
  gitx <command>          # 另一种用法
  gitx <command> --json   # JSON 输出 (脚本友好)
  ```

- 核心能力点
  - 功能点 1
  - 功能点 2
  - 功能点 3

## 📊 一次可看 / 做

- 指标 / 数据 1
- 指标 / 数据 2
- ...

## 🔧 技术细节

- 模块/文件: 关键变更点
- `xxx.py`: 新增/重构了什么, 原因/设计
- ...

## 📦 安装/升级

```bash
# 方式 1: 从源码安装
uv tool install .        # 或: uv tool install git@github.com:FLT18355/gitx.git

# 方式 2: 从 Release 附件安装 (wheel)
uv tool install gitx-X.Y.Z-py3-none-any.whl

# 验证
gitx --version           # 应输出 gitx X.Y.Z
gitx doctor              # 环境自检
```

## 🔗 相关

- 源码: https://github.com/FLT18355/gitx/tree/vX.Y.Z
- 完整变更: `git log v<prev>..vX.Y.Z --oneline`
- Issue / PR: #<编号>

---

*发布于: 2026-XX-XX*

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