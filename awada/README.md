# Awada Relay V2 plugin

基于 OpenClaw 2026.10.4，连接 Relay `/api/v2/awada`, 实现微信对话机器人（微信用户可以直接添加好友，基于企业微信）

## 配置

插件通过 `plugins.load.paths` 加载本目录；`plugins.entries.awada.enabled` 和 `channels.awada.enabled` 均需启用。安装依赖由现有安装器和 `apply-addons.sh` 完成。

```json
{
  "channels": {
    "awada": {
      "enabled": true,
      "relayBaseUrl": "https://relay.openclaw-for-business.com/api/v2/awada",
      "awadaKey": "<由 Relay 签发的 lane key>",
      "dmPolicy": "open",
      "allowFrom": ["*"],
      "groupPolicy": "allowlist",
      "groupAllowFrom": ["<允许的群 ID>"],
      "requireMention": true
    }
  }
}
```

- 默认 Base URL 为 `https://relay.openclaw-for-business.com/api/v2/awada`；兼容填写 origin 或完整 `/api/v2/awada`；旧 `/api/v1/awada` 后缀会规范化为 v2，不回退到 v1。
- HTTP 与 WS 使用 `X-OFB-Key`。省略 lane 时由服务端选择唯一的 `user` lane。
- DM 默认 `pairing`，支持 `open`、`pairing`、`allowlist`、`disabled`。与新版飞书一样，`open` 必须同时设置 `allowFrom: ["*"]`；仅写 `dmPolicy: "open"` 不会开放所有发送者。
- 群聊使用 `groupPolicy`、`groupAllowFrom` 和 `requireMention`，继承 `channels.defaults.groupPolicy`。与飞书一致，未显式配置 `requireMention` 时，open 群无需 @，allowlist 群要求 @；`groupSenderAllowFrom` 可进一步限制群内发送者。
- 多账号放在 `channels.awada.accounts.<accountId>`，共用字段可在顶层配置；`defaultAccount` 选择默认账号。每个账号配置自己的 key；lane 可省略，仅选择其他 lane 或消除歧义时再指定，并使用 OpenClaw 标准 bindings 绑定 crew。
- 目标 ID 直接使用入站事件提供的值，不从昵称猜测稳定身份；会话按本地账号、服务端账号标识和会话目标隔离。

所有账号共享同一套 Awada 动作和参数格式。客户端不展示或询问底层实现，不按账号裁剪能力，也不预判某个动作在当前账号下是否支持；服务端负责适配、权限检查和执行结果。

## 消息与媒体

入站使用 OpenClaw 的 ingress 权限、持久队列、上下文构建、音频预转写、inbound turn 和回复管线。agent 获得标准 Sender、MessageSid、MediaPaths、MediaTypes 等字段。连续纯文本按账号、lane、聊天和发送者合并；控制命令、本地 slash、媒体消息不并入普通文本。

插件内部统一处理结构化 @，在合并及命令识别前移除机器人称呼。仅因缺少 @ 而未触发回复的群消息进入同一套历史上下文窗口，下次触发时补充给 agent，不混入命令正文。`historyLimit` 默认沿用系统群聊设置（缺省 50、上限 200）。每个聊天保持顺序，单任务超过五分钟后按飞书规则释放后续消息；已运行的任务继续执行。

普通回复输出 assistant 文本；主动消息和附件使用与飞书相同的工具格式：

```text
message(action="send", message="演示材料", media="/absolute/path/demo.mp4")
message(action="send", media="https://example.com/demo.mp4")
```

当前会话省略 target。主动指定目标时使用 `target="user:<用户 ID>"` 或 `target="chat:<群 ID>"`，并按需要指定 channel/account。内部自动回复仍接受历史编码目标。

- 不使用 `[SEND_FILE]`、`sendAttachment` 或仅凭云端文件名发送的约定。
- 同一 payload 的正文和附件一起保留。图片、视频、文件使用标准 media；语音气泡使用标准 `audioAsVoice`。
- 本地文件通过 OpenClaw 的媒体权限和大小限制读取，统一提交附件内容；语音内部转换编码并携带真实时长。收到语音后自动完成原生转写申请与结果查询，文本进入标准消息上下文；缺少原始语音 ID、转写失败或超时则尝试 OpenClaw 公共音频转写，不使用独立 ASR 脚本。自动转写仅在入站权限放行后执行，不自动把转写结果另发一条消息。
- 需要通过链接交付本地附件时，配置 `mediaPublicBaseUrl`，只将该公网 origin 的 `/plugins/awada/media/` 转发到现有 Gateway；不新增监听端口。附件使用带随机 token、最长一小时有效的 URL，仍检查账号启用状态。公网 URL 可直接发送。所有账号采用同样的发送格式，服务端决定内容的执行支持。
- 加密媒体在插件内部解析为标准附件；服务端未提供下载材料的内容保留结构化事件及标准不可用提示，不伪造文件。
- 本地单文件上限默认 20 MiB，可用 `mediaMaxMb` 调低；更大的内容使用 URL 或目录中的异步上传操作。

