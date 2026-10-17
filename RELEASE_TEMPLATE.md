# gitx v1.0.6-pre2 发布说明

## 🎉 新增

- **`gitx repos`: 我的仓库一条龙** —— 上下键挑一个仓库(最多同时渲染 5 行, 超出的随光标滚动, 打字即筛选) ->
  进**仓库编辑界面**: 先摊开当前设置(描述 / 主页 / 话题 / 可见性 / 默认分支 / 功能开关 / 模板 / star),
  再一项一项地改, 改完自动刷新, 选"完成"退出; 列表 / 克隆 / 新建 / 复刻 / 改名 / 归档 / 同步 / 收藏 /
  设为默认 / 删除一应俱全, 全部交给已登录的 `gh`。

  ```bash
  gitx repos                     # 挑仓库 -> 编辑界面 (改描述 / 话题 / 可见性 ...)
  gitx repos -n 5                # 只取最近 5 个仓库来挑 (只想看前几个就给个小数字)
  gitx repos -n 5 delete         # 子命令也能省略仓库: 只在前 5 个里挑一个删
  gitx repos edit owner/repo     # 跳过挑选, 直接进这个仓库的编辑界面
  gitx repos edit owner/repo -d "新描述" -t cli --no-wiki   # 非交互: 直接给选项
  gitx repos star cli/cli        # 收藏 (unstar 取消)
  ```

- **`gitx actions`: Actions 运行一条龙** —— 不再需要开网页看 CI: 运行列表 / 详情(作业表与耗时, `--verbose` 连步骤) /
  日志 / 实时盯 / 重跑 / 取消 / 产物下载 / 工作流列表 / 手动触发, 全部交给已登录的 `gh`。

  ```bash
  gitx actions                          # 最近运行: 状态 / 工作流 / 标题 / 分支 / 触发 / 时间
  gitx actions -b main -s failure        # 只看 main 上失败的
  gitx actions view 1234 --verbose       # 作业 + 步骤 + 每步耗时
  gitx actions view 1234 --log-failed    # 只看失败步骤的日志
  gitx actions rerun 1234 --failed       # 只重跑失败的作业
  gitx actions download 1234 -D 产物目录  # 下载运行产物
  gitx actions dispatch build.yml -F version=1.0.6   # 手动触发 workflow_dispatch
  ```

- **`gitx auth`: 账号与登录态** —— 状态表(当前账号标出来) / 登录 / 退出 / 切换 / 调权限 / 取令牌 / 配 git 凭据;
  `gitx auth token --save` 把 gh 的令牌写进 gitx 配置, 只读 API 限额从 60 次/小时升到 5000 次/小时。

  ```bash
  gitx auth                      # 登录了哪些账号
  gitx auth login --web          # 浏览器登录
  gitx auth switch               # 切换当前账号
  gitx auth refresh -s workflow  # 补权限
  gitx auth token --save         # 令牌进 gitx 配置 (API 限额 60 -> 5000)
  ```

  | 附件 | 说明 |
  | --- | --- |
  | `gitx-1.0.6rc1-py3-none-any.whl` | uv 构建的 wheel (`uv tool install <whl>`, 支持 `gitx upgrade` 自更新) |
  | `gitx-1.0.6rc1.tar.gz` | 源码包 (审计源码 / 无 wheel 环境) |

## ♻️ 技术细节

- 新增 `ghcli.py`: `gh` 共用层 —— `find` / `require`(安装 + 登录检查) / `run` / `capture` / `json_out` /
  `repo_args`; 原来散在 `publish.py` 与 `pr.py` 的重复实现全部迁过来, `publish` / `pr` / `actions` / `auth` 共用一套
- 新增 `actions.py`: 拼 `gh run list|view|watch|rerun|cancel|download` 与 `gh workflow list|run` 参数;
  `list` / `view` / `workflows` 取 `--json` 后用 Rich 表格渲染 (状态与结论译成中文, 耗时按 ISO 时间对算出 `1m23s`);
  `--log` / `--log-failed` / `watch` / `dispatch` 等交互与流式输出原样透传给 `gh`
- 新增 `auth.py`: `gh auth status` 取 `--json hosts` 渲染成状态表 (没登录时给中文提示, 而非 gh 的英文原文);
  `login` / `logout` / `switch` / `refresh` / `setup-git` 原样透传; `token --save` 把令牌写进 `~/.config/gitx/config.toml`
- `cli.py`: 新增 `actions` 命令组 (list / view / watch / rerun / cancel / download / workflows / dispatch) 与
  `auth` 命令组 (status / login / logout / switch / refresh / token / setup-git), 面板「工作流 (Actions 运行)」与「账号 (登录态)」
- `dispatch.py`: `actions` / `auth` 加入自有子命令表 (git 无同名命令, 不影响透传)
- 下载侧一行未动: `gitx release` 仍是 API + 加速的只读路径 (不需要 gh)

## 📦 安装/升级

```bash
# 方式 1: wheel (uv tool, 带自更新 gitx upgrade)
uv tool install gitx-1.0.6rc1-py3-none-any.whl

# 方式 2: 源码
uv tool install .        # 或: uv tool install git@github.com:FLT18355/gitx.git

# 验证
gitx --version           # 应输出 gitx 1.0.6-pre2
gitx repos -n 5          # 挑一个我的仓库 -> 进编辑界面 (需要已安装并登录的 gh)
gitx repos view cli/cli  # 看别人仓库的当前设置 (只读)
gitx actions -n 5        # 看最近的 Actions 运行 (需要已安装并登录的 gh)
gitx auth                # 看登录了哪些账号
```

## 🔗 相关

- 源码: https://github.com/FLT18355/gitx/tree/v1.0.6-pre2
- 完整变更: `git log v1.0.6-pre1..v1.0.6-pre2 --oneline`

---

*发布于: 2026-10-15*

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