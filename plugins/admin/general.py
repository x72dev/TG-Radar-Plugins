from __future__ import annotations

from datetime import datetime
import shlex

from tgr.telegram_utils import bullet, format_duration, panel, section, shorten_path, soft_kv
from tgr.version import __version__


PLUGIN_META = {
    "name": "general",
    "version": "5.0.0",
    "description": "TR 管理器通用面板与日志命令",
}


async def cmd_ping(app, event, args):
    stats = app.db.get_runtime_stats()
    await app.safe_reply(
        event,
        panel(
            "TR 管理器 · 在线心跳",
            [section("快速状态", [bullet("管理层运行", format_duration((datetime.now() - app.started_at).total_seconds())), bullet("历史命中", stats.get("total_hits", "0")), bullet("热更新", "事件驱动"), bullet("自动同步", f"{app.config.auto_sync_time} 每日执行" if app.config.auto_sync_enabled else "已关闭", code=False)])],
        ),
        auto_delete=12,
        prefer_edit=False,
    )


async def cmd_status(app, event, args):
    await app.safe_reply(event, app.render_status_message(), auto_delete=0, prefer_edit=False)


async def cmd_version(app, event, args):
    await app.safe_reply(
        event,
        panel(
            "TR 管理器 · 版本信息",
            [
                section("当前构建", [bullet("版本", __version__), bullet("架构", "插件全解耦 / Admin + Core / SQLite WAL"), bullet("终端管理器", "TR")]),
                section("部署位置", [bullet("工作目录", shorten_path(app.config.work_dir), code=False), bullet("交互策略", "轻命令直回 / 重命令排队", code=False)]),
            ],
        ),
        prefer_edit=False,
    )


async def cmd_config(app, event, args):
    await app.safe_reply(event, app.render_config_message(), auto_delete=0, prefer_edit=False)


async def cmd_log(app, event, args):
    scope = "important"
    limit = 15
    tokens = shlex.split(args) if args else []
    for token in tokens:
        lower = token.lower()
        if lower in {"all", "raw", "full", "debug"}:
            scope = "all"
        elif lower in {"important", "key", "critical"}:
            scope = "important"
        elif lower in {"normal", "recent"}:
            scope = "normal"
        elif token.isdigit():
            limit = min(40, max(1, int(token)))
    rows = app.db.recent_logs_for_panel(limit=limit, scope=scope)
    if not rows:
        await app.safe_reply(event, panel("TR 管理器 · 最近关键事件", [section("结果", ["· <i>目前还没有可展示的关键事件。</i>"])]), auto_delete=0, prefer_edit=False)
        return
    blocks = []
    for row in rows:
        detail = row["detail"]
        if len(detail) > 110:
            detail = detail[:109] + "…"
        lines = [f"{row['icon']} <b>{row['title']}</b>", soft_kv("时间", row["created_at"]), soft_kv("摘要", row["summary"])]
        if detail and detail != row["summary"]:
            lines.append(soft_kv("详情", detail))
        blocks.append("\n".join(lines))
    footer = "<i>默认只展示关键事件。发送 <code>{0}log normal 20</code> 可看更多常规事件，发送 <code>{0}log all 20</code> 可看完整事件流。</i>".format(app.config.cmd_prefix)
    await app.safe_reply(event, panel("TR 管理器 · 最近关键事件", [section("事件流", blocks)], footer), auto_delete=0, prefer_edit=False)


async def cmd_jobs(app, event, args):
    await app.safe_reply(event, app.render_jobs_message(), auto_delete=0, prefer_edit=False)


def setup(ctx):
    ctx.register_command("ping", cmd_ping, summary="快速检测管理层是否在线", usage="ping", category="通用面板")
    ctx.register_command("status", cmd_status, summary="查看系统详细状态", usage="status", category="通用面板")
    ctx.register_command("version", cmd_version, summary="查看当前版本与部署信息", usage="version", category="通用面板")
    ctx.register_command("config", cmd_config, summary="查看关键配置快照", usage="config", category="通用面板")
    ctx.register_command("log", cmd_log, summary="查看关键事件日志", usage="log [important|normal|all] [数量]", category="通用面板")
    ctx.register_command("jobs", cmd_jobs, summary="查看后台任务队列", usage="jobs", category="通用面板")
