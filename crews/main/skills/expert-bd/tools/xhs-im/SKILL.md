---
name: xhs-im
description: 小红书私信会话、单聊与群聊历史、未读、文本收发、标记已读、撤回消息及删除会话；复用 xhs-hunter PC 会话。
metadata:
  openclaw:
    emoji: 💬
    requires:
      bins:
        - python3
        - node
---

# 小红书私信

先运行 `xhs-hunter check`，会话缺失或失效走 `xhs-hunter login`。本工具归 expert-bd，复用 `xhs-hunter` 保存的 PC 会话，不混用 Creator Cookie。

## 读取

```bash
xhs-im list --limit 30 --cursor 0
xhs-im groups --limit 30 --cursor 0
xhs-im history --conversation 用户ID --limit 30 --cursor 0
xhs-im history --conversation group:群ID --limit 30 --cursor 0
xhs-im unread
xhs-im listen --seconds 60 --max-events 100
```

列表 cursor 是页码，历史 cursor 是上一页真实 store_id。保留原始响应，不猜游标或字段。群聊仅支持列表和历史，字段需用真实返回核对。监听逐行输出 JSON，每次最多 3600 秒、1000 条。

## 写操作

以下命令默认只预览；已有用户授权时，在同一命令加 `--confirm`。

```bash
xhs-im send 用户ID "用户授权的文本"
xhs-im read --conversation 用户ID
xhs-im revoke --conversation 用户ID --message 真实消息ID
xhs-im delete --conversation 用户ID
```

仅支持单聊文本发送。`read` 使用真实会话游标（含实际返回的 `max_store_id`）和独立未读接口状态；缺会话、目标未读数或必要统计时安全停止，不用默认零伪造回执，不清空其他会话计数。`revoke` 撤回指定消息，`delete` 删除本账号的会话，不能解释为替对方删除消息。群聊拒绝发送、已读、撤回和删除。

已读请求按网页 IM 客户端的实际构造逻辑生成：目标游标来自 `max_store_id`，目标 `unread_count=0` 表示标记后的剩余未读；单聊类型按真实 `info.is_friend` / `info.is_mute` 区分普通、免打扰、陌生会话。全局计数在本地把目标未读置零后计算，保留其他单聊计数，不把群聊未读混入单聊统计；字段来源或列表覆盖不完整时安全停止。协议证据见仓库 `docs/xhs-im-read-protocol-2026-10-24.md`，不要把通知接口的赞、关注、提及未读数代入，也不要让 agent 手填全局计数。

WebSocket `send` 返回 submitted 与 mid 只代表向连接提交，不能当作送达或已读。提交结果不明先查历史，不直接重发。只有确认未提交时才用 HTTP 发送：

```bash
xhs-im call send_short_link_message --kwargs '{"receiver":"用户ID","content":"已授权正文"}' --confirm
```

`methods` 列出底层接口；`call` 的写方法同样默认预览，加 `--confirm` 执行。只传真实接口字段，不猜捕获帧或加密消息。

## 自动回复前置判断（本地，不联网发送）

已授权的私信自动回复流程可使用 `_shared/xhs_im_reply_guard.py`（相对本技能目录为 `../../../_shared/xhs_im_reply_guard.py`）：

```bash
python3 <guard路径> check --conversation 用户ID --history-file <原始history响应JSON> --ledger <本workspace账本路径>
python3 <guard路径> record --conversation 用户ID --incoming-id <真实客户消息ID> --outcome unknown --ledger <账本路径>
```

- 只有 `ok=true` 且 `should_reply=true` 才能生成新回复；`unknown` 意图应在发送前写入，且记录结果必须 `ok=true`、`already_recorded=false` 才可发送；已被预占则停止。已提交则记 `submitted`，查历史确认存在后才记 `confirmed`。按会话和消息 ID 跨天防重，不按日期清空。
- 平台提示可能沿用客户 `sender_id`。以结构化 `messageSource` / 模板等字段识别，不把风控提示当新客户咨询，不靠“微信”等普通关键词误判真人内容。
- 有平台风控提示时，用 `record --outcome platform_notice --incoming-id <last_notice_id>` 保存提示标志。`suppress_external_guidance=true` 时停止自动发送联系方式、contact 链接和站外交易引导；即使以后有真实新问题，也只能在平台内答复，不改用暗语或短链绕过限制。
- 检查坏账本、未知消息类型或缺少真实标识时停止发送并报告；旧版仅按日期的账本记录不能自动丢弃或到期重发。

这些私信写操作与实时监听仍需真实账号验收，离线回归通过不等于平台已送达。私信材料只存当前任务受控目录，不写入代码仓。
