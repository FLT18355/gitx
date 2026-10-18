# gitx v1.0.6-pre3 发布说明

## 🎉 新增

- **`gitx search`: 交互式搜索** —— 不给关键词就进交互界面: 先问一次搜索词(回车沿用上次的词), 结果照常列成表,
  再上下键挑一个仓库(直接打字即筛选), 然后选对它做什么 —— **下载到本地**(走加速) / **看仓库概览**(`gitx stat`
  同一套输出) / **打开网页**; 挑完能接着挑下一个, 想换关键词就选「换个关键词再搜」, 因此一轮搜索里可以
  连着挑好几个仓库。`-i` 供"带了关键词也想进这个界面"的场合, `-d` 仍是"搜完直接挑一个下载"的快捷方式。

  ```bash
  gitx search                              # 问关键词 -> 结果表 -> 挑一个 -> 下载 / 概览 / 网页
  gitx search -i "vim 插件"                 # 带着关键词进交互界面 (挑完还能接着挑)
  gitx search "vim 插件" --language go -d   # 老用法不变: 搜完直接挑一个下载
  ```

- **`gitx repos`: 会搜了** —— `-q/--search` 走 `gh search repos`, 按关键词搜仓库, **搜得到全部**,
  不再受 `-n` 的"只取前几个"限制; 挑选器底部还加了一条「用关键词搜全部仓库」, 挑着挑着想起关键词,
  选中它就能现场搜一遍再接着挑。搜索结果缺的字段(模板 / 收藏 / 话题)由 `gh repo view` 补齐,
  因此编辑界面的显示与修改都不受影响。

  ```bash
  gitx repos -q dotfile              # 搜自己的仓库 (全量)
  gitx repos -q pet list             # 子命令与 -q 可组合
  gitx repos -o cli -q "cli tool"    # 搜别人的仓库 (-o 谁的)
  ```

## 🐛 修复

- **选择器里中文打不进去**(所有交互界面): questionary 的"打字即筛选"只绑定了 ASCII 字符, 中文按键会落到
  它自己的 "Disallow inserting other text" 分支上被丢弃 —— 于是 `归档 / 下载 / 搜索` 这类中文项, 按提示
  "打字筛选"其实无效。gitx 现在补了一份 `Keys.Any` 绑定并放在它前面(同优先级时先注册者先匹配),
  中文能直接当筛选词, 英文 / 方向键 / 空格勾选的老行为不变。

## 🎨 调整

- **裸 `gitx` 的欢迎页不再画表格**: 换成无边框的对齐两列(命令 + 说明), 窄终端里说明折行会缩进到命令列
  之后, 而不是回到行首 —— 内容与顺序不变, 只是不再有横竖线, 窄终端下也不再被边框挤走正文。

## 📦 安装/升级

```bash
# 方式 1: wheel (uv tool, 带自更新 gitx upgrade)
uv tool install gitx-1.0.6rc3-py3-none-any.whl

# 方式 2: 源码
uv tool install .        # 或: uv tool install git@github.com:FLT18355/gitx.git

# 验证
gitx --version           # 应输出 gitx 1.0.6-pre3
gitx                     # 欢迎页: 无边框的两列速查
gitx search              # 不给关键词 = 交互式搜索 (需要终端)
gitx repos -q dotfile     # 按关键词搜自己的仓库 (需要已安装并登录的 gh)
```

## 🔗 相关

- 源码: https://github.com/FLT18355/gitx/tree/v1.0.6-pre3
- 完整变更: `git log v1.0.6-pre2..v1.0.6-pre3 --oneline`

---

*发布于: 2026-10-18*

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