PLUGIN_META = {
    "name": "routes",
    "version": "5.0.0",
    "description": "TR 管理器自动归纳与同步插件",
}

import shlex
from tgr.telegram_utils import bullet, escape, normalize_pattern_from_terms, panel, section


async def cmd_routes(app, event, args):
    rows = app.db.list_routes()
    if not rows:
        await app.safe_reply(event, panel("TR 管理器 · 自动归纳规则面板", [section("当前状态", ["· <i>当前没有自动归纳规则。</i>"])]), prefer_edit=False)
        return
    blocks = []
    for row in rows:
        blocks.append(f"<b>{escape(row['folder_name'])}</b>\n· 路由表达式：<code>{escape(row['pattern'])}</code>\n· 更新时间：<code>{escape(row['updated_at'])}</code>")
    await app.safe_reply(event, panel("TR 管理器 · 自动归纳规则面板", [section("当前规则", blocks)]), auto_delete=max(75, app.config.panel_auto_delete_seconds), prefer_edit=False)


async def cmd_addroute(app, event, args):
    tokens = shlex.split(args)
    if len(tokens) < 2:
        await app.safe_reply(event, panel("TR 管理器 · 参数不足", [section("示例", [f"<code>{app.config.cmd_prefix}addroute 示例分组 标题词A 标题词B</code>", f"<code>{app.config.cmd_prefix}addroute 示例分组 项目(?:A|B|C)</code>"])]), prefer_edit=False)
        return
    folder = app.find_folder(tokens[0]) or tokens[0]
    if app.db.get_folder(folder) is None:
        app.db.upsert_folder(folder, None, enabled=False)
    pattern = normalize_pattern_from_terms(tokens[1:])
    app.db.set_route(folder, pattern)
    app.queue_snapshot_flush()
    app.db.log_event("INFO", "ADD_ROUTE", f"{folder} -> {pattern}")
    await app.safe_reply(event, panel("TR 管理器 · 自动归纳规则已保存", [section("规则详情", [bullet("分组", folder), bullet("路由表达式", pattern)])], "<i>后续自动同步会持续扫描新群，并把命中的目标加入路由补群队列。</i>"), prefer_edit=False)


async def cmd_delroute(app, event, args):
    if not args:
        await app.safe_reply(event, panel("TR 管理器 · 参数不足", [section("示例", [f"<code>{app.config.cmd_prefix}delroute 示例分组</code>"])]), prefer_edit=False)
        return
    folder = app.find_folder(args) or args.strip()
    if not app.db.delete_route(folder):
        await app.safe_reply(event, panel("TR 管理器 · 没有找到该自动归纳规则", [section("定位信息", [bullet("分组", folder)])]), prefer_edit=False)
        return
    app.queue_snapshot_flush()
    app.db.log_event("INFO", "DELETE_ROUTE", folder)
    await app.safe_reply(event, panel("TR 管理器 · 自动归纳规则已删除", [section("删除结果", [bullet("分组", folder)])]), prefer_edit=False)


async def cmd_sync(app, event, args):
    await app.run_sync_command(event)


async def cmd_routescan(app, event, args):
    await app.run_route_scan_command(event)


def setup(ctx):
    ctx.register_command("routes", cmd_routes, summary="查看自动归纳规则", usage="routes", category="自动归纳")
    ctx.register_command("addroute", cmd_addroute, summary="新增自动归纳规则", usage="addroute 分组 关键词...", category="自动归纳", heavy=True)
    ctx.register_command("delroute", cmd_delroute, summary="删除自动归纳规则", usage="delroute 分组", category="自动归纳", heavy=True)
    ctx.register_command("sync", cmd_sync, summary="手动执行一次同步", usage="sync", category="自动归纳", heavy=True)
    ctx.register_command("routescan", cmd_routescan, summary="手动执行一次自动归纳扫描", usage="routescan", category="自动归纳", heavy=True)
