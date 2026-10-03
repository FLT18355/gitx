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