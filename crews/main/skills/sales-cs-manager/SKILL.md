---
name: sales-cs-manager
description: 对外销售客服（sales-cs crew）管理技能。负责启用（channel、workspace、业务知识）、复盘升级（客户反馈、话术与客服手册）以及主动跟进定时任务的开启、调整和停用；调度由 main 派 IT engineer 管理原生 Automations。sales-cs 不自行升级或管理系统调度。零散 channel 检查、反馈扫描也可直接做。不涉及商务获客（expert-bd）、投资人关系（expert-ir）、content-producer 启用（AGENTS.md crew 管理）。
metadata:
  openclaw:
    emoji: ☎️
---

# sales-cs 管理（sales-cs-manager）

## 预设 Workflow

| 场景 | Workflow | 什么时候触发 |
|------|----------|-------------|
| sales-cs 启用 | Enablement | 用户想要对外客服 / 销售客服 / 公开接待客户的 agent；从零到可用的一次性完整流程 |
| sales-cs 复盘与升级 | Review | 用户想复盘 sales-cs / 调整客服话术 / 改客服手册 / 改对外称呼 / 增减客服可用技能；或 main agent 定期检查客户反馈 |
| 主动跟进调度 | [Follow-up Scheduling](workflows/follow-up-scheduling.md) | 用户开启、调整、暂停或停用定时扫描到期客户跟进；客服记录已到期但没有发送时也先核对该流程 |

## 资源命名约定

- Tools、Workflows 等名称是 `sales-cs-manager` 技能包内的逻辑资源名，不是 Agent Workspace 路径，也不要拼成相对路径执行。
- 工作区本机工具备忘使用 `AGENTS.md` 的 `## Tools` 节；这与包内的 `tools/` 资源目录不同，不初始化独立 `TOOLS.md`。具体文件分工按 Enablement / Review 执行。
- 技能部署后整个包通过软链进入运行环境；Agent 不要假设这些资源被展开到 Workspace 下。
- 其他文档中出现的 `~/.openclaw/workspace-sales-cs/` 等路径是实例真实路径，按字面解析；本包自身不落任何运行期数据，无 Workspace 数据目录。
- 只有工具清单中明确列出的 wrapper 名称可以直接作为 shell 命令调用；其余 Tool 名称仅用于定位对应说明。

零散操作（只想查下 channel 状态、只想扫下反馈）直接用下面的工具。

## 工具清单

| 工具 | 用途 | 命令 |
|------|------|------|
| `sales-cs-enablement` | Awada V2 多账号配置/绑定检查、可选只读探测 + business_knowledge 软链 | `sales-cs-enablement check-channel [--account-id <账号>] [--probe]` / `sales-cs-enablement link` |
| `sales-cs-review` | 扫描 sales-cs workspace 的客户反馈，输出结构化摘要 | `sales-cs-review [--since YYYY-MM-DD]` |

配置类操作（channel 绑定、`openclaw.json` 合入、Gateway 重启、daemon.env、customer-db schema）及 Automations 调度变更不在本包工具内，一律 spawn IT engineer 执行（渠道技能：`awada-channel-setup` / `work-channel-binding`；调度按其 AGENTS.md「心跳与定时任务管理」）。

Awada 是项目局部 Relay V2 插件。配置检查须看具体账号、策略和 binding，不因配置段非空就判为可用；不要把已有其他 crew 的账号抢绑 sales-cs。普通消息和媒体使用与飞书相同的 `message`，自定义 slash 放插件本地 JSON，完整能力由统一的 `awada_api` 目录提供。所有账号使用相同动作，支持情况由 server 返回，不询问或判断底层实现。启用时由 IT 核对客户接待权限、CustomerDB 账号归属和可选媒体 origin；main 配置实际演示素材，按执行回执验收。

## 核心治理边界

- **sales-cs 不自行升级**：它被设定为不根据客户反馈自主调整自己的 workspace 文件。对它的任何调整（记忆 / 话术 / IDENTITY / 客服手册 / 可用技能）都是 main agent 的责任，一律经 Review workflow 由用户确认后落地。
- **业务知识单点维护**：`business_knowledge.md` + `business_knowledge/` 只在 main agent workspace 维护，sales-cs workspace 通过软链只读访问（Enablement workflow 建链）。改业务知识在 main workspace 改，不要在 sales-cs 侧改软链目标。
- **反馈只读**：sales-cs workspace 的 `feedback/` 是客户反馈历史，只用于复盘，不修改、不删除。
- **跟进记录与调度分开**：customer-db 的 follow_up 保存客户级到期时间和发送状态，独立 Automation 负责周期唤起 sales-cs。HEARTBEAT.md、MEMORY 中的登记或 sample 的 heartbeat 段均不能证明扫描任务已启用；须以实际 jobId、schedule 和运行记录验收。
- **客户消息只发送一次**：跟进任务由 sales-cs 使用标准 message 主动发送，Automation delivery 设为 none；Awada 排队回执须确认 succeeded 后再更新业务状态。调度器运行成功也不等于客户消息发送成功。

## 边界

- 商业情报 / 市场研究 -> `expert-osbi`；潜客探索筛选 / 评论区互动 / 客户联络 -> `expert-bd`。
- 投资人发掘 / 融资跟进 -> `expert-ir`。
- content-producer 启用与调整 -> AGENTS.md「crew 管理」段（不走本包）。
