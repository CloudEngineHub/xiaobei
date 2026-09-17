---
name: demo-send
description: >
  Send product demo material to a free-status customer when they
  ask about concrete usage, want to understand the product form, or need a
  first visual reference before deeper sales qualification.
---

# demo-send

## 用途
当客户属于 `free` 状态，且提出具体使用问题、想先看看产品形态、或需要一个直观参考时，发送 demo 视频。

## ⭐ 唯一调用方式：一键脚本（2026-09-17 起）

直接执行脚本发送 demo 视频（**不要**使用 `message` 工具的 `sendAttachment` 手动发送）：

```
bash /home/ctyun/.openclaw/workspace-sales-cs/skills/demo-send/scripts/send-demo.sh --user-id-external "<客户昵称>"
```

> `<客户昵称>` 必须是客户库 `cs_record.peer` 中完全一致的昵称（含空格），
> 发送前脚本会校验收件人存在性，不存在会拒绝发送并 exit 1。

**脚本行为**：
- 固定发送微信网盘预存文件 `wiseflow5x.mp4`（唯一 demo 文件，已写死）
- 参数已全部封装，脚本自动构造正确的 file 消息，**无需手动拼参数**
- 成功打印 `✅ demo 视频(...)已发送给「...」: <streamId>`，exit 0
- 失败打印错误到 stderr，exit 1

## 完整发送流程

1. 执行上面的脚本（**本 turn 不输出任何文字**）
2. 工具返回成功（exit 0）后，在最后一个 turn 统一输出完整回复：
   - 说明已发送 demo 视频
   - 追问客户的具体需求或应用场景
   - 提醒官网/GitHub 主页获取最新信息

> **重要**：不要在调用脚本前生成任何文字（包括"我先给您发一份..."之类的介绍语），否则客户会收到多条内容相近的消息。

## 调用后必须做的事
发送 demo 后，**必须立刻追问客户的具体需求或应用场景**，不得只发完就结束。

## 如果脚本失败
- 若是 `收件人校验失败`：说明客户昵称拼写有误，检查客户库中的准确昵称（可用 `sqlite3` 查询 `cs_record.peer`），用完全一致的昵称重试一次。
- 若是 Redis 连接失败：报告给用户/上级，不要反复重试刷屏。
- 最多重试 1 次；仍失败则停止，如实告知客户"稍后为您补发"，并汇报给上级。
