"""关键词监控与告警发送。"""

PLUGIN_META = {"name": "keyword_monitor", "version": "6.0.0", "description": "关键词监控与告警", "kind": "core",
    "config_schema": {"bot_filter": {"type": "bool", "default": True, "description": "过滤 bot 消息"}, "max_preview_length": {"type": "int", "default": 760, "description": "告警预览最大字符数"}}}

from tgr.plugin_sdk import PluginContext, RuleHit, build_message_link, collect_rule_hits, display_sender_name, render_alert_message

def setup(ctx: PluginContext):
    log = ctx.log
    bot_filter = ctx.config.get("bot_filter", True)

    @ctx.hook("keyword_monitor", summary="监听群组消息并发送告警", order=100)
    async def on_message(app, event):
        state = app.state
        if state is None:
            return

        # PERF: pre-check — 99% of messages rejected here with 0 API calls
        if not (event.is_group or event.is_channel):
            return
        tasks = state.target_map.get(int(event.chat_id))
        if not tasks:
            return
        msg_text = event.raw_text or ""
        if not msg_text:
            return

        # PERF: check rules BEFORE any API calls (lazy evaluation)
        all_hits: list[tuple[dict, list[RuleHit]]] = []
        sent_routes: set[tuple[int, str]] = set()
        for task in tasks:
            route_key = (int(task["alert_channel"]), str(task["folder_name"]))
            if route_key in sent_routes:
                continue
            hits: list[RuleHit] = []
            for rule_name, pattern in task["rules"]:
                count, first_hit = collect_rule_hits(pattern, msg_text)
                if count > 0 and first_hit:
                    hits.append(RuleHit(rule_name=rule_name, total_count=count, first_hit=first_hit))
            if hits:
                all_hits.append((task, hits))
                sent_routes.add(route_key)

        # No hits → no API calls needed
        if not all_hits:
            return

        # Only now do we call get_chat / get_sender (lazy load)
        chat = await event.get_chat()
        chat_title = getattr(chat, "title", None) or getattr(chat, "username", None) or "未知来源"

        try:
            sender = await event.get_sender()
            if bot_filter and getattr(sender, "bot", False):
                return
            sender_name = display_sender_name(sender, "隐藏用户")
        except Exception:
            sender_name = "广播系统"

        msg_link = build_message_link(chat, int(event.chat_id), int(event.id))

        for task, hits in all_hits:
            alert_text = render_alert_message(
                folder_name=str(task["folder_name"]), chat_title=chat_title,
                sender_name=sender_name, msg_link=msg_link, msg_text=msg_text, rule_hits=hits,
            )
            try:
                await app.client.send_message(int(task["alert_channel"]), alert_text, link_preview=False)
                ctx.db.increment_hit(str(task["folder_name"]))
                ctx.db.log_event("INFO", "HIT", f"{task['folder_name']} <- {chat_title} | rules={len(hits)}")
            except Exception as exc:
                log.exception("告警发送失败: %s", exc)
                ctx.db.log_event("ERROR", "SEND_ALERT", str(exc))

    @ctx.healthcheck
    async def check(app):
        state = getattr(app, "state", None)
        if state is None:
            return "warn", "运行时状态未初始化"
        return "ok", f"监听 {len(state.target_map)} 个目标，{state.valid_rules_count} 条规则"
