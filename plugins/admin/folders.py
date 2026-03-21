PLUGIN_META = {
    "name": "folders",
    "version": "5.0.0",
    "description": "TR 管理器分组查看与启停插件",
}

from tgr.telegram_utils import bullet, escape, html_code, panel, section


async def cmd_folders(app, event, args):
    rows = app.db.list_folders()
    if not rows:
        await app.safe_reply(event, panel("TR 管理器 · 分组总览", [section("当前状态", ["· <i>系统里还没有任何分组记录。先执行一次同步，或先在 Telegram 侧创建分组。</i>"])]), prefer_edit=False)
        return
    blocks = []
    for row in rows:
        folder_name = row["folder_name"]
        group_count = app.db.count_cache_for_folder(folder_name)
        rule_count = app.db.count_rules_for_folder(folder_name)
        icon = "🟢" if int(row["enabled"]) == 1 else "⚪"
        blocks.append(f"{icon} <b>{escape(folder_name)}</b>\n· 监听：{html_code('开启' if int(row['enabled']) == 1 else '关闭')}\n· 群组：{html_code(group_count)}\n· 规则：{html_code(rule_count)}")
    await app.safe_reply(event, panel("TR 管理器 · 分组总览", [section("当前分组", blocks)]), auto_delete=max(75, app.config.panel_auto_delete_seconds), prefer_edit=False)


async def cmd_rules(app, event, args):
    if not args:
        await app.safe_reply(event, panel("TR 管理器 · 缺少参数", [section("示例", [f"<code>{app.config.cmd_prefix}rules 示例分组</code>"])]), prefer_edit=False)
        return
    folder = app.find_folder(args)
    if folder is None:
        await app.safe_reply(event, panel("TR 管理器 · 找不到该分组", [section("提示", [f"· 先发送 <code>{app.config.cmd_prefix}folders</code> 查看系统已识别的分组。"])]), prefer_edit=False)
        return
    rows = app.db.get_rules_for_folder(folder)
    if not rows:
        await app.safe_reply(event, panel(f"TR 管理器 · {folder} 的规则面板", [section("当前状态", ["· <i>该分组还没有任何启用中的规则。</i>"])]), prefer_edit=False)
        return
    blocks = []
    for row in rows:
        blocks.append(f"<b>{escape(row['rule_name'])}</b>\n· 表达式：<code>{escape(row['pattern'])}</code>\n· 更新时间：<code>{escape(row['updated_at'])}</code>")
    await app.safe_reply(event, panel(f"TR 管理器 · {folder} 的规则面板", [section("已启用规则", blocks)]), auto_delete=max(80, app.config.panel_auto_delete_seconds), prefer_edit=False)


async def cmd_enable(app, event, args):
    if not args:
        await app.safe_reply(event, panel("TR 管理器 · 缺少参数", [section("示例", [f"<code>{app.config.cmd_prefix}enable 示例分组</code>"])]), prefer_edit=False)
        return
    folder = app.find_folder(args)
    if folder is None:
        await app.safe_reply(event, panel("TR 管理器 · 找不到该分组", [section("提示", [f"· 先发送 <code>{app.config.cmd_prefix}folders</code> 查看列表。"])]), prefer_edit=False)
        return
    app.db.set_folder_enabled(folder, True)
    app.queue_snapshot_flush()
    app.queue_core_reload("enable_folder", folder)
    app.db.log_event("INFO", "ENABLE_FOLDER", folder)
    await app.safe_reply(event, panel("TR 管理器 · 分组监控已开启", [section("当前动作", [bullet("分组", folder), bullet("状态", "开启")])], "<i>这项变更已直接通知 Core 立即重载，不再依赖短周期轮询。</i>"), prefer_edit=False)


async def cmd_disable(app, event, args):
    if not args:
        await app.safe_reply(event, panel("TR 管理器 · 缺少参数", [section("示例", [f"<code>{app.config.cmd_prefix}disable 示例分组</code>"])]), prefer_edit=False)
        return
    folder = app.find_folder(args)
    if folder is None:
        await app.safe_reply(event, panel("TR 管理器 · 找不到该分组", [section("提示", [f"· 先发送 <code>{app.config.cmd_prefix}folders</code> 查看列表。"])]), prefer_edit=False)
        return
    app.db.set_folder_enabled(folder, False)
    app.queue_snapshot_flush()
    app.queue_core_reload("disable_folder", folder)
    app.db.log_event("INFO", "DISABLE_FOLDER", folder)
    await app.safe_reply(event, panel("TR 管理器 · 分组监控已关闭", [section("当前动作", [bullet("分组", folder), bullet("状态", "关闭")])], "<i>对应监听目标已通知 Core 立即重载，新的匹配范围会尽快生效。</i>"), prefer_edit=False)


def setup(ctx):
    ctx.register_command("folders", cmd_folders, summary="查看全部 Telegram 分组状态", usage="folders", category="分组管理")
    ctx.register_command("rules", cmd_rules, summary="查看指定分组规则", usage="rules 分组名", category="分组管理")
    ctx.register_command("enable", cmd_enable, summary="开启指定分组监控", usage="enable 分组名", category="分组管理")
    ctx.register_command("disable", cmd_disable, summary="关闭指定分组监控", usage="disable 分组名", category="分组管理")
