PLUGIN_META = {
    "name": "system",
    "version": "5.0.0",
    "description": "TR 管理器系统任务与重启更新插件",
}

from tgr.telegram_utils import panel, section


async def cmd_restart(app, event, args):
    app.write_last_message(event.id, "restart")
    result = app.command_bus.submit(
        "restart_services",
        payload={"reply_to": int(event.id), "delay": app.config.restart_delay_seconds, "trace": app._event_trace(event)},
        priority=20,
        dedupe_key="restart_services",
        origin="telegram",
        visible=True,
        delay_seconds=app.config.restart_delay_seconds,
    )
    app.db.log_event("INFO", "JOB_QUEUE", f"{app._event_trace(event)} restart_services queued")
    title = "TR 管理器 · 重启任务已接收" if result.created else "TR 管理器 · 重启任务已在后台执行"
    await app.safe_reply(event, panel(title, [section("执行说明", ["· 影响范围：Admin / Core 双服务。", "· 数据库中未完成的自动归纳任务会继续保留。", "· 调度层会在空闲时下发重启指令。"])]), auto_delete=0)


async def cmd_update(app, event, args):
    await app.run_update_command(event)


def setup(ctx):
    ctx.register_command("restart", cmd_restart, summary="重启 Admin / Core 双服务", usage="restart", category="系统任务", heavy=True)
    ctx.register_command("update", cmd_update, summary="执行核心与插件更新检查", usage="update", category="系统任务", heavy=True)
