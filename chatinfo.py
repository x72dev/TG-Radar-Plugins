"""转发消息提取群 ID · 分组变动自动增量同步。"""

PLUGIN_META = {"name": "chatinfo", "version": "6.0.1", "description": "群 ID 识别 · 分组变动实时同步", "kind": "admin"}

from tgr.plugin_sdk import PluginContext


def setup(ctx: PluginContext):
    ui, log = ctx.ui, ctx.log

    # ── 转发消息自动提取群 ID ──
    # 直接注册到 Telethon client，不通过 hook 机制
    _forward_handler_ref = None
    _filter_handler_ref = None

    async def _setup_handlers():
        client = ctx.client
        if client is None:
            log.warning("client 未就绪，跳过 handler 注册")
            return

        from telethon import events as tl_events

        self_id = getattr(ctx.app, "self_id", None)
        if not self_id:
            try:
                me = await client.get_me()
                self_id = int(me.id)
            except Exception as exc:
                log.error("无法获取 self_id: %s", exc)
                return

        log.info("注册转发检测 handler, self_id=%s", self_id)

        @client.on(tl_events.NewMessage(chats=self_id, incoming=True, outgoing=True))
        async def _on_saved_message(event):
            """捕获收藏夹中的所有消息，检测转发来源。"""
            try:
                # 跳过命令消息
                text = (event.raw_text or "").strip()
                prefix = getattr(ctx.app, "config", None)
                cmd_prefix = getattr(prefix, "cmd_prefix", "-") if prefix else "-"
                if text.startswith(cmd_prefix):
                    return

                # 检查是否是转发消息
                msg = event.message
                fwd = getattr(msg, "fwd_from", None) if msg else None
                if fwd is None:
                    return

                log.info("检测到转发消息, fwd_from=%s", type(fwd).__name__)

                source_id = None
                from_id = getattr(fwd, "from_id", None)
                if from_id:
                    try:
                        from telethon import utils as tu
                        source_id = int(tu.get_peer_id(from_id, add_mark=True))
                        log.info("从 from_id 提取: %s", source_id)
                    except Exception as exc:
                        log.warning("from_id 解析失败: %s", exc)

                # 有些频道转发只有 from_name 没有 from_id
                if source_id is None:
                    from_name = getattr(fwd, "from_name", None)
                    if from_name:
                        log.info("只有 from_name: %s", from_name)
                        await client.send_message(
                            "me",
                            ui.panel("TG-Radar · 群 ID 识别", [ui.section("来源信息", [
                                ui.bullet("名称", from_name, code=False),
                                ui.bullet("ID", "隐藏（来源启用了转发保护）", code=False),
                            ])]),
                            reply_to=event.id, link_preview=False,
                        )
                    else:
                        log.info("转发消息无 from_id 也无 from_name")
                    return

                # 获取来源详情
                title = "未知"
                stype = "未知"
                try:
                    entity = await client.get_entity(source_id)
                    title = getattr(entity, "title", None) or getattr(entity, "first_name", None) or "未知"
                    if getattr(entity, "megagroup", False) or getattr(entity, "gigagroup", False):
                        stype = "超级群"
                    elif getattr(entity, "broadcast", False):
                        stype = "频道"
                    elif hasattr(entity, "participants_count"):
                        stype = "群组"
                    elif getattr(entity, "bot", False):
                        stype = "Bot"
                    else:
                        stype = "用户"
                except Exception as exc:
                    log.warning("获取实体失败 %s: %s", source_id, exc)
                    title = "无法获取"

                rows = [
                    ui.bullet("名称", title, code=False),
                    ui.bullet("ID", source_id),
                    ui.bullet("类型", stype, code=False),
                ]
                tips = []
                if stype in ("频道", "超级群", "群组"):
                    p = ui.escape(cmd_prefix)
                    tips.append(f"设为告警频道: <code>{p}setalert {source_id}</code>")
                    tips.append(f"设为通知频道: <code>{p}setnotify {source_id}</code>")
                secs = [ui.section("来源信息", rows)]
                if tips:
                    secs.append(ui.section("快捷操作", tips))
                await client.send_message("me", ui.panel("TG-Radar · 群 ID 识别", secs), reply_to=event.id, link_preview=False)
                log.info("识别完成: %s (%s) = %s", title, stype, source_id)

            except Exception as exc:
                log.exception("转发检测异常: %s", exc)

        nonlocal _forward_handler_ref
        _forward_handler_ref = _on_saved_message
        log.info("转发检测 handler 已注册")

        # ── 分组变动实时同步 ──
        async def _on_filter_update(event):
            update = getattr(event, "update", event)
            utype = type(update).__name__
            if utype not in ("UpdateDialogFilter", "UpdateDialogFilterOrder", "UpdateDialogFilters"):
                return
            log.info("检测到分组变动: %s", utype)
            try:
                if hasattr(ctx.app, "command_bus"):
                    ctx.app.command_bus.submit(
                        "sync_manual",
                        payload={"reply_to": 0, "trace": "filter_change"},
                        priority=30, dedupe_key="sync_filter_change",
                        origin="system", visible=False, delay_seconds=3,
                    )
                    log.info("已触发增量同步 (3s debounce)")
            except Exception as exc:
                log.warning("增量同步触发失败: %s", exc)

        nonlocal _filter_handler_ref
        client.add_event_handler(_on_filter_update)
        _filter_handler_ref = _on_filter_update
        log.info("分组变动监听已激活")

    @ctx.cleanup
    async def _cleanup():
        nonlocal _forward_handler_ref, _filter_handler_ref
        client = ctx.client
        if client:
            if _forward_handler_ref:
                try:
                    client.remove_event_handler(_forward_handler_ref)
                except Exception:
                    pass
                _forward_handler_ref = None
            if _filter_handler_ref:
                try:
                    client.remove_event_handler(_filter_handler_ref)
                except Exception:
                    pass
                _filter_handler_ref = None
        log.info("handler 已注销")

    # 延迟注册（等 client 完全连接）
    import asyncio
    async def _delayed():
        await asyncio.sleep(2)
        await _setup_handlers()
    try:
        asyncio.get_running_loop().create_task(_delayed())
    except RuntimeError:
        pass

    @ctx.command("chatid", summary="转发消息到收藏夹获取群 ID", usage="chatid", category="工具", hidden=True)
    async def _(app, event, args):
        await ctx.reply(event, ui.panel("TG-Radar · 获取群 ID", [ui.section("用法", [
            "从任意群/频道转发一条消息到收藏夹，系统自动识别并回复 ID。",
        ])]), prefer_edit=False)

    @ctx.healthcheck
    async def check(app):
        if _forward_handler_ref and _filter_handler_ref:
            return "ok", "转发检测 + 分组监听已激活"
        if _forward_handler_ref:
            return "ok", "转发检测已激活"
        if _filter_handler_ref:
            return "warn", "仅分组监听，转发检测未注册"
        return "warn", "handler 未注册"
