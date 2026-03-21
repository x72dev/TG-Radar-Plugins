PLUGIN_META = {
    "name": "rules",
    "version": "5.0.0",
    "description": "TR 管理器规则维护与通知设置插件",
}

import shlex
from tgr.config import load_config, update_config_data
from tgr.telegram_utils import blockquote_preview, bullet, escape, merge_patterns, normalize_pattern_from_terms, panel, section, split_terms, try_remove_terms_from_pattern


async def cmd_addrule(app, event, args):
    tokens = shlex.split(args)
    if len(tokens) < 3:
        await app.safe_reply(event, panel("TR 管理器 · 参数不足", [section("示例", [f"<code>{app.config.cmd_prefix}addrule 示例分组 规则A 监控词A 监控词B</code>", f"<code>{app.config.cmd_prefix}addrule 示例分组 规则A 项目(?:A|B|C)</code>", f"<code>{app.config.cmd_prefix}setrule 示例分组 规则A 全量表达式</code>"])]), prefer_edit=False)
        return
    folder = app.find_folder(tokens[0]) or tokens[0]
    rule_name = tokens[1]
    incoming_pattern = normalize_pattern_from_terms(tokens[2:])
    if app.db.get_folder(folder) is None:
        app.db.upsert_folder(folder, None, enabled=False)
    existing_rows = app.db.get_rules_for_folder(folder)
    existing_rule = next((row for row in existing_rows if row["rule_name"] == rule_name), None)
    merged_pattern = merge_patterns(existing_rule["pattern"] if existing_rule else None, incoming_pattern)
    app.db.upsert_rule(folder, rule_name, merged_pattern)
    app.queue_snapshot_flush()
    app.queue_core_reload("add_rule", f"{folder}/{rule_name}")
    action = "UPDATE_RULE" if existing_rule else "ADD_RULE"
    app.db.log_event("INFO", action, f"{folder}/{rule_name} -> {merged_pattern}")
    new_terms = split_terms(tokens[2:])
    new_terms_preview = " / ".join(new_terms[:6]) + ("…" if len(new_terms) > 6 else "")
    await app.safe_reply(event, panel("TR 管理器 · 规则已追加", [section("规则详情", [bullet("分组", folder), bullet("规则名", rule_name), bullet("新增词项", new_terms_preview, code=False), bullet("当前表达式", merged_pattern)])], f"<i>同名规则默认追加新词并自动去重。若要整条覆盖，请使用 <code>{app.config.cmd_prefix}setrule</code>。</i>"), prefer_edit=False)


async def cmd_setrule(app, event, args):
    tokens = shlex.split(args)
    if len(tokens) < 3:
        await app.safe_reply(event, panel("TR 管理器 · 参数不足", [section("示例", [f"<code>{app.config.cmd_prefix}setrule 示例分组 规则A 新表达式</code>"])]), prefer_edit=False)
        return
    folder = app.find_folder(tokens[0]) or tokens[0]
    rule_name = tokens[1]
    pattern = normalize_pattern_from_terms(tokens[2:])
    if app.db.get_folder(folder) is None:
        app.db.upsert_folder(folder, None, enabled=False)
    app.db.upsert_rule(folder, rule_name, pattern)
    app.queue_snapshot_flush()
    app.queue_core_reload("set_rule", f"{folder}/{rule_name}")
    app.db.log_event("INFO", "UPDATE_RULE", f"{folder}/{rule_name} -> {pattern}")
    await app.safe_reply(event, panel("TR 管理器 · 规则已覆盖", [section("规则详情", [bullet("分组", folder), bullet("规则名", rule_name), bullet("表达式", pattern)])]), prefer_edit=False)


