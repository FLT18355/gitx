"""GitHub 登录态管理 (交给已安装的 gh, 本工具不自己存令牌).

  gitx auth                 看本机登录了哪些账号 (当前账号标出来)
  gitx auth login           登录 (交互; --web 走浏览器, --with-token 从标准输入读)
  gitx auth logout [账号]    退出登录
  gitx auth switch [账号]    切换当前账号
  gitx auth refresh         调整授权范围 (加权限用 --scopes, 重置用 --reset-scopes)
  gitx auth token           打印当前账号的令牌 (--save 顺手写进 gitx 配置)
  gitx auth setup-git       让 git 的 https 推送走 gh 的凭据

登录 / 退出 / 切换 / 刷新都由 gh 自己做交互 (设备码、浏览器、密钥), 因此原样透传它的输出;
只有"查看状态"与"取令牌"两处会把结果整理成表格或直接打印, 方便脚本里用。
gitx 自己的只读 API (search / stat / pr 列表) 也会复用这里的登录态: 有 token 时限额从
60 次/小时升到 5000 次/小时 ([key]gitx auth token --save[/key] 即写入配置)。
"""

from __future__ import annotations

import json

from . import config, console, ghcli


def status(*, hostname: str = "", active_only: bool = False, show_token: bool = False) -> None:
    """看登录状态: 主机 / 账号 / 状态 / 协议 (哪个账号是当前的).

    没登录时给中文提示并以非 0 退出 (gh 自己的提示是英文的, 这里就不透传了)。
    """
    gh = ghcli.find("查看登录状态")
    accounts = _accounts(gh, hostname)
    if not accounts:
        console.error("没有登录任何 GitHub 账号\n"
                      "提示: gitx auth login 登录 (--web 走浏览器, --with-token 读标准输入)")
    if show_token:  # 想连令牌一起看就交给 gh 打印 (它负责打码 / 显示明文)
        ghcli.run(gh, ["auth", "status", *(["--hostname", hostname] if hostname else []),
                       "--show-token"], "查看登录状态")
        return
    if active_only:
        accounts = [item for item in accounts if item.get("active")]
        if not accounts:
            console.warn("没有当前账号 (登录了但没有活跃账号)")
            console.info("切换账号: gitx auth switch")
            return
    table = console.table("主机", "账号", "状态", "git 协议", title=f"已登录 {len(accounts)} 个账号")
    for item in accounts:
        ok = str(item.get("state") or "") == "success"
        mark = "当前" if item.get("active") else ("正常" if ok else "异常")
        table.add_row(
            console.txt(item.get("host") or ""),
            console.txt(item.get("login") or ""),
            console.txt(mark),
            console.txt(item.get("gitProtocol") or ""),
        )
    console.print(table)
    console.info("切换账号: gitx auth switch   |   权限范围: gitx auth refresh -s workflow")


def _accounts(gh: str, hostname: str = "") -> list[dict]:
    """`gh auth status --json hosts` -> 账号列表 (没登录 / 解析不出来就是空表).

    gh 在没登录时也会以 0 退出并给出 {"hosts":{}}, 因此这里看的是结果为空而不是退出码。
    """
    args = ["auth", "status", "--json", "hosts"]
    if hostname:
        args += ["--hostname", hostname]
    code, out, _ = ghcli.capture(gh, args)
    if code != 0:
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return []
    hosts = data.get("hosts") if isinstance(data, dict) else None
    if not isinstance(hosts, dict):
        return []
    return [item for items in hosts.values() if isinstance(items, list)
            for item in items if isinstance(item, dict)]


# ---------------------------------------------------------------- 登录 / 退出

