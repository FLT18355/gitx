"""GitHub Actions: 工作流与运行管理 (交给已安装并登录的 gh).

工作流本身跑在 GitHub 上, 本模块只负责"看与操作", 同样不接触令牌:

  gitx actions                    列出最近的运行 (可按工作流 / 分支 / 状态过滤)
  gitx actions view [运行号]       看运行详情: 作业 / 步骤 / 耗时 (--log 看日志)
  gitx actions watch [运行号]      实时盯一个运行到结束
  gitx actions rerun [运行号]      重跑 (--failed 只重跑失败的作业)
  gitx actions cancel [运行号]     取消运行
  gitx actions download [运行号]   下载运行产物 (附件)
  gitx actions workflows          列出工作流 (名称 / 状态 / 路径)
  gitx actions dispatch <工作流>   手动触发 workflow_dispatch

运行号可以省略: 那时由 gh 弹出交互式选择器让人挑 (需要终端), 直接从列表里选。
日志 (--log / --log-failed) 与交互式命令由 gh 原样输出, 因此保留它自己的配色与进度。
"""

from __future__ import annotations

from datetime import datetime

from . import console, ghcli

LIST_FIELDS = ("databaseId,displayTitle,workflowName,status,conclusion,headBranch,"
               "event,createdAt,url,headSha")
VIEW_FIELDS = ("attempt,conclusion,createdAt,databaseId,displayTitle,event,headBranch,headSha,"
               "name,number,startedAt,status,updatedAt,url,workflowName,jobs")

# gh 的状态名 -> 中文 (未完成时看 status, 已完成时看 conclusion)
_STATUS = {
    "queued": "排队", "requested": "已请求", "waiting": "等待中", "pending": "待处理",
    "in_progress": "进行中", "completed": "已完成", "action_required": "需处理",
    "cancelled": "已取消", "stale": "已陈旧", "startup_failure": "启动失败",
}
_CONCLUSION = {
    "success": "成功", "failure": "失败", "neutral": "中立", "cancelled": "已取消",
    "skipped": "跳过", "timed_out": "超时", "action_required": "需处理",
    "startup_failure": "启动失败", "stale": "已陈旧",
}
_WORKFLOW_STATE = {"active": "启用", "deleted": "已删除", "unknown": "未知"}


def _state(status: str, conclusion: str) -> str:
    """运行状态 -> 中文: 有结论时以结论为准, 否则用进行中的状态."""
    if conclusion:
        return _CONCLUSION.get(conclusion, conclusion)
    return _STATUS.get(status, status or "-")


def _workflow_state(state: str) -> str:
    if state.startswith("disabled"):
        return "已停用"
    return _WORKFLOW_STATE.get(state, state or "-")


def _clock(value: str) -> str:
    """ISO 时间 -> 本地 月-日 时:分 (空值或解析不出来的原样截断)."""
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%m-%d %H:%M")
    except ValueError:
        return value[:16]


def _elapsed(started: str, ended: str) -> str:
    """ISO 时间对 -> 耗时 (1m23s); 缺一端或起点晚于终点时返回 -."""
    if not started or not ended:
        return "-"
    try:
        seconds = (datetime.fromisoformat(ended) - datetime.fromisoformat(started)).total_seconds()
    except ValueError:
        return "-"
    if seconds < 0:
        return "-"
    if seconds >= 3600:
        return f"{seconds / 3600:.1f}h"
    if seconds >= 60:
        return f"{int(seconds // 60)}m{int(seconds % 60):02d}s"
    return f"{seconds:.0f}s"


def _filters(workflow: str = "", branch: str = "", status: str = "", event: str = "",
             user: str = "") -> list[str]:
    """gh run list 的过滤参数."""
    args: list[str] = []
    if workflow:
        args += ["--workflow", workflow]
    if branch:
        args += ["--branch", branch]
    if status:
        args += ["--status", status]
    if event:
        args += ["--event", event]
    if user:
        args += ["--user", user]
    return args


# ---------------------------------------------------------------- 运行列表 / 详情

def list_runs(target: str = "", *, workflow: str = "", branch: str = "", status: str = "",
              event: str = "", user: str = "", limit: int = 20, all_workflows: bool = False) -> None:
    """列出最近的工作流运行: 运行号 / 状态 / 工作流 / 标题 / 分支 / 触发时间."""
    gh = ghcli.require("管理工作流")
    args = ["run", "list", "-L", str(max(1, limit)), "--json", LIST_FIELDS,
            *_filters(workflow, branch, status, event, user), *ghcli.repo_args(target)]
    if all_workflows:
        args.append("--all")
    data = ghcli.json_out(gh, args, "列出运行")
    if not isinstance(data, list):
        console.error("运行数据异常, 请稍后重试")
    if not data:
        console.info("没有匹配的运行\n提示: 工作流要跑过至少一次; 手动触发用 gitx actions dispatch <工作流>")
        return
    table = console.table("运行号", "状态", "工作流", "标题", "分支", "触发", "时间",
                          title=f"最近 {len(data)} 次运行")
    for run in data:
        table.add_row(
            console.txt(run.get("databaseId") or ""),
            console.txt(_state(str(run.get("status") or ""), str(run.get("conclusion") or ""))),
            console.txt(str(run.get("workflowName") or "-")[:24]),
            console.txt(str(run.get("displayTitle") or "")[:44]),
            console.txt(str(run.get("headBranch") or "-")[:20]),
            console.txt(str(run.get("event") or "-")[:20]),
            console.txt(_clock(str(run.get("createdAt") or ""))),
        )
    console.print(table)
    console.info("看详情: gitx actions view <运行号>   |   看日志: gitx actions view <运行号> --log-failed")


