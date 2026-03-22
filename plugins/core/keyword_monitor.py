"""关键词监控与告警发送。"""

PLUGIN_META = {"name": "keyword_monitor", "version": "6.0.0", "description": "关键词监控与告警", "kind": "core",
    "config_schema": {"bot_filter": {"type": "bool", "default": True, "description": "过滤 bot 消息"}, "max_preview_length": {"type": "int", "default": 760, "description": "告警预览最大字符数"}, "sender_id_blacklist": {"type": "list", "default": [], "description": "屏蔽的用户 ID 列表"}, "sender_name_keywords": {"type": "list", "default": [], "description": "屏蔽的昵称关键词列表（包含即屏蔽）"}}}

from tgr.plugin_sdk import PluginContext, RuleHit, build_message_link, collect_rule_hits, display_sender_name, render_alert_message

def setup(ctx: PluginContext):
    log = ctx.log
    bot_filter = ctx.config.get("bot_filter", True)

    @ctx.hook("keyword_monitor", summary="监听群组消息并发送告警", order=100)
    async def on_message(app, event):
        state = getattr(app, "state", None)
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
            # 用户 ID 黑名单
            sid_blacklist = ctx.config.get("sender_id_blacklist", [])
            if sid_blacklist and int(getattr(sender, "id", 0)) in [int(x) for x in sid_blacklist]:
                return
            sender_name = display_sender_name(sender, "隐藏用户")
            # 昵称关键词屏蔽
            name_keywords = ctx.config.get("sender_name_keywords", [])
            if name_keywords and sender_name:
                lower_name = sender_name.lower()
                for kw in name_keywords:
                    if str(kw).lower() in lower_name:
                        return
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
    @ctx.command("block", summary="屏蔽用户 ID 或昵称关键词", usage="block id 123456 / block name 广告", category="监控")
    async def cmd_block(app, event, args):
        parts = args.strip().split(None, 1)
        if len(parts) < 2:
            return await ctx.reply(event, ui.panel("TG-Radar · 屏蔽", [ui.section("用法", [
                f"<code>{app.config.cmd_prefix}block id 用户ID</code>  按 ID 屏蔽",
                f"<code>{app.config.cmd_prefix}block name 关键词</code>  按昵称屏蔽",
                f"<code>{app.config.cmd_prefix}unblock id 用户ID</code>  取消屏蔽",
                f"<code>{app.config.cmd_prefix}unblock name 关键词</code>  取消屏蔽",
                f"<code>{app.config.cmd_prefix}blocklist</code>  查看屏蔽列表",
            ])]), prefer_edit=False)
        kind, val = parts[0].lower(), parts[1].strip()
        if kind == "id":
            lst = list(ctx.config.get("sender_id_blacklist", []))
            try:
                v = int(val)
            except ValueError:
                return await ctx.reply(event, ui.panel("TG-Radar · 错误", [ui.section("", ["ID 必须是数字"])]), prefer_edit=False)
            if v not in lst:
                lst.append(v)
                ctx.config.set("sender_id_blacklist", lst)
            await ctx.reply(event, ui.panel("TG-Radar · 已屏蔽", [ui.section("用户 ID", [ui.bullet("ID", v)])]), prefer_edit=False)
        elif kind == "name":
            lst = list(ctx.config.get("sender_name_keywords", []))
            if val not in lst:
                lst.append(val)
                ctx.config.set("sender_name_keywords", lst)
            await ctx.reply(event, ui.panel("TG-Radar · 已屏蔽", [ui.section("昵称关键词", [ui.bullet("关键词", val)])]), prefer_edit=False)
        else:
            await ctx.reply(event, ui.panel("TG-Radar · 错误", [ui.section("", [f"类型必须是 id 或 name"])]), prefer_edit=False)

    @ctx.command("unblock", summary="取消屏蔽", usage="unblock id 123456 / unblock name 广告", category="监控")
    async def cmd_unblock(app, event, args):
        parts = args.strip().split(None, 1)
        if len(parts) < 2:
            return await ctx.reply(event, ui.panel("TG-Radar · 用法", [ui.section("", [f"<code>{app.config.cmd_prefix}unblock id 用户ID</code>", f"<code>{app.config.cmd_prefix}unblock name 关键词</code>"])]), prefer_edit=False)
        kind, val = parts[0].lower(), parts[1].strip()
        if kind == "id":
            lst = list(ctx.config.get("sender_id_blacklist", []))
            try:
                v = int(val)
                if v in lst:
                    lst.remove(v)
                    ctx.config.set("sender_id_blacklist", lst)
                    await ctx.reply(event, ui.panel("TG-Radar · 已取消屏蔽", [ui.section("", [ui.bullet("ID", v)])]), prefer_edit=False)
                else:
                    await ctx.reply(event, ui.panel("TG-Radar · 不在列表中", []), prefer_edit=False)
            except ValueError:
                await ctx.reply(event, ui.panel("TG-Radar · 错误", [ui.section("", ["ID 必须是数字"])]), prefer_edit=False)
        elif kind == "name":
            lst = list(ctx.config.get("sender_name_keywords", []))
            if val in lst:
                lst.remove(val)
                ctx.config.set("sender_name_keywords", lst)
                await ctx.reply(event, ui.panel("TG-Radar · 已取消屏蔽", [ui.section("", [ui.bullet("关键词", val)])]), prefer_edit=False)
            else:
                await ctx.reply(event, ui.panel("TG-Radar · 不在列表中", []), prefer_edit=False)

    @ctx.command("blocklist", summary="查看屏蔽列表", usage="blocklist", category="监控")
    async def cmd_blocklist(app, event, args):
        ids = ctx.config.get("sender_id_blacklist", [])
        names = ctx.config.get("sender_name_keywords", [])
        secs = []
        if ids:
            secs.append(ui.section("屏蔽 ID", [f"<code>{i}</code>" for i in ids]))
        if names:
            secs.append(ui.section("屏蔽昵称关键词", [f"<code>{n}</code>" for n in names]))
        if not secs:
            secs.append(ui.section("状态", ["<i>暂无屏蔽</i>"]))
        await ctx.reply(event, ui.panel("TG-Radar · 屏蔽列表", secs), prefer_edit=False)

    @ctx.healthcheck
    async def check(app):
        state = getattr(app, "state", None)
        if state is None:
            return "warn", "运行时状态未初始化"
        return "ok", f"监听 {len(state.target_map)} 个目标，{state.valid_rules_count} 条规则"