def login(*, hostname: str = "", git_protocol: str = "", web: bool = False,
          with_token: bool = False, scopes: list[str] | None = None, clipboard: bool = False,
          skip_ssh_key: bool = False, insecure_storage: bool = False) -> None:
    """登录 GitHub (不要求已经登录): 不加选项时由 gh 交互询问登录方式."""
    gh = ghcli.find("登录")
    args = ["auth", "login"]
    if hostname:
        args += ["--hostname", hostname]
    if git_protocol:
        args += ["--git-protocol", git_protocol]
    if web:
        args.append("--web")
    if with_token:
        args.append("--with-token")  # 令牌从标准输入读, 不进命令行历史
    for scope in scopes or []:
        args += ["--scopes", scope]
    if clipboard:
        args.append("--clipboard")
    if skip_ssh_key:
        args.append("--skip-ssh-key")
    if insecure_storage:
        args.append("--insecure-storage")
    ghcli.run(gh, args, "登录")
    console.done("登录完成   查看状态: gitx auth")


def logout(user: str = "", *, hostname: str = "") -> None:
    """退出登录: 给账号名可跳过 gh 的交互选择."""
    gh = ghcli.require("退出登录", login=False)
    args = ["auth", "logout"]
    if user:
        args += ["--user", user]
    if hostname:
        args += ["--hostname", hostname]
    ghcli.run(gh, args, "退出登录")
    console.done("已退出登录")


def switch(user: str = "", *, hostname: str = "") -> None:
    """切换当前账号 (多个账号时用; 不指定账号由 gh 列出来让人挑)."""
    gh = ghcli.require("切换账号")
    args = ["auth", "switch"]
    if user:
        args += ["--user", user]
    if hostname:
        args += ["--hostname", hostname]
    ghcli.run(gh, args, "切换账号")
    console.done("已切换当前账号   查看状态: gitx auth")


def refresh(*, hostname: str = "", scopes: list[str] | None = None,
            remove_scopes: list[str] | None = None, reset_scopes: bool = False,
            clipboard: bool = False, insecure_storage: bool = False) -> None:
    """调整授权范围 (例如给工作流加 [key]workflow[/key] 权限)."""
    gh = ghcli.require("调整授权范围")
    args = ["auth", "refresh"]
    if hostname:
        args += ["--hostname", hostname]
    for scope in scopes or []:
        args += ["--scopes", scope]
    for scope in remove_scopes or []:
        args += ["--remove-scopes", scope]
    if reset_scopes:
        args.append("--reset-scopes")
    if clipboard:
        args.append("--clipboard")
    if insecure_storage:
        args.append("--insecure-storage")
    if len(args) == 2:  # 只写了 gitx auth refresh: 没有要改的权限, 别白跑一次设备码流程
        console.error("请说明要改的范围: gitx auth refresh -s workflow"
                      " (或 --remove-scopes / --reset-scopes)")
    ghcli.run(gh, args, "调整授权范围")
    console.done("授权范围已更新   查看状态: gitx auth")


# ---------------------------------------------------------------- 令牌与 git 凭据

def token(*, hostname: str = "", user: str = "", save: bool = False) -> None:
    """打印当前账号的令牌 (给脚本用时可直接 `gitx auth token`).

    [key]--save[/key] 会把它写进 gitx 配置 ([key]token[/key] 项), 之后 gitx 的只读 API
    走这个令牌, 限额从 60 次/小时升到 5000 次/小时; 只打印则不改任何配置。
    """
    gh = ghcli.require("取令牌")
    args = ["auth", "token"]
    if hostname:
        args += ["--hostname", hostname]
    if user:
        args += ["--user", user]
    if not save:
        ghcli.run(gh, args, "取令牌")
        return
    code, out, err = ghcli.capture(gh, args)
    if code != 0:
        console.error(f"取令牌失败\n{err}" if err else "取令牌失败")
    value = out.strip()
    if not value:
        console.error("gh 没有返回令牌\n提示: 先 gitx auth login")
    config.save({**config.load(), "token": value})
    console.done(f"令牌已写入 {config.config_path()} (token 项, 共 {len(value)} 位)")


def setup_git(*, hostname: str = "", force: bool = False) -> None:
    """让 git 走 gh 的凭据 (https 推送 / 拉取不用再输账号密码)."""
    gh = ghcli.require("配置 git 凭据")
    args = ["auth", "setup-git"]
    if hostname:
        args += ["--hostname", hostname]
    if force:
        args.append("--force")
    ghcli.run(gh, args, "配置 git 凭据")
    console.done("已把 gh 的凭据接进 git")
