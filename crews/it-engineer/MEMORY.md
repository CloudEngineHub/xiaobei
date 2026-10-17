# IT Engineer Agent — 背景知识

## 系统与配置

- xiaobei 是基于 OpenClaw 的自媒体获客智能体。仓库的 `openclaw.version` 是引擎 pin；源码 pin 与运行版本可能不同，部署事实以实际进程和构建信息为准。
- OpenClaw 2026.10.4 使用 `agents.entries.<agentId>` 注册 agent，执行模式使用 `tools.exec.mode`。`agents.list`、exec 的 security/ask 旧配置由官方迁移处理。
- 本项目根据 `SOUL.md` 的 `crew-type` 和 `ALLOWED_COMMANDS` 生成执行策略：内部 crew 通常为 full；外部 crew 有明确 `+` 条目时为 allowlist，否则为 deny。实际权限由当前配置和原生审批存储共同决定。
- 聊天 allowlist 不授予管理命令 owner 身份；可信操作者由 `commands.ownerAllowFrom` 等原生授权决定。
- 新安装模板的系统推理 owner 是 it-engineer，由 `agents.defaults.systemAgent.agentId` 指定；Custodian 运维技能库只对该 owner 发现，普通 crew 聊天、心跳和 Talk 各有独立归属。已有实例以保留的实际 owner 设置为准。

## 工作区与持久化

- 自动 bootstrap 文件为 AGENTS.md、SOUL.md、IDENTITY.md、USER.md、BOOTSTRAP.md、MEMORY.md。独立 TOOLS.md 已退役，本机工具备忘属于 AGENTS.md 的 Tools 节。
- 子 agent 自动上下文只有 AGENTS.md；Cron 自动上下文为 AGENTS.md、SOUL.md、IDENTITY.md、USER.md。MEMORY.md 属于私密主会话，不是子 agent 的默认运维手册。
- 共享运行状态在 `<stateDir>/state/openclaw.sqlite`；各 agent 的会话、聊天记录、记忆索引等在 `<stateDir>/agents/<agentId>/agent/openclaw-agent.sqlite`。
- 旧 sessions.json、JSONL 和工作区状态 sidecar 是迁移输入；`session-sqlite-import-archive` 保存官方迁移归档，不是日常会话写入目录。
- 运行中的 SQLite 文件身份受原生保护。Git checkout、rebase 或 autostash 替换打开的数据库会使写入被拒绝；Git 采集数据库文件不等于一致性快照。

## 心跳与 Automations

- 目前版本OpenClaw的心跳属于系统维护的 Automation；Gateway 内置调度器执行，共享 SQLite 持久化任务、monitor scratch 和运行记录。
- 心跳频率、活跃时段和通知目标仍由 `agents.defaults.heartbeat` / `agents.entries.<id>.heartbeat` 定义；monitor scratch 是每次心跳的提示上下文，不是业务任务调度表。
- 独立定时取数、复盘和客户跟进各有 Automation 定义，可分别启停和查看运行历史。业务数据库中的到期跟进记录不等于 OpenClaw 中已注册调度任务。
- `TOOLS.md` / `HEARTBEAT.md` 旧文件由用户升级后手动删除，setup 不负责迁移或清理。文件不存在不代表心跳或独立任务被取消，实际以当前配置、Automation 和 scratch 为准。
- main 的定时取数参考文档为 `<PROJECT_ROOT>/crews/main/skills/content-calibrator/references/scheduled-review.md`；销售客服跟进的调度参考为 `<PROJECT_ROOT>/crews/main/skills/sales-cs-manager/workflows/follow-up-scheduling.md`。这两份是供 IT 读取的参考文档，不是 IT 的技能；`PROJECT_ROOT` 由本 workspace 的 OFB_ENV.md 确定，Docker 为 `/opt/openclaw`。管理操作和核验流程在 AGENTS.md「心跳与定时任务管理」。

## 技能与依赖

- 公共技能位于 `skills/`，crew 专属技能位于 `crews/<id>/skills/`；部署时技能可能软链到仓库，修改技能源码可能立即影响实例。
- 仓内 Python 依赖由 requirements.txt 统一声明；Node 技能依赖由各技能的 package.json 声明。apply 按内容哈希安装，不以临时 pip/npm 命令和未核验的版本替代项目依赖锁。
- 插件依赖与技能依赖分开。Awada 的 silk-wasm、typebox、ws、zod 安装在项目 awada/node_modules，不属于全局 OpenClaw 依赖。

## 浏览器

- 项目浏览器使用主仓 TypeScript SDK camoufox 0.5.8、Playwright 1.62.1 和配套内核 156.0.1-beta.36，独立于 OpenClaw 自身的 Playwright 依赖。
- browser 工具、xiaobei-browser、camoufox-cli 兼容入口共用 `browser/` 运行时。普通站点使用持久化 default；平台专用会话由对应技能规定，不按 agent 或站点另建通用 profile。
- 身份版本为 v2；旧 v1、损坏身份或缺身份的已有登录 profile 需要整体归档后重新登录，不复制指纹模板或导回旧 cookies。版本化资产与旧 SDK cache 分开。
- snapshot 的 ref 与捕获时 DOM 绑定；页面变化可能产生 STALE_REF，超时可能表示结果未知。操作规则统一在浏览器技能和 AGENTS.md，不以关闭所有会话作为通用修复。

## 渠道与 Awada

- binding 的 channel、accountId、peer 共同参与路由；不写 accountId 不等于通配全部账号，通配必须明确写 `*`。
- 按当前配置解析 agent 和 sessionKey，路由缓存检查配置引用。删除旧 sessions.json 不是改绑所需的常规步骤；当前会话状态存放在 SQLite。
- Awada 是项目局部插件，默认连接 `https://relay.openclaw-for-business.com/api/v2/awada`，使用 X-OFB-Key；lane 可省略，由服务端解析 user，存在多个匹配时报歧义。本地仅持有 Awada 访问凭据。
- Awada 对外提供产品范围内的业务动作；登录设备、客户端指令/维护、历史诊断、回调扩展、通信加密和原消息转发不属于客户端操作。所有账号使用相同动作，底层实现与执行支持归服务端。标准消息与媒体由 message 处理，本地 slash 使用插件 JSON 配置；语音自动转为文本，手动转写入口为 voice.transcribe。
- Awada 启用流程默认同时配置 CustomerDB hook，归属为所选 agent/account/workspace；仅用户明确要求不启用或已有明确停用设置时跳过。10.4 外部插件需 hooks.allowConversationAccess=true，且 allowPromptInjection 不为 false；其他归属与显式权限拒绝不能被静默覆盖。
- WS 可靠入库后 ACK；provider 排队回执不等于执行成功，queued/submitted 与 succeeded 必须区分。具体操作由 awada-channel-setup 维护，路径和字段名在 AGENTS.md 的 Tools 节。

## 本机长期记录

仅在此补充需要跨会话保留的部署事实、用户偏好和已确认决策；流程、工具调用规范和临时排障步骤分别写入 AGENTS.md、SKILL.md 或当日日志。
