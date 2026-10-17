# Awada 客户端传输与 V2 接入

更新：2026-10-17。客户端实现位于 `awada/`，基准 OpenClaw 2026.10.4；服务端契约来自 Relay 2026-10-16 的 V2 API、能力映射和 OpenAPI。完整配置、命令和媒体示例见 [plugin README](../awada/README.md)。

## 地址与鉴权

默认 `https://relay.openclaw-for-business.com/api/v2/awada`，HTTP/WS 使用 `X-OFB-Key`，key 需带对应 `awada:lane:<完整 laneId>` scope。lane 是服务端账号标识；缺省 lane 由服务端唯一解析 `user`，不选择第一个匹配账号。agent 不需要知道服务端底层实现，所有账号使用同样的 Awada 动作。

`relayBaseUrl` 接受 origin 或完整 API 根路径；旧 v1 后缀规范化到 v2。v1 的下线日期由服务端健康接口提供；客户端不回退到 v1，不直接连接 Redis，仅持有 Awada 访问凭据。

## 客户端 API 覆盖

| API | plugin 接入 |
|---|---|
| GET `/health` | `probeAwada`；`awada_api health` |
| GET `/inbound` | 导出的 `readAwadaInbound`，支持 count、block_ms、last_id |
| WS `/inbound` | channel 持久入站、重连、ping/pong、显式 ACK |
| POST `/outbound` | 标准文字、图片、文件、视频和语音；普通回复与 `message send` |
| GET `/capabilities` | 合入完整契约快照，`awada_api capabilities` 返回统一能力合集，不按账号裁剪 |
| GET `/capabilities/:operation` | `awada_api schema`，获取统一动作的参数、query、响应 schema；账号未公开该动作时使用完整契约快照 |
| POST `/operations` | `awada_api operation`，完整透传 params/query/file |
| GET `/operations/:id` | `awada_api result` 与回复执行结果确认 |

客户端能力范围涵盖联系人、群、标签、朋友圈、消息、媒体和待办等业务能力。移除登录设备，以及客户端指令管理、存储维护、历史诊断、回调扩展、通信加密和原消息转发。统一范围策略同时用于快照生成、动态目录、schema 查询和提交校验，禁止通过原始动作 ID 绕过；该限制是产品范围，与某账号是否支持无关。其余动作仍由 server 决定执行支持、授权与限制。

语音转写的申请与查询仅内部可用，公开业务动作 `voice.transcribe` 接收 `params.messageId` 和可选 `timeoutMs`（默认 30 秒，1–60 秒），完成整个任务后返回文本。普通收件权限放行后自动执行，优先使用回调内原始 msgServerId（不能将可能不同的 source_message_id 当成它）；不可用或超时则走宿主公共转写。转写与媒体上下文仍通过原生入站管线进入 agent，不自动向客户单独发送转写文本。

当前动作 ID 已隐藏实现名称，但其余同义业务动作尚未全部合并；原始接口数不是去重后的命令数。同一能力一个公开命令、统一参数的要求继续有效。新动作可由服务端目录合入，已移出产品范围的动作不会重新暴露。

契约快照由开发者运行 `node scripts/sync-awada-catalog.mjs <服务端完整目录 JSON>` 更新，包含来源文件摘要与契约日期。输入必须是完整契约，不能用某个账号的 capabilities 代替；生成时剔除已移除动作，原生转写步骤仅供内部使用。快照不宣称 server 已支持或已执行成功。

## 入站与 ACK

WS 帧沿用 `{id,event}`，event 的 `schema_version` 仍为 1。API 的 V2 与 envelope 的 schema 版本含义不同。

1. 验证 envelope 和消息路由标识。
2. 按 account/lane/event_id 写 OpenClaw 原生持久入站队列。
3. 写入成功才发送 `{type:"ack",id}`；存储失败保留服务端 PEL 并重连。
4. 只有 `MESSAGE_NEW` 进入聊天；其他事件持久保存后完成消费。
5. 原生 ingress 生命周期负责去重、adoption、重试和重启恢复。

