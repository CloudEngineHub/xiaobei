# Sales-CS 启用（Enablement）

main 负责用户选择、业务知识和 workspace 内容；IT engineer 负责 channel、账号、crew 注册与绑定。沿用用户已经明确的 channel/账号和运维授权，不重复征询。

## 1. 检查已有账号和路由

```bash
sales-cs-enablement check-channel
```

读取脱敏 JSON，区分账号配置、`agentRegistered`、`boundToRequestedAgent`：

- exit 0 只表示至少一个账号满足静态条件。已绑定 sales-cs 的账号优先复核；其他 crew 的账号不能抢占。多账号按用户指定选择，不默认取第一条。
- exit 1 查看具体错误，交 IT 修复，不能直接认定未配置并覆盖。
- exit 2 先确认实际 config/stateDir 路径，不能在错误位置新建配置。
- 用户已选其他 channel 时按对应路径处理，Awada 检查失败不自动改变用户选择。

## 2. 补齐必要选择

awada channel的开通必须 awada key, 这个要问用户获得，用户没有或者不清楚的话，让他联系wiseflow掌柜。联系二维码见`ofb_contact.png`, 素材存在时，用标准 `message(action="send", media="<main workspace>/ofb_contact.png")` 发送。

Awada 须明确 OpenClaw accountId、服务端账号标识（lane）、Awada key 和接待方式。key 只交 IT 的受支持配置输入，不写公开资料或日志；不收其他服务管理凭据。公开私聊使用 open + allowFrom ["*"]；pairing/allowlist 是限制接待范围的选择，不把它们报告为公开开放。

## 3. 派 IT 完成配置并回报

按用户所选 channel 派工：

- **Awada**：使用 `awada-channel-setup`，先脱敏预览，再应用指定账号/agent。该脚本已统一处理局部插件路径、账号、crew sample 注册、精确 account binding 和默认启用的 CustomerDB hook；不要再手工合入一次 sample，不改已有 tools/heartbeat/subagents。
- **飞书/企微**：使用 `work-channel-binding` 的配置流程；Awada 专属 CustomerDB hook 不因此对其他 channel 生效。
- **其他 channel**：按该 channel 的实际插件和注册流程处理，不称 Awada 为内置插件，不擅自换成 Awada。

Awada 派工时一并说明：

- 保留其他账号、crew 和插件路径；binding 写 `match.channel` + `match.accountId`，agent 顶层不写 channel。
- 启用 Awada 时默认一并配置 CustomerDB hook，限定本账号、sales-cs 和实际 workspace，并授予 hooks.allowConversationAccess=true；仅用户明确要求不启用或已有明确停用设置时跳过。已有其他归属或权限拒绝时报告冲突，不能改绑、混库或擅自省略 hook。核验 hook 注册与客户上下文注入，不仅核验 channel 连接。
- 需要通过链接交付本地附件时，配置可访问的 mediaPublicBaseUrl，并只转发现有 Gateway 的 token 媒体路由。公网素材 URL 可直接使用；附件的执行支持由 server 返回。
- 有本地 slash 需求时保留用户现有 commands.json，使用静态标准回复或固定 exec handler；新增/删除名字后按正常流程重载。
- 在用户已授权的维护窗口使配置生效；若只要求源码准备，不改运行态、不重启。返回配置摘要、绑定、运行状态和未完成验收项，勿返回 key。

IT 完成后，对选定账号执行：

```bash
sales-cs-enablement check-channel --account-id <账号> --probe
```

这只核对 V2 health、Redis 和 capabilities 鉴权，不替代 WS 连接和真实收发验证。获准实号测试后再核对普通消息、标准媒体和 CustomerDB 来访；provider 结果 `succeeded` 才表示执行成功，queued/submitted 继续查原回执，unknown/部分失败不盲目重发。

## 4. 完善客服内容与素材

结合 business_knowledge.md，填写 sales-cs workspace 的 AGENTS.md、IDENTITY.md、SOUL.md 中由 main 维护的占位内容，并遵循各文件职责。把演示素材实际本地绝对路径或有效 URL 写入 `skills/demo-send/config.json.media`；未准备好时明确记录待补，不写裸云端文件名或虚构路径。

本机路径、环境变量名称、工具别名等备忘写在 `AGENTS.md` 的 `## Tools` 节，不创建 `TOOLS.md`；操作步骤仍查对应 `SKILL.md`，密钥值不写入工作区文档。保留已有工作区的自定义正文；旧版本遗留的 `TOOLS.md` / `HEARTBEAT.md` 由用户升级后手动删除，启用流程不负责迁移或清理。子 agent 只自动加载 AGENTS.md，派工所需的客服边界和操作约束须在该文件或本次派工中说明。

普通回复直接输出 assistant 文本，媒体统一使用标准 `message`；不为 Awada 另写发送标签、sendAttachment 或独立音频转写规则。主动跟进遵守其技能中的执行回执核对流程。

用户要求定时主动跟进时，继续读取 [Follow-up Scheduling](follow-up-scheduling.md)，由 main 明确业务范围并派 IT 配置独立 Automation。HEARTBEAT.md 已退役，sample 的 heartbeat 频率也不能代替到期扫描任务；不能仅创建 follow_up 记录就承诺会定时发送。用户未要求时不默认启用。

## 5. 链接业务知识并交付

```bash
sales-cs-enablement link
```

正文和支撑材料统一在 main workspace 维护，sales-cs 只通过 business_knowledge.md / business_knowledge/ 软链读取。目标是真实文件时工具拒绝覆盖，确认来源后再处理。

向用户报告所选 channel/account、workspace、对外称呼、业务知识与演示素材就绪情况，并区分配置、服务连接和实号验收结果。知识仍是模板、素材缺失或测试未获准时如实列出；后续话术和资料优化由 main 按 Review workflow 负责。
