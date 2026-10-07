"""Nuitka 打包入口 —— 编译成独立二进制时从这里进.

`gitx/__main__.py` 里是包内相对导入 (`from . import main`), 直接编译它会让入口
不在包里而失败; 所以单独放一个顶层脚本当入口 (二进制里跑的仍然是 `gitx.main`)。

构建 (见 .github/workflows/release.yml):

    uv pip install . nuitka
    python -m nuitka --onefile --assume-yes-for-downloads --include-package=gitx \
        --output-dir=dist --output-filename=gitx-<版本>-linux-<架构> \
        packaging/nuitka_main.py
"""

from __future__ import annotations

from gitx import main

if __name__ == "__main__":
    main()