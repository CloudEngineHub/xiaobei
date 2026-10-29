# 心跳与 Automations

## 配置、任务与提示正文

| 需求 | 位置 |
|---|---|
| agent 心跳频率、活跃时段、模型、通知目标 | `agents.defaults.heartbeat` / `agents.entries.<id>.heartbeat` |
| 每次心跳的简短检查清单 | `heartbeat:<agentId>` 系统任务的 monitor scratch |
| 固定时间取数、复盘、客户跟进 | 独立 Automation 的 schedule、agentId、payload、delivery |

HEARTBEAT.md 已退役，不重建、不自动导入旧任务。scratch 不解析 cron 或 `tasks:` 来建立调度；独立任务不继承创建时的聊天或私人 MEMORY.md。普通 Automation 也有私有 scratch 读写接口，但**不能据此假设它会自动注入普通 agentTurn 的提示上下文**；执行细则放 payload 或其明确要求读取的 workspace 文件。

新装模板默认 `heartbeat.every="0m"`；只按用户需求开启。停用某 agent 定期心跳改该 agent 的 every 为 `"0m"`，不只 disable 生成的系统 job。当前 pin 通常保留 enabled=false 的 monitor 行；默认 list 隐藏停用项，不能误判为任务/scratch 已删除。停用或移除前仍保存当前 scratch 与原配置，恢复后按实际 jobId 和 revision 回读，不宣称所有版本都保留或删除。`cron.enabled=false` / `OPENCLAW_SKIP_CRON=1` 会停止调度；停心跳不等于停独立业务任务。

## 接到派工

1. 沿用已确定的业务范围与授权，补齐执行 agent/workspace、说明绝对路径、时间与 IANA 时区、活跃窗口、结果去向、现有 jobId。用原生工具列出相关任务（含停用项、完整分页），get 核对完整定义；无权限看到已知任务时交管理员，不重复建任务。
2. 固定业务按 jobId 更新或建立独立任务，通常 `sessionTarget="isolated"`、`payload.kind="agentTurn"`，明确 agentId、真实 workspace、说明/技能路径与参数、有限超时。不假设业务任务继承系统心跳的 activeHours；工具不能指定 agent 时使用已授权的管理 CLI/API，不误建在 IT 名下，不给外部 crew 开放任意 shell。
3. main 定时取数参考 `<PROJECT_ROOT>/crews/main/skills/content-calibrator/references/scheduled-review.md`；销售跟进参考 `<PROJECT_ROOT>/crews/main/skills/sales-cs-manager/workflows/follow-up-scheduling.md`。从 OFB_ENV.md 确认 PROJECT_ROOT（Docker 为 `/opt/openclaw`），只读参考，不能调用 IT 未配置的 main 技能。将选定内容放进目标 workspace 的任务说明或 payload，不改仓库技能来定制某个实例任务。
4. 明确唯一交付路径：报告类的**最终回复必须包含完整报告正文**，由调度器 delivery 投递，不再调用 message 重发；客户跟进由 sales-cs 的 message 按账号/peer 发送，设 `delivery.mode="none"`。失败通知若启用指向可信操作者。`NO_DUE_TASKS` 等成功空结果不触发额外 shell 验证。
5. 保存后回读 jobId、agentId/effectiveAgentId、schedule/时区、enabled、nextRunAt、payload、delivery；核对所引用文件存在、技能和工具可用。管理注册成功不等于执行成功。暂停按既有 ID 更新；移除前核对活动运行，保留业务数据、回执与无关任务。

## CLI 与 scratch

优先用原生 automations 工具；`cron` 是 CLI 兼容别名。独立查询如下，结果按当前工具 schema 和权限解释：

| 命令 | 用途 |
|---|---|
| `openclaw automations list --all --json` | 包括停用项；按实际返回读完分页 |
| `openclaw automations get <jobId>` | 完整定义 |
| `openclaw automations runs <jobId>` | 状态、错误、session 与投递记录 |
| `openclaw automations scratch <jobId> --json` | 正文与 currentRevision |

scratch 写回是整体替换。用 wrapper 保存当前正文和 revision 到 mode 600 的新文件，按用户要求编辑一份完整合并正文；保留无关巡检。写回 wrapper 从快照读取 jobId/revision，通过原生 CAS 更新并回读，冲突立即停止，不自动覆盖新版本：

```bash
openclaw-maintenance scratch-save --job <jobId> --output /绝对路径/scratch-before.json
```

```bash
openclaw-maintenance scratch-replace --snapshot /绝对路径/scratch-before.json --file /绝对路径/merged.md
```

merged.md 用真实换行；不把字面量 `\n` 当换行。快照仅用于**同一实例、同一任务**，不是跨实例导入。命令超时或写后回读失败时结果可能未知，先读当前 scratch，不重放写入。

## 判断何时执行及是否完成

心跳 activeHours 采用对应时区、左闭右开；`08:00–24:00` 覆盖 08:00–23:59，也支持跨午夜。`nextRunAtMs` 是原始节拍，可能落在窗口外；答复实际下一次时结合节拍、activeHours、时区和运行占用条件，不保证“到点一定执行”。

| run.error | 解释 |
|---|---|
| heartbeat skipped: quiet-hours | 本拍在活跃窗口外 |
| heartbeat skipped: cron-in-progress | 同 agent 的 cron 正在执行 |
| heartbeat skipped: requests-in-flight | 尚有在途回复/请求 |
| heartbeat skipped: no-route | 没有可用投递路由 |

`status=skipped` 即使 completionStatus 显示 failed，也不等同业务动作执行失败；读 error 再归因。连续跳过导致业务漏执行仍需报告，不能整类过滤。

报告类检查 run 的最终 assistant 正文是否完整，不只看 delivered=true。用获授权的 sessions_history 或原生会话查询；读取不到时说明缺口，不默认扫描其他 agent 的 SQLite/私密正文。只剩“报告如下”等占位符时视为内容未交付，检查 payload 的交付措辞。参考文档修正不会自动更新已有 payload。

字体/排版仅在用户提出时排查具体消息类型与渠道渲染，不把一次本机处理结果当通用修法，不承诺改 renderMode 必能对齐。核验不自动执行真实客户触达。
