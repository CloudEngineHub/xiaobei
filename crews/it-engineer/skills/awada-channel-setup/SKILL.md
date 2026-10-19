---
name: awada-channel-setup
description: 配置 Awada 账号、crew 路由及默认启用的 CustomerDB hook，检查消息权限、本地 slash、标准媒体与统一动作接口。用于用户或 main 明确选定 Awada 后的启用和修复。
---

# Awada Relay V2 配置

用户或 main 选定 Awada 后使用本技能；channel 选择仍由用户决定。启用 Awada channel 时，配置并验证 CustomerDB hook 是标准动作，不再单独询问是否启用；仅用户明确要求不启用或已有明确停用设置时跳过。Awada 是本项目局部插件，默认连接 `https://relay.openclaw-for-business.com/api/v2/awada`。所有账号使用相同动作和参数格式；不询问服务端底层实现，不按账号筛掉能力，也不在本地预判某个业务动作是否支持。执行支持和限制由 Awada server 返回。

## 配置前

- 本机工具和字段名备忘查 `AGENTS.md` 的 `## Tools` 节，程序路径查 `OFB_ENV.md`；不创建或更新独立 `TOOLS.md`。旧版本遗留的 `TOOLS.md` / `HEARTBEAT.md` 由用户升级后手动删除，不在渠道配置流程中迁移或清理。
- 从 `OFB_ENV.md` 确认项目路径；Docker 通常为 `/opt/openclaw`。插件要求 OpenClaw 2026.10.4，局部依赖为 `silk-wasm`、`typebox`、`ws`、`zod`。安装器已负责安装；缺依赖时按项目升级流程修复，不把依赖装进 `~/.openclaw/node_modules`。
- 获取 Awada 账号的 `awadaKey`，使用 `X-OFB-Key`，scope 须含 `awada:lane:<完整 laneId>`。客户端仅配置 Awada 访问凭据；`OFB_KEY` 不是 awadaKey。
- 确定 crew 和 OpenClaw accountId。lane 默认不填，由服务端解析唯一 `user` lane；只有服务端返回歧义或用户明确选择其他 lane 时才指定。一个 lane 绑定一个企业微信（企微）账号。
- key 优先复用已有配置或读取 `AWADA_KEY` 环境变量；交互终端可隐藏输入。不要把 key 写进命令参数或日志。配置路径依次使用显式 `--config`、`OPENCLAW_CONFIG_PATH`、`OPENCLAW_JSON`、stateDir/openclaw.json。
- 已有 key 不因环境中出现另一个 key 而被覆盖；轮换时显式使用 `--replace-key`，可通过 `--key-env <变量名>` 选择新 key 来源。多账号未指定 defaultAccount 时必须传 `--account-id`。

## 预览和应用

```bash
awada-channel-setup --project-root <项目根> --account-id <账号> --agent-id sales-cs --dry-run
awada-channel-setup --project-root <项目根> --account-id <账号> --agent-id sales-cs
```

先审阅脱敏预览，再在用户已授权的配置范围内应用。已有 lane 会保留；显式 `--lane ""` 恢复服务端默认，其他 lane 使用 `--lane <laneId>`。脚本统一处理以下动作，不要手拼 JSON 或覆盖整段数组：

- 合入所选账号和插件加载路径，保留其他账号、插件路径和配置。
- crew 不存在时读取 `crews/<agentId>/openclaw_setting_sample.json`，以 sample.id 为 `agents.entries` 的键注册，entry 内不写 id；保留 sample 的 tools/heartbeat/subagents，执行权限使用 tools.exec.mode。已存在的 crew 保留个性化设置。`--agent-sample`、`--workspace` 可指定实例位置。仍有旧 agents.list 的配置须先通过本版本 Doctor 或 apply 迁移。
- 写入精确 `bindings[].match: {channel:"awada",accountId:"<账号>"}`，不在 agent 顶层写 channel。账号已绑另一 crew 时拒绝抢占。
- 默认启用限定到本次所选 agent/account/workspace 的 CustomerDB hook，适用于所有通过本流程启用 Awada 的 crew；字段、权限和验收按下节执行。只有用户明确要求不启用时才传 `--without-customerdb`；已有同一归属的 `customerdb.enabled=false` 也作为明确停用保留。不得为绕过配置错误或归属冲突而擅自跳过 hook。
- 原子写回前保存权限为 0600 的备份；重复应用不重复添加 binding 或插件路径。`--dry-run` 不写配置、备份或工作区，不重启服务。

新客服账号默认 `dmPolicy: open`、`allowFrom: ["*"]`、`groupPolicy: disabled`，用于公开私聊接待。已有显式策略保持原值。调整权限时显式传 `--dm-policy`、重复 `--allow-from` 或 `--group-policy`；选 pairing 时按 OpenClaw 配对流程授权客户，不能声称已公开接待。open 必须含 `"*"`，allowlist 不能为空。群聊的允许名单和 @ 策略按实际需求配置；插件的 open 群默认无需 @，allowlist 群默认要求 @，显式 requireMention 优先。

## CustomerDB hook 标准配置与验收

脚本默认完成以下配置，不要求用户另选开关：

- `plugins.entries.awada.config.customerdb`：`enabled=true`、所选 `agentId`、本地 `accountId` 及该 crew 真实 workspace 的绝对路径；不能把 lane 填入 accountId，也不能仍指向其他 crew 的工作区。
- `plugins.entries.awada.hooks.allowConversationAccess=true`：2026.10.4 外部插件注册客户上下文 hook 的必要授权。`allowPromptInjection` 默认允许；已有显式 false 时报告权限冲突，保留该策略，不绕过宿主限制，也不擅自用 --without-customerdb 逃过检查。
- 当前插件只有一组 CustomerDB 归属。已有其他 agent/account 占用时报告冲突并保留原归属，不抢占、不共用客户库、不静默省略新账号的 hook。
- 先确认目标 crew 已部署、真实 workspace 存在且可写，并检查 Gateway 环境可执行 sqlite3。插件加载时在该 workspace 内创建缺少的 db 子目录和表；已有数据库与用户资料保留。缺少 workspace 或依赖时先按既有部署流程补齐，不能把已写配置报告为 hook 已生效。

