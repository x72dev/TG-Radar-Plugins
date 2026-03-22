"""转发消息提取群 ID · 分组变动自动增量同步。"""

PLUGIN_META = {"name": "chatinfo", "version": "6.1.0", "description": "群 ID 识别 · 分组变动实时同步", "kind": "admin"}

from tgr.plugin_sdk import PluginContext


def setup(ctx: PluginContext):
    ui, log = ctx.ui, ctx.log

    @ctx.hook("chatinfo_forward", summary="检测转发消息提取来源群 ID", order=10)
    async def on_forward(app, msg):
        fwd = getattr(msg, "fwd_from", None)
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

        client = getattr(app, "client", None)
        if client is None:
            return

        if source_id is None:
            from_name = getattr(fwd, "from_name", None)
            if from_name:
                log.info("只有 from_name: %s", from_name)
                try:
                    await client.send_message(
                        "me",
                        ui.panel("TG-Radar · 群 ID 识别", [ui.section("来源信息", [
                            ui.bullet("名称", from_name, code=False),
                            ui.bullet("ID", "隐藏（来源启用了转发保护）", code=False),
                        ])]),
                        reply_to=msg.id, link_preview=False,
                    )
                except Exception as exc:
                    log.warning("发送识别结果失败: %s", exc)
            return

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

        cmd_prefix = getattr(getattr(app, "config", None), "cmd_prefix", "-")
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
        try:
            await client.send_message("me", ui.panel("TG-Radar · 群 ID 识别", secs), reply_to=msg.id, link_preview=False)
        except Exception as exc:
            log.warning("发送识别结果失败: %s", exc)
        log.info("识别完成: %s (%s) = %s", title, stype, source_id)

    _filter_handler_ref = None

    async def _setup_filter_watcher():
        client = ctx.client
        if client is None:
            return

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
        nonlocal _filter_handler_ref
        if _filter_handler_ref and ctx.client:
            try:
                ctx.client.remove_event_handler(_filter_handler_ref)
            except Exception:
                pass
            _filter_handler_ref = None

    import asyncio

    async def _delayed():
        await asyncio.sleep(2)
        await _setup_filter_watcher()

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
        return ("ok", "转发检测(轮询) + 分组监听已激活") if _filter_handler_ref else ("ok", "转发检测(轮询)已激活")