## 客户端业务能力

启用插件后注册 `awada_api`，提供联系人、群管理、消息类型、标签、朋友圈、媒体上传下载、待办等产品范围内的能力合集；账号返回的部分目录不会删掉其他业务能力。登录/设备管理、客户端指令队列与存储维护、历史诊断、回调扩展、通信加密、原消息转发已从客户端接口移除：目录不展示、schema 不提供、手动提交也拒绝，动态目录不会将它们重新加入。

原生语音转写的申请/查询保留在内部流程，面向 agent 只提供 `voice.transcribe` 一个命令，返回完成的文本。其 `params` 为 `{"messageId":"<原始语音消息 ID>","timeoutMs":30000}`，超时范围 1–60 秒；普通收件自动执行，无需 agent 调用。

当前业务目录已隐藏实现名称，但其他同义业务动作尚未全部合并；原始接口数不等于业务命令数。开发要求仍是同一业务能力只有一个公开命令和统一参数，内部适配不应成为 agent 的分支选择。

```text
awada_api(action="capabilities")
awada_api(action="schema", operation="room.getRoomList")
awada_api(action="operation", operation="room.getRoomList", params={"nextStartIndex":0,"limit":20}, requestId="rooms-001")
awada_api(action="result", operationId="<返回的 eventId>", waitMs=10000)
awada_api(action="operation", operation="voice.transcribe", params={"messageId":"<原始语音消息 ID>"})
awada_api(action="events", eventType="SERVICE_EVENT", limit=20)
```

`params` 可为对象或数组，原生 query 放 `query`，multipart 文件使用 `file: {filename, base64, contentType}`。需要脚本对接时，可直接导入 `index.ts` 导出的 capabilities、submit、get/wait result、HTTP inbound helpers；转写使用 `transcribeAwadaVoice`。

账号操作与账号级结果只对 owner 或经 OpenClaw 工具策略授权的本地自动任务开放；普通外部发送者仅能读取本人的聊天事件。标准 `message` 发送继续走系统的会话和媒体权限。客户端只配置 Awada 访问凭据，不向 agent 下发服务管理凭据。

目录保留服务级授权范围、定制和废弃标记；目录存在不等于执行成功。客户端不根据账号类型或服务端目录的 `enabled` 值拦截动作，支持情况与权限由 server 检查后返回。ID 超出 JavaScript 安全整数范围时必须传字符串，响应保留原始数字 token。

## 执行结果、幂等与事件

`/outbound` 的 200 和 `/operations` 的 202 均只代表入队。返回的 `eventId` 是结果查询 ID，不能把 Redis `streamId` 当作已发送凭证。区分 `queued`、`running`、`submitted`、`succeeded`、`failed`、`unknown`；只有执行结果 `succeeded` 表示操作成功，也不表示对方已读。

写请求携带 `request_id`。Gateway 内持久化请求指纹和回执，重复的已接受请求复用同一 eventId，不重新提交；同 ID 的不同内容拒绝。无法确认结果的写操作不自动重发，超出服务端七天幂等窗口的未知请求需对账。普通消息的多段内容按原顺序交由服务端发送，保留部分失败信息。

WS 在 OpenClaw 持久入站队列可靠接收后 ACK；入库失败不 ACK。`MESSAGE_NEW` 才进入聊天和 slash；服务事件与 `OPERATION_RESULT` 保存到本地事件存储后完成消费，不唤起 LLM。工具中统一用 `SERVICE_EVENT` 查询服务事件，不暴露内部传输字段。事件存储最多 2000 条、最长七天，可通过 `awada_api events` 查询。服务端 stream 仅保留约 1000 条，长时间离线不能保证远端历史完整。

## 本地 slash

默认读取 `<OpenClaw stateDir>/awada/commands.json`；或配置 `plugins.entries.awada.config.commandsFile`。相对路径以 stateDir 为基准。格式见 [examples/commands.json](./examples/commands.json)。

每个命令配置 `name`、`description`，以及 `reply` 或 `exec` 二选一。通过 OpenClaw 原生命令注册机制执行，channel 限定为 awada；原有 `/new`、`/reset` 等系统命令保留。自定义命令不能占用已有命令名，默认需要命令授权；确需公开的业务命令可显式设置 `requireAuth: false`。

- `reply` 返回标准 `{text, mediaUrl, mediaUrls}`；空对象表示无可见回复。
- `exec.command` 和 `exec.args` 是本地可信配置，无 shell 拼接。工作目录是 JSON 文件所在目录；用户参数仅通过 stdin JSON 传递。
- stdin 包括 command、args、senderId、channel、accountId、agentId、sessionKey、sessionId、from、to、isAuthorizedSender，不包含 OpenClaw 配置或 key。
- 脚本 stdout 必须是同一标准回复 JSON；stderr 不转发给客户。超时默认 15 秒、最多 30 秒，输出最多 1 MiB。
- 修改已有 handler 内容下次执行生效；新增/删除命令名或修改注册元数据后，按正常流程重载插件。JSON 文件不改服务端配置。