def view(run_id: str = "", target: str = "", *, job: str = "", attempt: int = 0,
         log: bool = False, log_failed: bool = False, verbose: bool = False,
         web: bool = False, exit_status: bool = False) -> None:
    """看运行详情: 标题 / 分支 / 耗时 + 作业表 (--verbose 连步骤一起列).

    [key]--log[/key] / [key]--log-failed[/key] 打印日志, [key]--web[/key] 打开网页版,
    三者都由 gh 原样输出 (保留它自己的配色); [key]--job[/key] 只看某个作业。
    """
    gh = ghcli.require("管理工作流")
    args = ["run", "view", *([run_id] if run_id else []), *ghcli.repo_args(target)]
    if job:
        args += ["--job", job]
    if attempt:
        args += ["--attempt", str(attempt)]
    # 日志与网页版交给 gh 自己渲染 (彩色 / 分页 / 浏览器), 不截获它的输出
    if log or log_failed or web:
        if log:
            args.append("--log")
        if log_failed:
            args.append("--log-failed")
        if web:
            args.append("--web")
        if exit_status:
            args.append("--exit-status")
        ghcli.run(gh, args, "查看运行")
        return
    run = ghcli.json_out(gh, [*args, "--json", VIEW_FIELDS], "查看运行")
    if not isinstance(run, dict):
        console.error("运行数据异常, 请稍后重试")
    head = f"[key]{run.get('databaseId') or run_id or '(最新)'}[/key]  {run.get('displayTitle') or ''!s}"
    state = _state(str(run.get("status") or ""), str(run.get("conclusion") or ""))
    console.print(console.styled(f"{head}  [dim]({state})[/dim]"))
    console.print(console.txt(
        f"工作流: {run.get('workflowName') or '-'}    "
        f"分支: {run.get('headBranch') or '-'}    "
        f"事件: {run.get('event') or '-'}"))
    console.print(console.txt(
        f"提交: {str(run.get('headSha') or '')[:8] or '-'}    "
        f"耗时: {_elapsed(str(run.get('startedAt') or ''), str(run.get('updatedAt') or ''))}    "
        f"时间: {_clock(str(run.get('createdAt') or ''))}"))
    if run.get("url"):
        console.print(console.link(str(run["url"]), str(run["url"])))
    jobs = [item for item in (run.get("jobs") or []) if isinstance(item, dict)]
    if not jobs:
        console.info("该运行没有作业 (可能还在排队)")
    else:
        _jobs_table(jobs)
        if verbose:
            _steps_table(jobs)
    console.info(f"日志: gitx actions view {run.get('databaseId') or run_id} --log-failed"
                 f"   |   产物: gitx actions download {run.get('databaseId') or run_id}")
    if exit_status and str(run.get("conclusion") or "") not in ("success", "neutral", "skipped"):
        raise SystemExit(1)  # 与 gh 的 --exit-status 对齐: 没成功就是非 0


def _jobs_table(jobs: list[dict]) -> None:
    table = console.table("作业", "状态", "耗时", "编号", title=f"作业 {len(jobs)} 个")
    for job in jobs:
        table.add_row(
            console.txt(str(job.get("name") or "-")[:48]),
            console.txt(_state(str(job.get("status") or ""), str(job.get("conclusion") or ""))),
            console.txt(_elapsed(str(job.get("startedAt") or ""), str(job.get("completedAt") or ""))),
            console.txt(job.get("databaseId") or ""),
        )
    console.print(table)


def _steps_table(jobs: list[dict]) -> None:
    """--verbose: 把每个作业的步骤摊平, 直接看出卡在哪一步."""
    rows = [(str(job.get("name") or "-"), step)
            for job in jobs for step in (job.get("steps") or []) if isinstance(step, dict)]
    if not rows:
        return
    table = console.table("作业", "步骤", "状态", "耗时", title=f"步骤 {len(rows)} 个")
    for name, step in rows:
        table.add_row(
            console.txt(name[:24]),
            console.txt(f"{step.get('number') or ''} {step.get('name') or ''}"[:48]),
            console.txt(_state(str(step.get("status") or ""), str(step.get("conclusion") or ""))),
            console.txt(_elapsed(str(step.get("startedAt") or ""), str(step.get("completedAt") or ""))),
        )
    console.print(table)


