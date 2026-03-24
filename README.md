<div align="center">

<img src="docs/banner.svg" alt="TG-Radar Plugins Dynamic Banner" width="100%" style="max-width: 800px; margin-bottom: 24px;" />

# TG-Radar Plugins

**官方扩展与生态插件注册中心** <br />
专为 TG-Radar 架构解耦设计，支持毫秒级无感热重载。

<br />

[**🏠 核心基座**](https://github.com/x72dev/TG-Radar) · [**🚀 快速接入**](#-快速接入) · [**📚 SDK 架构**](#-sdk-架构)

</div>

---

## ⚡ 核心定位

此仓库为 `TG-Radar` 的专属插件池。所有的上层业务逻辑（包括管理面板、自动路由、规则解析等）均被剥离至此。

通过严苛的接口约束与沙盒化的 `PluginContext` SDK，插件在主核心的高频异步事件循环中运行，却能享受完全隔离的生命周期管理，支持 `Hot-Reload` 与异常熔断。

## 📦 插件生态池

分为负责后台调度的 **Admin 组件** 与负责监听拦截的 **Core 组件**。

| 组件名 | 类型 | 职责说明 |
| :--- | :--- | :--- |
| `general` | Admin | 基础系统监控、状态面板与日志分发 |
| `folders` | Admin | 集群监控对象的动态生命周期管理（启停/移除） |
| `rules` | Admin | 基于预编译正则表达式的高性能规则栈维护 |
| `routes` | Admin | 数据智能归纳与自动化流量路由调度 |
| `keyword_monitor` | Core | **核心引擎**：海量并发下的关键词高精度匹配与告警抛出 |

## 🚀 快速接入

在 `TG-Radar` 的强解耦架构下，一行代码即可集成 SDK，创建一个支持热重载的全新组件：

```python
# plugins/admin/hello.py
PLUGIN_META = {"name": "hello", "version": "1.0.0", "kind": "admin"}
from tgr.plugin_sdk import PluginContext

def setup(ctx: PluginContext):
    @ctx.command("hello", summary="打招呼", usage="hello", category="示例")
    async def handler(app, event, args):
        await ctx.reply(event, ctx.ui.panel("Hello", [ctx.ui.section("", ["👋"])]))
```

部署完成后，仅需在终端发送 `-reload hello` 即可将代码加载进内存上下文。

<details>
<summary><b>查看生命周期与 SDK 调试最佳实践</b></summary>

<br/>

**避免阻塞事件循环**
由于基于 `asyncio`，**严禁在 handler 中执行长时间的同步阻塞操作**（如大文件下载或 `requests.get`）。
请使用 `aiohttp` 或将繁重任务转移至系统后台总线：`ctx.bus.submit_job("kind", func, *args)`。

**插件状态隔离持久化**
避免在模块顶部定义全局变量缓存数据。重载机制会重置内存。
请强制使用 `ctx.config` 或 `ctx.db` 接口来管理所有持久化状态。

</details>

## 📚 SDK 架构

SDK 暴露了沙盒内的高权限接口，封装了底层的通信细节。

| 模块抽象 | 调用边界 |
| :--- | :--- |
| `ctx.config` | `.get()` / `.set()` — 读取或操作插件专用的持久化配置文件 |
| `ctx.db` | `.log_event()` — 穿透至 SQLite 层面的统一日志规整 |
| `ctx.ui` | `.panel()` / `.bullet()` — 在 Telegram 输出标准化的高规格 HTML 面板 |
| `ctx.bus` | `.submit_job()` — 将重度任务甩出主事件循环进入后台调度池 |
| `@ctx.hook` | 将自身挂载至 Core 层面的特定高频事件节点 |
