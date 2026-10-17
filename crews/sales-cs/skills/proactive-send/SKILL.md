---
name: proactive-send
description: 使用 OpenClaw 标准 message 工具向 awada 客户主动跟进，并确认服务端执行结果。
metadata:
  openclaw:
    emoji: 📤
---

# 主动跟进

何时联系、联系谁和话术由业务流程决定。当前对话的普通回复直接输出 assistant 文本；主动跟进使用与飞书相同的标准工具：

```text
message(action="send", channel="awada", target="user:<SenderId>", message="您好，之前聊到的演示材料已经准备好了。")
message(action="send", channel="awada", target="user:<SenderId>", message="演示材料", media="/absolute/path/demo.mp4")
```

多账号时指定 `accountId`。用户 ID 来自标准上下文 `SenderId`，不能将 CRM 的归一化 peer 当作原始路由 ID。

- 保存返回的 operationIds/messageId；它们是 Relay 的 eventId。
- `queued`、`running`、`submitted` 表示尚未确认执行，使用 `awada_api(action="result", operationId="<eventId>", waitMs=10000)` 查询；本地定时任务须具备对应账号的工具权限。
- 只有所有步骤 `succeeded` 后才能将跟进任务标为已发送；`succeeded` 不表示对方已读。
- 排队、超时、`unknown` 或部分失败时，保留回执并继续核对原操作；不要创建新发送任务重试。`failed` 须先检查是否已有部分发送，再决定后续操作。
- 话术保持简短、自然，不向客户重复发送同一条内容。

旧自动任务可继续调用 `proactive-send --user-id-external "<SenderId>" --text "<正文>" [--account "<accountId>"]`。该 wrapper 只转交标准 `openclaw message send --channel awada --json`，不读取 key 或直调 Relay。exit 0 只表示标准发送调用被接受，输出 JSON 中的排队回执仍需查询执行结果。

## 定时扫描到期跟进

只有被已配置的 Automation 或明确的心跳 scratch 调用时执行；HEARTBEAT.md 不是运行入口。main 通过 `sales-cs-manager` 定义业务范围，IT 管理 schedule，sales-cs 不自行创建、调整或停用系统调度。

1. 从自身真实 workspace 运行 customer-db 的到期查询，使用该技能提供的 follow-up-due.sh 具名脚本；只处理本任务授权范围内的记录。无到期记录时保持静默。
2. 对每条记录读取 context_summary，生成不超过三句话的自然跟进。目标来自记录的原始 user_id_external，账号来自本任务明确配置；不要依赖定时会话中不存在的当前客户 Sender/CustomerDB 注入，也不要猜账号归属。
3. 回执账本使用 `db/follow-up-receipts.json`，以 `<id>:<status>` 区分本次跟进。保存发送意图、话术、账号及返回的 operationIds/messageId，不保存 key。有原回执先查原操作；有意图但无回执先对账，不自动重发。不覆盖已有账本，不把旧账本当成不存在；账本不可读或无法保存时停止对应记录的发送。
4. 按上文标准 message 和 awada_api 规则发送并确认。全部 succeeded 后，使用 customer-db 已有的 follow-up-mark-sent.sh 或 follow-up-complete.sh 具名操作推进 `pending → sent_once → completed`；最多两轮。若发送已成功但业务状态更新失败，保留成功回执，后续只补状态，不重新发送。
5. 排队、超时、unknown 或部分失败保持业务状态并留待对账；客户明确不再跟进的按业务规则取消。不要自动执行旧的 48 小时过期清理，也不因任务迟到擅自增加次数。
6. 本任务的 Automation delivery 为 none，客户消息仅通过 message 发出。异常记录给可信操作者，不能把客户名单或内部字段发给其他客户；不在当前客户会话重复播报扫描总结。
