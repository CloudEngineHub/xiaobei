# 定时取数与 DNA 复盘参考

本参考承接 main 原 HEARTBEAT.md 的取数与复盘流程，供用户开启定时取数时选用。它不自动启用任何任务，也不作为新的 HEARTBEAT.md 复制到工作区。

## 写入 Automation 的执行约定

- 执行 agent 为 main，工作目录为其真实 workspace，通常使用 isolated 会话。任务 payload 明确要求读取本参考的实际绝对路径、`content-calibrator` SKILL.md 及涉及平台的技能说明；不依赖私人 MEMORY.md 或创建任务时的聊天上下文。
- main 把用户选定的平台/账号、执行时间与时区、是否评估 DNA、报告去向交 IT engineer。IT 将下面执行内容写入原生 Automation payload，或保存为 main workspace 内的任务说明并由 payload 引用。schedule/启停以原生任务为准，修改本参考不建立调度。
- 已有同类任务时更新既有 jobId；旧心跳 scratch 或已转换 Automation 中包含相同流程时先对照、去重并保留其他任务。不要同时让系统心跳和新任务重复执行本轮。
- 尊重任务的超时、权限与调度设置；深夜运行按同一流程处理，故障记入报告，不临时唤醒用户。超时或中断后先核对已有产物和运行记录，不盲目重跑整轮。
- 每次运行只执行下列工作流程。平台间顺序执行；认证失效跳过该平台，技术故障保留错误后继续其他平台。不要在本任务中创建调度、再次派发整轮或等待子任务。
- **最终回复正文就是交付报告**：把完整报告写在本轮任务的最终回复正文里，由配置好的 delivery 投递一次；不要再另外调用消息工具重复发送同一份报告。夜间投递或延后通知使用用户已选的规则。
  > 反面示例：正文只写“报告如下（由 delivery 统一投递）”之类的一句占位符——委托方收到的就只有这句话，看不到任何报告内容。

## Step 1：各平台已发布作品取数

仅处理用户实际开启的平台/账号。每个平台先查询启用状态，仅 `ok=true, enabled=true` 时执行该平台批量取数一次；未启用跳过，状态读取失败记入汇总后继续下一平台。

| 平台专家包 | 状态查询 | 批量取数 |
| --- | --- | --- |
| expert-douyin | `published-track platform-status --platform douyin` | `douyin-engagement daily` |
| expert-xhs | `published-track platform-status --platform xhs` | `xhs-engagement daily` |
| expert-wx-channel | `published-track platform-status --platform wx_channel` | `wx-channel-engagement fetch-all` |
| expert-wx-mp | `published-track platform-status --platform wx_mp` | `wx-mp-engagement fetch-all` |

- 先读取相应 engagement 技能的操作说明。取数窗口、作品匹配、分页和指标来源由工具负责，工具回填 published-track；不要另行逐条取数、补翻页或让 published-track 自行采集。
- 抖音复用发布 profile 登录态通过 HTTP 取数，不调用 login-manager 或 hunter 修复登录。其他平台同样按各自技能约定使用登录态。
- 按逐条结果汇总完整成功、部分成功、跳过和失败。`complete=false` 必须报告缺项；存在 `unavailable` / `unavailable_reasons` 或分析错误时，列出实际取得的指标、缺项及原因。缺失值不填零，保留的旧值不算本次取得；`ok=true` 不代表指标齐全。
- 失败保留原始输出和退出码。明确登录失效，例如 `SESSION_EXPIRED`、`API_SESSION_MISSING`、`API_SESSION_EXPIRED`、`RUNTIME_EXPIRED`、`PLATFORM_AUTH_REJECTED`、`PLATFORM_LOGIN_REJECTED` 或技能约定的 exit 2，停止该平台本轮后续取数并列入待用户处理清单。验证码/身份验证待处理也列入报告；不自动扫码、登录或发送验证码。
- `PROFILE_SESSION_UNAVAILABLE` / `PROFILE_SESSION_INVALID`（exit 1）及超时按技术故障报告，保留 `stage` / `reason`。登录状态未确认时，不称为登录失效，不提示用户重新登录。
- 不注入 cookie 制造登录态，不反复刷新或重导航尝试恢复。小红书认证失败立即跳过，不追加批量请求。
- `NOT_ON_FIRST_PAGE` 按工具规则跳过该记录；`CREATOR_ITEM_NOT_FOUND` 保留作品 ID，报告待核对链接和账号，不按标题猜 ID。

本参考目前覆盖表内四个平台。其他平台不自动加入本轮。用户仅开启取数时完成本步后进入 Step 3。

## Step 2：DNA 表现评估（用户开启、达到数量阈值时）

每个（平台, DNA）的成熟待评估记录累积至少 5 条才评估。成熟为发布至少 3 天；待评估为 `perf_evaluated=0` 且 `dna_id` 非空。

对本次启用平台调用 `content-calibrator eval --platform <platform> --check`。全部 `triggered=false` 时跳过后续评估，报告待评估计数；有触发时按对应专家包 review workflow 完成聚合、归因、报告和已评估标记：

| 平台 | review workflow |
| --- | --- |
| douyin | expert-douyin 的 `workflows/review.md` |
| xhs | expert-xhs 的 `workflows/review.md` |
| wx_channel | expert-wx-channel 的 `workflows/review.md` |
| wx_mp | expert-wx-mp 的 `workflows/review.md` |

- 复盘只消费已入库数据，不重复取数。记录本轮数据新鲜度；没有新鲜有效指标时跳过相关评估或只报告可得证据，不能把旧值称为本次采集结果。
- 按 content-calibrator 的趋势优先、账号基线归一化、先排混杂再归因原则执行。数据不足的结论降级为观察。
- 报告写在 main workspace 的 `<platform>/dna/<dna-id>/evals/`，报告完成后按 review workflow 标记覆盖的记录，不在技能源码中写运行产物。
- **不得自动更新 DNA**。优化建议等待用户逐条确认后，再按对应专家包 style-dna workflow 回写。

## Step 3：返回汇总报告

把下列内容**完整写进本轮最终回复的正文**（不只看成“待投递的内容”）：最终回复就是交付物，配送由已配置的 delivery 自动完成一次。

1. 本次启用范围及平台取数结果：完整成功、部分成功、跳过、失败数量；部分成功附作品 ID、缺失指标和原因。
2. 明确认证失效、身份验证待处理的平台及账号；技术故障单列错误分类，不混同登录失效。需要登录的事项留用户方便时处理。
3. 开启 DNA 评估时报告本轮评估平台、dna-id、覆盖篇数、整体趋势及关键归因。无触发时列待评估计数；未开启时写明未执行。
4. 待用户确认的 DNA 优化建议：每条含目标维度/template 部分与证据篇目。
5. 未完成项和需要 IT 排查的技术故障。

本任务不包含客户留言、私信或评论自动回复；此类互动按 `expert-bd` 的实际能力和用户授权另行安排。
