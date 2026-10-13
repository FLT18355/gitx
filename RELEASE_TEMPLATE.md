# gitx vX.Y.Z 发布说明

> 这是**模板**: 本文件第一个 `---` 之前的内容就是贴进发行版的说明 (`sed -n '1,/^---$/p'`),
> 发版时把 `X.Y.Z` 换成实际版本号, 按小节填本版内容, 空小节整段删掉 (别把占位符发出去)。

## 🎉 新增

- **<一句话亮点>** —— <用户能看到的变化, 可直接复制粘贴的命令示例>

  | 附件 | 说明 |
  | --- | --- |
  | `gitx-X.Y.Z-py3-none-any.whl` | uv 构建的 wheel (`uv tool install <whl>`, 支持 `gitx upgrade` 自更新) |
  | `gitx-X.Y.Z.tar.gz` | 源码包 (审计源码 / 无 wheel 环境) |

## 🔧 修复

- **`<命令>` 的 `<症状>`** —— <根因 (哪一行 git 行为导致的)>; 现在 <新行为>。
  <有实测数字就写上: 裸 git N 次里失败 M 次, gitx N 次全成功>

## 📦 安装/升级

```bash
# 方式 1: wheel (uv tool, 带自更新 gitx upgrade)
uv tool install gitx-X.Y.Z-py3-none-any.whl

# 方式 2: 源码
uv tool install .        # 或: uv tool install git@github.com:FLT18355/gitx.git

# 验证
gitx --version           # 应输出 gitx X.Y.Z (预发布是 X.Y.ZrcN)
gitx doctor              # 环境自检
```

## 🔗 相关

- 源码: https://github.com/FLT18355/gitx/tree/vX.Y.Z
- 完整变更: `git log <上个标签>..vX.Y.Z --oneline`

---

*发布于: YYYY-MM-DD*

<!-- ================================================================
     以下是发布流程规范 (不随发布说明一起贴出), 每次发版必须遵守。
     ================================================================ -->

# 发布流程 (每次发版必做)

> 发版在本地完成, 没有 CI: `uv build` 出两个附件 (wheel + 源码包), 再用 `gitx publish create` 建发行版。

## 1. 版本与文档

- `pyproject.toml` 的 `version` 与 `src/gitx/__init__.py` 的 `__version__` 必须同时改成 `X.Y.Z`
  (两处不一致时 `gitx --version` 报的就不是实际发布号)。
- 改写本文件顶部 (第一个 `---` 之前) 的发布说明; README 顶部更新本版亮点;
  INSTALL.md 的 `gitx --version` 期望值、`skill/gitx/SKILL.md` 的 `version` 同步更新。
- 预发布版本号写成 `X.Y.Z-preN` (uv 会按 PEP 440 归一化成 `rcN`, 构建出的附件名是 `gitx-X.Y.ZrcN*`, 不是笔误)。

## 2. 构建 (附件恰好 2 个)

```bash
rm -rf dist
uv build --out-dir dist                  # ① wheel + 源码包, 纯 Python 不需要编译器
ls -l dist                               # 应恰好 2 个文件
```

隔离环境实测 wheel 可安装:

```bash
uv venv -q /tmp/gitx-verify
uv pip install -q --python /tmp/gitx-verify/bin/python dist/*.whl
/tmp/gitx-verify/bin/gitx --version
/tmp/gitx-verify/bin/gitx publish -h >/dev/null
```

## 3. 提交、打标签、推送

```bash
git add -A && git commit -m "vX.Y.Z: <一句话>"
git tag -a vX.Y.Z -m "gitx X.Y.Z"
git push origin <当前分支> && git push origin vX.Y.Z
```

## 4. 创建发行版

```bash
# 说明取"本文件第一个 --- 之前"的内容 (用管道, 别用 <(...) 进程替换: fd 不会传给 gh)
sed -n '1,/^---$/p' RELEASE_TEMPLATE.md \
  | gitx publish create vX.Y.Z dist/*.tar.gz dist/*.whl -T "gitx X.Y.Z" -F -
# 预发布加 -p; 想先建草稿检查就加 -d, 之后 gitx publish edit vX.Y.Z --no-draft 正式发布

# 等价的手工方式:
gh release create vX.Y.Z dist/*.tar.gz dist/*.whl --title "gitx X.Y.Z" --verify-tag --notes-file dist/notes.md
```

## 5. 上传后自检 (附件必须正好 2 个)

```bash
gitx publish view vX.Y.Z                        # 附件清单应该只有 wheel + tar.gz
gh release download vX.Y.Z -p '*.whl' -D /tmp/gitx-check-dl
uv venv -q /tmp/gitx-check && uv pip install -q --python /tmp/gitx-check/bin/python /tmp/gitx-check-dl/*.whl
/tmp/gitx-check/bin/gitx --version
```