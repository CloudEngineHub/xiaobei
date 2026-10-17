# Sales-CS 复盘与升级（Review）

扫描 sales-cs 的客户反馈，结合用户意见产出升级建议，用户确认后由 main agent 直接改 sales-cs workspace 文件。sales-cs 是对外 crew，不自行升级，所有调整经本 workflow 落地。

**依赖**：`sales-cs-review`（反馈扫描）。workspace 文档修改由 main agent 直接编辑；channel / `openclaw.json` / schema 或 Automations 调度变更交 IT engineer。

---

## 前置条件

- sales-cs 已启用（`~/.openclaw/workspace-sales-cs/` 存在）。未启用 -> 先走 Enablement workflow。

## 执行流程

### Step 1 · 扫描反馈

```bash
sales-cs-review
# 或限定时间窗：
sales-cs-review --since 2026-06-01
```

输出 JSON：反馈条目数、按文件分布、高频关键词（投诉/退款/价格/试用/开票/人工…）。输出字段细节见 `sales-cs-review` 工具说明。

### Step 2 · 结合用户意见生成升级建议

读反馈摘要 + 用户本轮诉求（用户临时发起时）或定期巡检发现（main agent 自查时），提出具体建议，**不直接动手**，先呈现给用户确认。建议对象：

- **客服手册（MEMORY.md）**：补/改 FAQ、价格政策、开票流程
- **话术（AGENTS.md 意图分流段）**：调整各场景应对策略
- **本机工具备忘（AGENTS.md → Tools）**：更新实际路径、环境变量名称和工具别名；不新建 TOOLS.md，不把技能操作手册或密钥值复制进去
- **IDENTITY 称呼**：改对外自我称呼
- **DECLARED_SKILLS**：增减 sales-cs 可用技能（如加 `order-cli` 查订单）
- **SOUL.md**：调整语气/边界（少见，谨慎）
- **主动跟进规则与调度**：话术和业务范围按本流程确认；频率、时段、启停和账号调整再走 [Follow-up Scheduling](follow-up-scheduling.md)，交 IT 更新既有任务，不新建 HEARTBEAT.md

呈现形式：

```
建议改动：
1. MEMORY.md「常见问题 FAQ」补一条：退款流程 -> 引导填反馈问卷
2. AGENTS.md 3.1 话术：把"先讲适合解决什么问题"改为"先问客户场景再匹配"
3. IDENTITY 称呼：小明助手 -> 小贝同学
确认后我直接改 sales-cs workspace。
```

### Step 3 · 用户确认后落地

用户确认后，main agent **直接编辑** `~/.openclaw/workspace-sales-cs/` 下的对应文件：

- `MEMORY.md` / `AGENTS.md` / `IDENTITY.md` / `SOUL.md` / `DECLARED_SKILLS`
- 修改工具备忘时定位 AGENTS.md 的 Tools 节，只改指定内容，保留其他规则；旧 TOOLS.md / HEARTBEAT.md 由用户升级后手动删除，本流程不迁移或清理
- 改完报平安：列出改了哪些文件、改了什么
- **不需要 spawn IT engineer**（这些是 workspace 文档，不是 openclaw.json / channel 配置）
- 若涉及 channel / openclaw.json / schema 或 Automations 调度变更 -> spawn IT engineer；保留既有 jobId、未完成回执和其他任务

### Step 4 · 核验生效范围

AGENTS.md（含 Tools 节）、SOUL.md、IDENTITY.md 等正文更新通常在后续符合加载条件的运行中生效，不因改文档就重启 Gateway。子 agent 不自动加载 SOUL.md；必须随派工生效的约束放在 AGENTS.md 或任务说明里。

DECLARED_SKILLS 或 SOUL.md 的 crew-type 是安装/权限声明输入，修改后交 IT 通过安装同步流程更新实际技能与权限配置，再验证；不把重启当作声明同步。渠道、插件或配置变更是否需要重载/重启，由 IT 按当前版本和既有维护授权处理。

---

## 调整边界

| 类别 | 范围 |
|------|------|
| **可改** | sales-cs workspace 下所有 .md / DECLARED_SKILLS / 业务知识 |
| **慎改** | SOUL.md（角色边界）；heartbeat 基础配置和已有主动跟进调度须按用户要求交 IT 核对 |
| **不改** | sales-cs 的 `feedback/` 历史记录（只读，用于复盘） |
| **转交** | customer-db schema 变更、channel / `openclaw.json` / Automations 任务和 monitor scratch -> IT engineer |

## Pitfalls

- **没确认就改**：必须先呈现建议给用户确认，再落地。sales-cs 面对外部客户，误改话术影响真实对话。
- **把改文件当作配置验收**：binding / agents.entries 交 IT 修改后，分别核对配置和实际路由；不能一概假设必须重启，也不能只凭保存成功宣布已生效。
- **业务知识双写**：`business_knowledge.md` + `business_knowledge/` 是软链到 main workspace 的，改业务知识在 main workspace 改，不要在 sales-cs workspace 改软链目标。
- **把一次性问题当系统性问题**：单条负面反馈先核对原始对话再决定是否升级话术；多次出现的同类关键词才作为手册/话术修改依据。
