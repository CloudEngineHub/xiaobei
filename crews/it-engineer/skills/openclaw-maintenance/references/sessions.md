# 指定会话的定位与重置

优先使用获授权的 sessions_* 工具，或 `openclaw sessions list --agent <id> --limit all --json` 定位本次目标，核对 agent、账号、联系人和完整 key，不凭昵称或手拼 key 删除。默认 list 有数量上限，未找到不能直接判不存在。

Awada 历史上可存在明文 peer 和 JSON 数组 peer 的 key 形态；以实际列出的 key 为准。身份比较只 trim/移除 ASCII 控制字符，**保留大小写**，不 lower()、不按同昵称合并。binding 路由变更通常无需删除会话；业务状态变化优先核对业务库/hook 的最新事实，不把重置历史当作业务开通或状态修复。

只在用户或本次派工明确要求重置目标历史时使用原生 sessions delete。以下分别为预览和执行入口，沿用已核实的原 key，不删除其他匹配项：

```bash
openclaw sessions delete '<完整key>' --agent <id> --dry-run --json
```

```bash
openclaw sessions delete '<完整key>' --agent <id> --yes --json
```

删除是管理动作，不像聊天 `/new` 那样主动回联系人；不为验收再发送消息。用结构化 `results[].status` 区分 deleted、not_found、failed，不把所有 exit 1 当已删除或全局故障。批量流程要写脚本维护明确 key 清单及逐项结果；不靠 stderr 文本猜成功。

删除会执行原生归档/运行清理语义，归档副本可能仍可被记忆检索；这不是彻底遗忘。如需删除索引记忆，另按明确授权和原生 memory forget 流程处理。只核对目标不再活跃；后续自然来信可确认新 session，不自动触达客户或扫描其他 agent 私人记忆。不要直接写库伪造重置，也不要复制单个活动 SQLite 文件来查历史。
