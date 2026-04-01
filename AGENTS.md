# AGENTS.md（TG-Radar-Plugins 项目级执行规范）

## 1. 文档目的
本文件用于规范在 `TG-Radar-Plugins` 仓库内工作的 AI/自动化代理行为，确保插件开发满足：
- 与 TG-Radar 核心基座兼容；
- 不阻塞核心事件循环；
- 可热重载、可回滚、可观测。

## 2. 仓库定位
- 本仓库是 TG-Radar 的插件生态仓库，不是核心运行时仓库。
- 业务能力（命令、监控、路由策略等）应尽量在插件侧实现，避免侵入核心。
- 插件按职责分层：
  - `plugins/admin/`：后台命令与运维控制。
  - `plugins/core/`：高频消息监听与规则命中逻辑。

## 3. 目录职责
- `plugins/admin/`：Admin 插件。
- `plugins/core/`：Core 插件。
- `plugin_template.py`：新插件模板（首选起点）。
- `docs/`：文档资源。
- `requirements.txt`：插件额外依赖。

## 4. 插件接口硬约束
- 每个插件文件必须提供 `PLUGIN_META`。
- 必须提供 `setup(ctx: PluginContext)` 作为入口。
- 可选提供 `teardown(ctx)` 做卸载清理。
- 元数据建议字段：
  - `name`
  - `version`
  - `description`
  - `kind`（`admin` / `core`）
  - `config_schema`
  - `min_core_version`

## 5. PluginContext 使用规范
- 仅通过白名单接口访问系统能力：
  - `ctx.db`：数据库能力（受控）。
  - `ctx.ui`：统一面板渲染能力。
  - `ctx.bus`：后台任务总线。
  - `ctx.config`：插件配置读写。
  - `ctx.log`：插件日志。
- 禁止访问核心内部私有实现或未公开对象。

## 6. 事件与命令开发规范
- 命令注册使用 `@ctx.command(...)`，必须填写：
  - `summary`
  - `usage`
  - `category`
- 高耗时任务必须标记 `heavy=True` 并交由 `ctx.bus.submit_job(...)` 异步执行。
- Core 监听使用 `@ctx.hook(...)`，按 `order` 控制顺序。
- 健康检查使用 `@ctx.healthcheck`，返回 `(status, detail)`。
- 资源清理使用 `@ctx.cleanup`，确保重载后不残留 handler/task。

## 7. 异步与性能规范（高优先级）
- 禁止在插件路径中使用阻塞调用：
  - 禁用 `time.sleep()`；
  - 禁用同步网络请求（如直接 `requests.get()`）。
- 必须使用异步方式：
  - `await asyncio.sleep(...)`
  - 异步 I/O 客户端。
- Core 插件需优先做前置过滤，避免无效正则或重复网络请求。

## 8. Telethon 使用边界
- 插件层通常不应自行创建 `TelegramClient`。
- 当前仓库应视为“依赖 app.client 的逻辑层”，而非连接管理层。
- 如确需新建客户端，必须先在核心仓库评审并提供统一工厂方案，不得在插件中私建连接。

## 9. 配置与数据规范
- 插件配置通过 `ctx.config` 读写，自动落盘到 `configs/<plugin>.json`。
- 新增配置项必须在 `PLUGIN_META.config_schema` 中给出默认值与说明。
- 不要在日志或面板输出敏感信息（token、密钥、会话细节）。

## 10. 兼容性与版本策略
- 改动插件接口时，必须评估 `min_core_version` 影响。
- 破坏性改动需提升插件版本并写清迁移提示。
- 新增依赖需评估对核心运行环境与 Docker 部署的影响。

## 11. 验收清单（最少）
- 语法检查：对插件文件执行 Python 编译检查。
- 加载检查：插件可被核心识别并加载，无 ImportError。
- 行为检查：
  - 命令插件：命令可注册、可执行、输出可读。
  - 监听插件：不误触发、不重复发送、不阻塞。
- 重载检查：`-reload` 后无重复 handler、无资源泄漏。

## 12. 禁止事项
- 禁止在插件内绕过 `ctx.*` 直接操作核心私有状态。
- 禁止将耗时任务直接塞在命令/消息主 handler 内同步执行。
- 禁止提交包含真实敏感信息的配置、日志或示例数据。
- 禁止“重构 + 行为改变 + 风险改动”混在一个提交中。

## 13. 提交说明模板（建议）
- 改动目标：一句话说明业务意图。
- 影响插件：列出文件路径。
- 风险说明：是否影响命令、监听、任务队列、兼容性。
- 验证步骤：执行过哪些检查，结果如何。
- 回滚方案：出现异常时如何禁用/回滚该插件。