async def cmd_delrule(app, event, args):
    tokens = shlex.split(args)
    if len(tokens) < 2:
        await app.safe_reply(event, panel("TR 管理器 · 参数不足", [section("示例", [f"<code>{app.config.cmd_prefix}delrule 示例分组 规则A</code>", f"<code>{app.config.cmd_prefix}delrule 示例分组 规则A 监控词A</code>"])]), prefer_edit=False)
        return
    folder = app.find_folder(tokens[0]) or tokens[0]
    rule_name = tokens[1]
    terms = tokens[2:]
    rows = app.db.get_rules_for_folder(folder)
    rule = next((row for row in rows if row["rule_name"] == rule_name), None)
    if rule is None:
        await app.safe_reply(event, panel("TR 管理器 · 找不到该规则", [section("定位信息", [bullet("分组", folder), bullet("规则名", rule_name)])]), prefer_edit=False)
        return
    if not terms:
        app.db.delete_rule(folder, rule_name)
        app.queue_snapshot_flush()
        app.queue_core_reload("delete_rule", f"{folder}/{rule_name}")
        app.db.log_event("INFO", "DELETE_RULE", f"{folder}/{rule_name}")
        await app.safe_reply(event, panel("TR 管理器 · 规则已删除", [section("删除结果", [bullet("分组", folder), bullet("规则名", rule_name)])]), prefer_edit=False)
        return
    new_pattern = try_remove_terms_from_pattern(rule["pattern"], terms)
    if not new_pattern:
        app.db.delete_rule(folder, rule_name)
        app.queue_snapshot_flush()
        app.queue_core_reload("clear_rule", f"{folder}/{rule_name}")
        await app.safe_reply(event, panel("TR 管理器 · 规则已清空", [section("删除结果", [bullet("分组", folder), bullet("规则名", rule_name)])]), prefer_edit=False)
        return
    app.db.update_rule_pattern(folder, rule_name, new_pattern)
    app.queue_snapshot_flush()
    app.queue_core_reload("update_rule", f"{folder}/{rule_name}")
    app.db.log_event("INFO", "UPDATE_RULE", f"{folder}/{rule_name} -> {new_pattern}")
    await app.safe_reply(event, panel("TR 管理器 · 规则已更新", [section("新表达式", [f"<code>{escape(new_pattern)}</code>"])]), prefer_edit=False)


async def cmd_setnotify(app, event, args):
    value = app.parse_int_or_none(args)
    update_config_data(app.config.work_dir, {"notify_channel_id": value})
    app.config = load_config(app.config.work_dir)
    app.db.log_event("INFO", "SET_NOTIFY", str(value))
    await app.safe_reply(event, panel("TR 管理器 · 系统通知目标已更新", [section("新配置", [bullet("通知去向", value if value is not None else "Saved Messages"), bullet("覆盖范围", "启动 / 同步 / 更新 / 恢复", code=False)])]), prefer_edit=False)


async def cmd_setalert(app, event, args):
    value = app.parse_int_or_none(args)
    update_config_data(app.config.work_dir, {"global_alert_channel_id": value})
    app.config = load_config(app.config.work_dir)
    app.queue_core_reload("set_alert", str(value))
    app.db.log_event("INFO", "SET_ALERT", str(value))
    await app.safe_reply(event, panel("TR 管理器 · 默认告警频道已更新", [section("新配置", [bullet("默认告警", value if value is not None else "未设置"), bullet("生效范围", "未单独配置告警频道的分组", code=False)])]), prefer_edit=False)


async def cmd_setprefix(app, event, args):
    value = args.strip()
    if not value or len(value) > 3 or " " in value or any(ch in value for ch in ["\\", '"', "'"]):
        await app.safe_reply(event, panel("TR 管理器 · 命令前缀格式无效", [section("输入要求", [bullet("长度", "1-3 个字符", code=False), bullet("限制", "不能包含空格、引号、反斜杠", code=False)])]), prefer_edit=False)
        return
    update_config_data(app.config.work_dir, {"cmd_prefix": value})
    app.db.log_event("INFO", "SET_PREFIX", value)
    app.write_last_message(event.id, "restart")
    await app.safe_reply(event, panel("TR 管理器 · 命令前缀已更新", [section("新前缀", [bullet("命令前缀", value), bullet("试用命令", f"{value}help")])], "<i>接下来会自动重启 Admin / Core，新的前缀会在服务恢复后立刻生效。</i>"), auto_delete=0, prefer_edit=False)
    app.restart_services(delay=1.2)


def setup(ctx):
    ctx.register_command("addrule", cmd_addrule, summary="追加词项到同名规则", usage="addrule 分组 规则名 关键词...", category="规则维护", heavy=True)
    ctx.register_command("setrule", cmd_setrule, summary="直接覆盖整条规则", usage="setrule 分组 规则名 表达式", category="规则维护", heavy=True)
    ctx.register_command("delrule", cmd_delrule, summary="删除整条规则或部分词项", usage="delrule 分组 规则名 [关键词...]", category="规则维护", heavy=True)
    ctx.register_command("setnotify", cmd_setnotify, summary="设置系统通知目标", usage="setnotify ID/off", category="规则维护", heavy=True)
    ctx.register_command("setalert", cmd_setalert, summary="设置默认告警目标", usage="setalert ID/off", category="规则维护", heavy=True)
    ctx.register_command("setprefix", cmd_setprefix, summary="修改 Telegram 命令前缀", usage="setprefix 新前缀", category="规则维护", heavy=True)