传输层按连接顺序串行入库，聊天不阻塞 ACK。普通聊天的 debounce、会话顺序、上下文、权限和回复都接 OpenClaw 的同一套宿主接口。文本合并键包含本地账号、服务端账号标识、聊天及发送者；媒体/控制命令不并入普通文本。两条不同 event_id 的相同文本都保留。

群聊默认策略、@ 激活和历史窗口与飞书一致：继承系统 groupPolicy，open 默认无需 @，allowlist 默认要求 @，显式 requireMention 优先。仅因缺少 @ 被跳过的已授权消息进入待补充上下文，不参与命令识别。聊天任务按飞书的五分钟超时规则释放顺序队列。

可变昵称身份由插件内部按事件身份类型处理。原始昵称/群备注保留在事件中；不从清洗后的 ID 猜回原名称。回复通过服务端映射，映射过期的 `ROUTE_EXPIRED` 不当作已发送。工具输出将服务事件、动作 ID 和技术元数据统一为 Awada 表达，保留业务内容、原始目标 ID 和操作回执。

## 出站与结果

标准内容使用 `payload` 数组和 `meta`；路由来自选定 lane，当前回复保留原 channel/user，附带 `source_event_id`。文字与附件不互相覆盖，不解析专用文本标签。

- 使用 `request_id`；Gateway 本地保留请求指纹和回执，相同请求复用同一 eventId。
- 200/202 是入队确认，返回 `streamId` 和 `eventId`；结果查询使用 `eventId`。
- `queued/running/submitted` 不代表最终成功；`succeeded` 不代表对方已读。
- `failed` 保留部分已执行步骤，`unknown` 先查询/对账，不盲目建立新写任务。
- 服务端幂等和结果窗口为七天；本地未知请求超出该窗口时拒绝自动重投。
- 大整数 ID 使用字符串；本地保留响应原始整数 token，拒绝已失真的数值输入。

本地文件通过宿主媒体权限读取，使用统一附件内容提交；配置 mediaPublicBaseUrl 时可通过 token 保护的媒体 URL 交付。选择由显式媒体配置决定，不探测账号底层类型，也不在本地拒绝某一账号的附件。不得把本地 `file_path` 或裸云端文件名传给服务端充当可读文件。

## CustomerDB hook

原 CustomerDB 的自动建档、画像注入、客户回复时结束 sent_once 跟进，以及 payment_success/club_join 静默命令保留。IT 配置 Awada 时默认同时配置并验证此 hook，仅用户明确不启用或已有明确停用设置时跳过；运行时仍需要显式配置，单独启用 channel 不会自动生成该段。必须设置 `plugins.entries.awada.config.customerdb.agentId`，且该段 enabled 不为 false；外部插件还须显式授权 `plugins.entries.awada.hooks.allowConversationAccess=true`，并且 allowPromptInjection 不为 false。完整配置、范围与验收见 [README 的 CustomerDB 节](../awada/README.md#customerdb-hook-与静默业务命令)。

awada-channel-setup 默认按所选 crew/account/workspace 设置 CustomerDB 并补齐会话访问授权，保留已有权限策略；显式拒绝时返回错误，不越过宿主策略。定时任务与心跳不执行客户回复 hook，主动扫描流程须另行配置。

## 运行边界

服务端 inbound/outbound 各保留约 1000 条，超过离线窗口可能丢失历史。客户端已接收的事件交由 OpenClaw 持久队列；服务事件和操作结果另保留最多 2000 条、最长七天。异步任务依赖对应回调，客户端不能把 API 接受任务视为最终执行成功。

本轮仅完成源码与隔离回归；部署、`apply-addons.sh`、现役 Gateway/浏览器切换及实号发送应按用户确认的升级顺序执行。