## CustomerDB hook 与静默业务命令

CustomerDB 是可选功能。启用 Awada channel 或给 crew 配上 customer-db 技能，不会单独开启这个 hook；需在 `plugins.entries.awada` 合入下面配置（账号、agent 和绝对路径按实例调整，保留已有其他字段）：

```json
{
  "enabled": true,
  "hooks": {
    "allowConversationAccess": true
  },
  "config": {
    "customerdb": {
      "enabled": true,
      "agentId": "sales-cs",
      "accountId": "default",
      "workspaceDir": "/home/user/.openclaw/workspace-sales-cs"
    }
  }
}
```

- `customerdb.agentId` 必须明确填写，`enabled` 缺省为允许；没有 agentId 或显式 enabled=false 不注册 CustomerDB hook 和两个业务命令。
- OpenClaw 2026.10.4 对外部插件要求显式 `hooks.allowConversationAccess=true`；未授权会阻止 `before_prompt_build` 注册。`hooks.allowPromptInjection` 缺省允许，若显式为 false 也会阻止该 hook。这些 hooks 字段与 config 同级，不放入 config.customerdb。
- `accountId` 是 channels.awada 的本地账号名，不是 lane。省略时使用插件加载时解析的默认 Awada 账号；多账号须明确填写，并将该账号绑定到指定 agent。`workspaceDir` 指向该 crew 的真实工作区；省略时回退到 `$HOME/.openclaw/workspace-sales-cs`。
- 先部署 crew，保证其 `db/` 目录存在且可写、Gateway 环境可执行 sqlite3。插件会按现有 schema 或内置 DDL 建表、补缺表，并保留已有数据；不会自动建立工作区/db 目录。
- 配置后完整重启 Gateway 即加载注册，不需要再执行独立的 hook 安装命令。使用 awada-channel-setup 启用 sales-cs 时默认写入 CustomerDB 配置和必要的会话访问授权；已有显式权限拒绝会报错，不自动覆盖。`--without-customerdb` 保留原配置，不为本账号设置 CustomerDB。

启用后保留以下行为：

| 入口 | 自动处理 |
|---|---|
| 匹配 agent/account 的客户私聊，在构建模型提示前 | 按 Sender 生成 peer，首次接触建档，更新 updated_at，注入 `[CustomerDB]` 的商业状态与画像 |
| 已发送一次跟进的客户再次发起对话 | 将该客户 sent_once 跟进标为 completed，并注入 `[FollowUp]` 提醒；未发送的 pending 保留 |
| `/payment_success` | 静默将当前客户 business_status 改为 subs，并记录日期 |
| `/club_join` | 静默将当前客户 business_status 改为 club，并记录入群日期 |

严格说是一个 `before_prompt_build` hook 加两个原生 slash 命令。命令随 CustomerDB 注册，不需要放入 commands.json，也不要用自定义命令占用这两个名字。两条命令仅修改业务状态，不代表插件独立校验了支付订单或真实入群事实。它们保留原有 requireAuth=false 设置，仍受渠道入站策略和账号/agent 归属限制。

客户上下文 hook 跳过其他账号/agent、其他渠道、群聊，以及 cron/heartbeat 触发；失败写 Gateway 日志。它不负责创建定时调度、发送跟进、新建跟进前取消旧 pending、48 小时清理或发送次数封顶，这些仍属于 customer-db/proactive-send 的业务流程。启用验收应分别核对 hook 注册、私聊注入和业务命令，不能仅凭 channel 已连接就判定 CustomerDB 生效。


## 迁移与验证

升级时核对 OpenClaw 精确 pin、V2 健康与 lane 权限；检查原 `open` 配置是否缺少 `["*"]`，并将旧附件指令改为标准 `message send/media`。仅按文件名保存的旧素材必须补成本地绝对路径或有效 URL；不会猜测云端文件句柄。

客服 demo 技能从自己的 `config.json.media` 读取实际素材。主动跟进改用标准 `message`，旧 `proactive-send` wrapper 仅转交标准 CLI；跟进流程保存执行回执，确认成功后才更新客户记录。

客户端协议说明见 [AWADA-CLIENT-TRANSPORT.md](../docs/AWADA-CLIENT-TRANSPORT.md)。能力与参数以 `awada_api capabilities/schema` 为准。

回归和夹具仅在仓根、Git 忽略的 `test/awada/`。覆盖业务能力范围、被移除动作的调用阻断、自动/手动语音转写与回退、统一动作/工具输出、真实本机 WS、OpenClaw 2026.10.4 原生入站队列/权限/上下文、标准媒体与本地 slash。该验证不替代实号收发验收。
