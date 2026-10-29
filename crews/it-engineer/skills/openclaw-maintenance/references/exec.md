# exec 审批拒绝

- 分清 `tools.exec.mode`、原生审批策略与 workspace `ALLOWED_COMMANDS`。当前运行审批存于共享 SQLite；JSON 里没有 allowlist 不代表未配置。只用原生 approvals 接口维护，Gateway 不可达也不提供手写数据库兜底。
- 本项目按 SOUL.md 的 crew-type 与 ALLOWED_COMMANDS 生成策略：内部 crew 通常 full；外部 crew 有明确 `+` 条目时 allowlist，否则 deny。声明、配置与运行审批均要核对，不仅凭 crew 名称判断权限。
- 多 agent 同时被拒时核对错误原文和旧 `exec-approvals.json` / `.doctor-claim` 迁移门禁。不要创建退役文件、手动删迁移输入或盲目重启；按当前版本 Doctor 与管理权限处理。当前仓库 setup 已用 `scripts/sync-exec-approvals.mjs`，不能沿用“每次 setup 后必须重启”的旧结论。
- 部分技能被拒时核对原命令、cwd、解释器和脚本真实路径。引擎会考虑 symlink 的 realpath；声明中的 workspace 路径不一定匹配运行目标。当前 `scripts/lib/exec-tiers.sh` 已解析存在目标的真实路径，先确认实例是否已使用该版本。

独立查询/维护入口（路径和 agent 必须是本次已核实值）：

| 命令 | 用途 |
|---|---|
| `openclaw approvals get --json` | 当前审批快照与 hash；输出保存为受限文件供回退 |
| `openclaw approvals allowlist add --agent <id> <已核实的绝对真实路径>` | 原生添加，维护条目 id 与一致性 |
| `openclaw approvals allowlist remove --agent <id> <精确pattern>` | 撤销指定条目 |

修改运行审批后回读；如需跨 setup 保留，也更新该 workspace 的 ALLOWED_COMMANDS 中对应声明，保留用户其余条目。仅改声明不会立即更新运行审批，仅改运行审批也不保证下次 setup 保留。涉及备份、realpath、声明与运行审批同步的多步骤修复须写脚本调用原生接口，先呈现具体差异，不临时拼命令链。

不要为消噪放行通用 bash、python/node 解释器或宽泛通配符。脚本 exit 0 且无输出不一定失败；按其接口约定判断，`NO_DUE_TASKS` 是成功无任务，不反复用 `bash -c` / `ls` 验证。不改权限来掩盖业务脚本缺少成功/空结果标记的问题。

离线求值器只可作为分析证据；必须使用原生解析器保留引号与参数边界，并带上实际 mode、safeBins、cwd 等完整有效策略。不使用 Workshop 的 `command.split(/\s+/)` 简化模型，也不因离线 ALLOW 就声称运行授权已通过。核验命令须无副作用，不执行客户发送或发布来测试审批。