脱敏预览必须检查 customerdb、customerdbHooks 和 customerdbSetup。正常结果应为 enabled，且会话访问授权为 true。用户明确不启用时才允许 skipped_by_request；已有明确停用设置返回 existing_disabled，交付时说明仍停用，不擅自重新启用。--without-customerdb 只跳过本次配置并保留现有段落，不能据此声称已停用原来运行的 hook；明确要求停用已有同一归属的 hook 时，设置该段 enabled=false，保留客户数据及其他账号配置。

在已授权的重载/重启后，核对 Gateway 没有 hook blocked / DB init failed 错误，并确认 before_prompt_build 已注册；获准验证私聊时确认 `[CustomerDB]` 注入和建档。客户回复仅结束 sent_once，pending 保留；cron/heartbeat 不执行客户回复处理。`/payment_success`、`/club_join` 随 hook 功能注册，不在 commands.json 重复配置。返回 channel 状态和 hook 配置/注册/业务验证结果；仅 channel 已连接不算完整验收。

## 媒体与本地命令

- 普通回复直接输出 assistant 文本；文字和附件统一用标准 `message(action="send", media="<本地绝对路径或 URL>")`。不配置专用发送标签或按裸云端文件名发附件。
- 收到语音后插件自动完成转写并将文本交给消息管线，不需要配置独立 ASR 脚本。原生转写失败或缺少原始语音 ID 时使用 OpenClaw 公共音频转写。确需手动处理时读取 `awada_api schema voice.transcribe`，传入原始消息 ID；不要求 agent 分别申请、轮询任务。
- 本地单文件默认上限 20 MiB；插件按统一格式提交附件，语音内部处理编码。需要通过链接交付本地附件时，设置 `--media-public-base-url https://<可访问的 origin>`，只将该 origin 的 `/plugins/awada/media/` 转发到现有 Gateway。链接自带临时 token；不因此公开整个 Gateway 或新开端口。公网媒体 URL 可直接使用。是否接受该内容由 server 决定，不按账号类型预先拦截。
- 本地 slash 默认读取 `<stateDir>/awada/commands.json`，或以 `--commands-file <已有 JSON 路径>` 写入插件 config.commandsFile（相对 stateDir）。格式和示例 handler 在 `<项目根>/awada/examples/`；配置静态标准回复或固定 exec 的 JSON stdin/stdout。先准备有效文件，配置脚本会检查显式路径；保留现有文件，不覆盖用户命令。新增/删除命令名或改注册元数据后正常重载插件。
- sales-cs 的实际演示素材写入其 `skills/demo-send/config.json.media`。媒体 origin、演示素材和业务知识分别配置。

## 生效与验证

脚本不重启 Gateway。按用户已确认的维护窗口和部署方式处理重载/重启；用户已授权时延续该授权，不重复询问。若当前仅获准源码开发，不应用运行配置、不重启或切换服务。

配置后请 main 执行 `sales-cs-enablement check-channel --account-id <账号> --probe`；该工具属于 main 的 sales-cs-manager。它只读取 V2 health 和带 key 的 capabilities，不发送消息。IT 也可在已启用插件且具备权限时用 `awada_api` 核对 health/capabilities。静态配置通过、WS 已连接和客户收发成功是三个独立结果；检查输出不代表实号验收。

- 检查所选账号、agent 注册与 binding。401/403 查 key 和 lane scope；lane 歧义/未找到应修正选择，不能回退 V1。
- 获准实号验证后，检查外部入站、普通回复和标准媒体；只有 operation result 的 `succeeded` 才代表操作执行成功。`queued/running/submitted` 继续查原回执，`unknown` 或部分失败不盲目新发。
- 业务能力使用 `awada_api capabilities/schema/operation/result/events`。动作名统一如 `room.getRoomList`、`todo.create`，先读 schema 再提交，不按账号挑选另一套动作。登录设备、客户端队列/维护、历史诊断、回调扩展、通信加密、原消息转发不向客户端开放；不要尝试绕过目录调用。业务操作遵循宿主工具策略和服务端权限，账号范围的结果查询保留 owner 限制。
- 普通本地图片继续使用标准 `message` 的 `media`。已存在于网盘的文件使用统一动作 `drive.send`，参数 `targets`、`fileName`、`kind`（`image|file`）及可选 `caption`；不要让 agent 选择底层协议或填写内部指令。业务操作不要求客户本人是 owner；非 owner 的 `result` 仅查询当前 agent/sessionId 已登记的回执，其他会话和历史未登记回执交 owner 核查，不能因查询被拒就重发。
- CustomerDB 验证在所配 workspace 下进行：`db/` 须存在且可写，`sqlite3` 命令可用；匹配账号的客户私聊应注入 `[CustomerDB]`，首次接触自动建档。客户回复后仅结束 sent_once 跟进，不取消 pending；cron/heartbeat 不执行客户回复处理。静默命令为 `/payment_success`、`/club_join`，不在 commands.json 重复注册。功能边界和完整配置见 `<项目根>/awada/README.md` 的 CustomerDB 节；非聊天服务事件和操作结果不应自动唤起 LLM。使用收到的原始目标 ID，不猜测可变昵称对应的稳定身份。

完整契约和迁移说明见 `<项目根>/awada/README.md`、`docs/AWADA-CLIENT-TRANSPORT.md`。
