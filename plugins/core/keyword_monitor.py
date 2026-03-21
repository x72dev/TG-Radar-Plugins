PLUGIN_META = {
    "name": "keyword_monitor",
    "version": "5.0.0",
    "description": "关键词监控与告警发送核心插件",
}

from tgr.core_service import RuleHit, build_message_link, collect_rule_hits, display_sender_name, render_alert_message


async def message_hook(app, event):
    state = app.state
    if state is None:
        return
    if not (event.is_group or event.is_channel):
        return
    tasks = state.target_map.get(int(event.chat_id))
    if not tasks:
        return
    msg_text = event.raw_text or ""
    if not msg_text:
        return
    chat = await event.get_chat()
    chat_title = getattr(chat, "title", None) or getattr(chat, "username", None) or "未知来源"
    try:
        sender = await event.get_sender()
        if getattr(sender, "bot", False):
            return
        sender_name = display_sender_name(sender, "隐藏用户")
    except Exception:
        sender_name = "广播系统"
    msg_link = build_message_link(chat, int(event.chat_id), int(event.id))
    sent_routes: set[tuple[int, str]] = set()
    for task in tasks:
        route_key = (int(task["alert_channel"]), str(task["folder_name"]))
        if route_key in sent_routes:
            continue
        rule_hits: list[RuleHit] = []
        for rule_name, pattern in task["rules"]:
            count, first_hit = collect_rule_hits(pattern, msg_text)
            if count <= 0 or not first_hit:
                continue
            rule_hits.append(RuleHit(rule_name=rule_name, total_count=count, first_hit=first_hit))
        if not rule_hits:
            continue
        sent_routes.add(route_key)
        alert_text = render_alert_message(
            folder_name=str(task["folder_name"]),
            chat_title=chat_title,
            sender_name=sender_name,
            msg_link=msg_link,
            msg_text=msg_text,
            rule_hits=rule_hits,
        )
        try:
            await app.client.send_message(int(task["alert_channel"]), alert_text, link_preview=False)
            app.db.increment_hit(str(task["folder_name"]))
            app.db.log_event("INFO", "HIT", f"{task['folder_name']} <- {chat_title} | rules={len(rule_hits)} hits={sum(item.total_count for item in rule_hits)}")
        except Exception as exc:
            app.logger.exception("failed to send alert: %s", exc)
            app.db.log_event("ERROR", "SEND_ALERT", str(exc))


async def healthcheck(app):
    state = app.state
    if state is None:
        return "warn", "运行时状态尚未初始化"
    return "ok", f"监听目标 {len(state.target_map)} 个，生效规则 {state.valid_rules_count} 条"


def setup(ctx):
    ctx.register_message_hook("keyword_monitor", message_hook, summary="监听群组消息并按规则发送告警", order=100)
    ctx.set_healthcheck(healthcheck)
