# 主动跟进调度（Follow-up Scheduling）

main 维护业务规则与用户选择，IT engineer 管理 OpenClaw 调度，sales-cs 在任务运行中执行到期跟进。沿用已有授权和配置，不因启用客服就默认开启主动触达。

## 1. 区分客户记录与系统任务

- `customer-db` 的 `follow_up` 表保存客户级的跟进时间、上下文与 `pending → sent_once → completed` 状态；写入一行不会创建 OpenClaw 调度。
- 原生 Automation 周期唤起 sales-cs 扫描到期记录，它有独立 jobId、schedule、启停状态和运行历史。
- 系统 `Heartbeat (sales-cs)` 的 monitor scratch 可以保留简短巡检，但不以 scratch 中写 cron 表达式建立任务。OpenClaw 2026.10.4 不读取 HEARTBEAT.md；不部署旧模板，也不从旧文件自动导入跟进任务。

## 2. 明确实际启用范围

补齐尚未确定的扫描频率、业务活跃时段与 IANA 时区、允许跟进的客户范围、channel/account、话术边界和异常报告去向。沿用用户已经确认的规则；未知时不要擅自选账号或扩大触达范围。

- 扫描频率决定多久检查一次，客户实际到期时间仍由 follow_up_at 决定；给用户说明这种延迟，不能承诺秒级精确发送。
- customer-db 当前用运行进程本地时间判断到期。IT 要核对 Gateway/容器时区、业务时区和 follow_up_at 口径；不一致时先解决，不能只给 cron 填一个 tz 就认为库内时间正确。
- Awada 多账号使用已确认的 accountId，并核对 CustomerDB 归属；不能把同一份无账号区分的到期列表交给多个账号各扫一遍。现有记录无法确认所属账号时暂停对应记录，不猜测接收方。

## 3. 派 IT 配置与核验

向 IT 提供：执行 agent `sales-cs`、真实 workspace、既有 jobId、频率/活跃时段/时区、channel/account、客户范围、操作说明与异常去向。IT 按其 AGENTS.md 的管理流程执行：

1. 核对实际已有任务（含停用项）、心跳 scratch 和迁移结果。同一客户库只保留一个获授权的到期扫描入口；已知 job 看不到时先核验权限，不据此重建。
2. 读取 sales-cs 的 `proactive-send` 和 `customer-db` 技能，整理用户选定的执行规则到 sales-cs workspace 的任务说明文件，或直接放入 payload。payload 明确给出说明/技能绝对路径、workspace、账号、范围和时区；不依赖创建任务的聊天、当前客户注入块或私人 MEMORY.md。
3. 用独立 Automation 执行，明确 `agentId="sales-cs"`、`sessionTarget="isolated"`、`payload.kind="agentTurn"`。任务需要的 message、awada_api 和 customer-db 具名脚本按实际权限核对；不开放任意 shell、系统配置或调度管理权限。
4. 客户消息由任务内标准 message 发送，`delivery.mode="none"`，避免调度器把总结再发送给某个客户。异常只交可信操作者，不把完整客户列表投递到最后一次聊天。
5. 本任务的活跃时段写入独立 schedule/执行规则；不要假设它会继承 heartbeat.activeHours。选择有限超时并保留原有其他任务配置。
6. 旧 scratch/Automation 已含同一跟进流程时，按已授权范围更新原任务或移走对应旧流程，保留其他巡检。完成去重后才启用新入口，不直接把旧 HEARTBEAT.md 重新写回。

## 4. 写入任务的执行要求

执行说明应要求 sales-cs 按 `proactive-send`「定时扫描到期跟进」执行：先通过 customer-db 查到期记录，无到期项保持静默；有到期项时按原始 user_id_external 与已确认的 accountId 发送，持久保存发送意图和回执，确认全部 succeeded 后才更新跟进状态。排队/超时/unknown 继续核对原操作，不再新发一条。

回执账本放在该 workspace 的 `db/follow-up-receipts.json`，与客户数据库一起留在获准业务目录，不写技能源码。既有账本若在其他位置，IT 应保留并迁移内容，不能按空账本重启发送。所有状态更新使用 customer-db 既有具名操作，不由 main 或 IT 以手写 SQL 代发或代改业务状态。

## 5. 验收、调整和停用

- IT 回读并提供 jobId、agent、schedule/时区、enabled、nextRunAt、delivery 和工具权限检查结果。main 登记已确认的任务事实与 ID，不将文档登记当作任务生效。
- 检查实际运行时区、无到期记录时静默、到期目标及账号正确、回执可恢复、成功后状态流转和旧入口已去重。实号发送只能在既有授权范围内验收，不为测试自行触达客户。
- `runs` 记录表示调度执行结果，Awada operation 结果表示发送执行结果；分别报告。权限或工具缺失、回执未知等未完成项明确列出。
- 用户调整频率/时段时交 IT 更新原 jobId；暂停时停用该扫描任务，保留 follow_up 记录及回执。客户级取消跟进按 customer-db 的规则处理，不能用停掉所有调度代替。
