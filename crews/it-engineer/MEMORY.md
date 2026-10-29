# IT Engineer Agent — 背景知识

- xiaobei 是基于 OpenClaw 的自媒体获客智能体；源码 pin、安装产物与实际运行版本可能不同。主仓维护产品配置、crew 模板、公共技能和专属技能，上游引擎是独立源码/构建目录。
- 新装实例的系统推理 owner 默认为 it-engineer，Custodian 运维技能库归实际 systemAgent；聊天 binding、心跳与 Talk 各有独立归属。实例已有明确设置可能不同。
- 当前持久化以共享与各 agent 的 SQLite 为主；旧 sessions.json、JSONL 和 session-sqlite-import-archive 属迁移来源/归档。删除活跃会话不等于清除所有可检索记忆。
- 公共技能在 skills/，专属技能在 crews/<id>/skills/；部署可能通过软链引用源码。Python 依赖统一声明，Node 技能依赖按包安装；Awada 插件依赖与技能依赖分开。
- xiaobei-browser 提供 Camoufox 受管生命周期，工具与兼容 CLI 共用 runtime；普通站点复用 default，平台有各自登录约定。profile 身份版本为 v2，登录与指纹状态属于用户持久化数据。
- Awada 使用统一 Relay V2 业务接口，本地只持有访问凭据；账号、binding 和 CustomerDB hook 共同决定接待归属。WS 入库 ACK、队列受理与业务成功是不同状态。

## 本机长期记录

在此追加已确认的部署事实、用户偏好和历史决策。工作流程与边界见 AGENTS.md，运维操作见 openclaw-maintenance，渠道配置见 awada-channel-setup / work-channel-binding；不在记忆中复制工具手册、密钥或临时排障结论。
