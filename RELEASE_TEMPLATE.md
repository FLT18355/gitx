# gitx v1.1.0-pre2b 发布说明

v1.1.0 的第二个预览版修复重发：克隆默认取完整历史，文档改为纯 git 管理。

## 🐛 克隆历史

- 修复 `gitx owner/repo` / `gitx download` 克隆出的仓库历史不完整：默认不再浅克隆，
  直接取全部历史；需要浅克隆时显式传 `--depth N`（只取最近 N 个提交）。
- `gitx ws clone` / `gitx repos clone` 同步改为默认完整历史；移除配置项 `depth`
  （旧配置里的 `depth` 会被忽略，浅克隆改用 `--depth N`）。

## 📚 文档

- 去除 `jj` 管理说明：发布流程、开发约定与 README 统一为 `git`（提交 / 分支 / 标签）。
- 克隆相关文案更新为「默认完整历史」，浅克隆需显式 `--depth N`。

## 📦 安装 / 升级

```bash
gitx upgrade                                  # 已在旧版预览版: 加 --force 可强制重装
uv tool install gitx-1.1.0rc2.post1-py3-none-any.whl
gitx daemon restart                           # 守护进程在用的话, 重启以加载新代码

# 验证
gitx --version        # 应输出 gitx 1.1.0-pre2.post1
```

> 标签写作 `v1.1.0-pre2b`；PEP 440 不接受 `pre2b`，因此包版本归一化为
> `1.1.0-pre2.post1`，构建出的附件名是 `gitx-1.1.0rc2.post1*`。

## 🔗 相关

- 源码: https://github.com/FLT18355/gitx/tree/v1.1.0-pre2b
- 完整变更: `git log v1.1.0-pre2..v1.1.0-pre2b --oneline`

---

*发布于: 2026-11-16*

<!-- 发布流程 (版本号双改 -> 构建 -> tag -> 建发行版 -> 上传后自检) 见 doc/发布流程.md -->
