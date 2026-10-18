# gitx v1.0.8 发布说明

热修: v1.0.7 的 wheel 在 `publish create` / `publish edit` 之后会因 `NameError: cache` 崩 (源码导入漏了一行, 只在预热好的守护进程里才暴露), 这一版只补它 —— 没有别的改动。 没升到 v1.0.7 的直接升 v1.0.8 即可。

## 🐛 修复

- **开了守护进程后有些地方掉色 / 表格按 80 列折行** —— rich 在 `Console` 构造时就把
  "是不是终端 / 多少列 / 支持几种颜色"定死了; 守护进程自己的 stdout/stderr 指向日志文件,
  于是它建出来的控制台记住的是"没有终端 + 80 列 + 不带颜色", fork 出的子进程**哪怕换成你的
  终端**也仍按这个旧结论渲染。现在子进程执行前会按当前 fd **重建控制台**, 颜色与终端宽度都正常;
  配色仍按 `palette` 走 (`auto` = 开了守护进程就用终端自己的 16 色)。

- **`gitx daemon stop` 要等三分钟** —— `stop` / `restart` 自己也被路由进了守护进程, 而它单线程
  收请求: 它正等着这个子进程结束, 子进程却在等它回 stop 的应答, 于是互相等成死锁。现在
  **"管守护进程自己"的命令一律本地执行**, 并且改成**不导入 typer / rich 的快速通道** ——
  `gitx daemon status` / `stop` 从约 2.3 秒降到 1 秒以内 (只剩 Python 启动);
  socket 也加了 30 秒兜底超时, 任何情况下都不会再"卡住不退"。

- **开了守护进程感觉没什么效果** —— 三处一起补:
  1. 第一条命令在召唤成功后**也走守护进程** (之前是"这条本地跑, 下条才快");
  2. 预热清单连带 `prompt_toolkit` / `questionary` / `rich.progress`, 所以**选择器与进度条**
     也不再重付导入 (交互命令原本要重付约 2 秒);
  3. 新增 **`gitx daemon bench`**, 直接在你机器上量"有/没有守护进程"的差距 (各跑几轮取中位数)。

## 🔧 新增

```bash
gitx daemon bench            # 实测这台机器的差距 (本机示例: 本地 1.9s -> 经守护进程 1.4s)
gitx daemon bench -n 5       # 各跑 5 轮
gitx daemon bench --cmd "repos list"   # 换成你要量的命令
gitx daemon status           # 快速通道: 配置 / 进程 / 空闲退出 / 实际配色
gitx daemon stop             # 立刻退出 (毫秒级)
```

## ⚙️ 配置提示

- `palette = auto` (默认) 在**开了守护进程**时用终端自己的 16 色, 没开时用内置 Catppuccin 真彩。
  如果你之前手动设过 `palette = mocha` 又觉得"颜色不对", 用下面这条回到跟随终端:

  ```bash
  gitx config set palette auto
  ```

## 📦 安装/升级

```bash
gitx upgrade                                  # 已在 v1.0.5 及以后: 直接自更新
uv tool install gitx-1.0.8-py3-none-any.whl    # 或装 wheel
gitx daemon restart                            # 守护进程在用的话, 重启它以加载新代码

# 验证
gitx --version        # 应输出 gitx 1.0.7
gitx daemon bench     # 看这台机器上到底省了多少
```

## 🔗 相关

- 源码: https://github.com/FLT18355/gitx/tree/v1.0.8
- 完整变更: `git log v1.0.7..v1.0.8 --oneline`

---

*发布于: 2026-10-18*

<!-- 发布流程 (版本号双改 -> 构建 -> tag -> 建发行版 -> 上传后自检) 见 doc/发布流程.md -->