# ---------------------------------------------------------------- 操作运行

def watch(run_id: str = "", target: str = "", *, interval: int = 0, compact: bool = False,
          exit_status: bool = False) -> None:
    """实时盯着一个运行到结束 (gh 自己刷新; 会阻塞到跑完)."""
    gh = ghcli.require("管理工作流")
    args = ["run", "watch", *([run_id] if run_id else []), *ghcli.repo_args(target)]
    if interval:
        args += ["--interval", str(interval)]
    if compact:
        args.append("--compact")
    if exit_status:
        args.append("--exit-status")
    ghcli.run(gh, args, "盯运行")


def rerun(run_id: str = "", target: str = "", *, failed: bool = False,
          job: str = "", debug: bool = False) -> None:
    """重跑运行: 默认整个重跑, [key]--failed[/key] 只重跑失败的作业 (含依赖)."""
    gh = ghcli.require("管理工作流")
    args = ["run", "rerun", *([run_id] if run_id else []), *ghcli.repo_args(target)]
    if failed:
        args.append("--failed")
    if job:
        args += ["--job", job]
    if debug:
        args.append("--debug")
    ghcli.run(gh, args, "重跑")
    console.done("重跑已提交   盯进度: gitx actions watch" + (f" {run_id}" if run_id else ""))


def cancel(run_id: str = "", target: str = "", *, force: bool = False) -> None:
    """取消运行 ([key]--force[/key] 强制取消, 用于卡住不动的运行)."""
    gh = ghcli.require("管理工作流")
    args = ["run", "cancel", *([run_id] if run_id else []), *ghcli.repo_args(target)]
    if force:
        args.append("--force")
    ghcli.run(gh, args, "取消运行")
    console.done("取消请求已发出")


def download(run_id: str = "", target: str = "", *, dest: str = ".", names: list[str] | None = None,
             patterns: list[str] | None = None) -> None:
    """下载运行的产物到 [key]--dir[/key]: 不给名字就全下, 每个产物一个子目录."""
    gh = ghcli.require("管理工作流")
    args = ["run", "download", *([run_id] if run_id else []), "-D", dest, *ghcli.repo_args(target)]
    for name in names or []:
        args += ["--name", name]
    for pattern in patterns or []:
        args += ["--pattern", pattern]
    console.step(f"下载产物到 {dest} ...")
    ghcli.run(gh, args, "下载产物")
    console.done(f"产物已下载到 {dest}")


# ---------------------------------------------------------------- 工作流

def workflows(target: str = "", *, limit: int = 50, all_workflows: bool = False) -> None:
    """列出仓库里的工作流: 名称 / 状态 / 路径 (/ 停用的也会标出来)."""
    gh = ghcli.require("管理工作流")
    args = ["workflow", "list", "-L", str(max(1, limit)), "--json", "id,name,path,state",
            *ghcli.repo_args(target)]
    if all_workflows:
        args.append("--all")
    data = ghcli.json_out(gh, args, "列出工作流")
    if not isinstance(data, list):
        console.error("工作流数据异常, 请稍后重试")
    if not data:
        console.info("仓库里没有工作流\n提示: 工作流文件放在 .github/workflows/*.yml")
        return
    table = console.table("工作流", "状态", "路径", "编号", title=f"工作流 {len(data)} 个")
    for flow in data:
        table.add_row(
            console.txt(str(flow.get("name") or "-")[:32]),
            console.txt(_workflow_state(str(flow.get("state") or ""))),
            console.txt(str(flow.get("path") or "")),
            console.txt(flow.get("id") or ""),
        )
    console.print(table)
    console.info("手动触发: gitx actions dispatch <工作流文件名或名称>   |   看运行: gitx actions")


def dispatch(workflow: str, target: str = "", *, ref: str = "", fields: list[str] | None = None,
             raw_fields: list[str] | None = None, json_input: bool = False) -> None:
    """手动触发工作流 (工作流里要有 [key]workflow_dispatch[/key] 事件).

    [key]-F 键=值[/key] 会把 [key]@文件[/key] 展开成文件内容, [key]-f 键=值[/key] 原样传字符串;
    参数多时用 [key]--json[/key] 从标准输入读整份 JSON。
    """
    gh = ghcli.require("管理工作流")
    args = ["workflow", "run", workflow, *ghcli.repo_args(target)]
    if ref:
        args += ["--ref", ref]
    for item in fields or []:
        args += ["-F", item]
    for item in raw_fields or []:
        args += ["-f", item]
    if json_input:
        args.append("--json")
    ghcli.run(gh, args, "触发工作流")
    console.done(f"已触发 {workflow}   看进度: gitx actions" + (f" --branch {ref}" if ref else ""))
