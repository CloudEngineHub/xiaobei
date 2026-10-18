---
name: sales-cs-enablement
description: sales-cs 启用的机械操作工具：Awada V2 账号与路由检查，以及 business_knowledge 软链建立。完整流程见 sales-cs-manager 的 Enablement workflow。
---

# sales-cs-enablement

## check-channel

```bash
sales-cs-enablement check-channel
sales-cs-enablement check-channel --account-id <账号> --agent-id sales-cs
sales-cs-enablement check-channel --account-id <账号> --probe
```

默认只读本地配置；`--probe` 另读 V2 health 和带 `X-OFB-Key` 的 capabilities，不发消息、不改配置。检查插件启用、账号 key、消息权限和 URL；支持顶层与 accounts 多账号，不因 channels.awada 非空就判成功。

输出 JSON：`configured`、`configuredAccountIds`、每账号的策略/错误、`boundAgents`、`boundToRequestedAgent`、`agentRegistered` 和可选 probe 状态。key 只显示存在与否，不输出原值。`configured` 只说明至少一个所选账号满足检查条件；不代表已经绑定 sales-cs、Gateway 已加载插件或实号收发成功。使用接收事件中的原始目标 ID，不把可变昵称当作稳定身份。

- 退出码 `0`：至少一个所选账号配置通过；继续检查账号归属和 binding。
- `1`：配置不完整、解析错误或所选账号探测失败；按输出派 IT 修复，不当成“从未配置”或覆盖整个配置。
- `2`：配置文件不存在；先确认实际路径，不立即新建配置。
- 路径优先级：`--config`、`OPENCLAW_CONFIG_PATH`、`OPENCLAW_JSON`、`OPENCLAW_STATE_DIR/openclaw.json`、`~/.openclaw/openclaw.json`。`${ENV_NAME}` 形式的 key 引用从环境解析；缺变量时不探测。

## link

```bash
sales-cs-enablement link
```

把 main workspace 的 `business_knowledge/` 目录软链到 sales-cs workspace；正文是目录内的普通文件 `business_knowledge.md`，从 workspace 根通过 `read` 读取 `business_knowledge/business_knowledge.md`。无参调用也等价于 link。

- 来源为 `~/.openclaw/workspace-main/business_knowledge/`；旧根目录正文迁入该目录，修正正文中的相对链接并同步工作区文档的路径引用。没有正文时复制仓库模板。
- 目标默认 `~/.openclaw/workspace-sales-cs/`；只建立目录软链，移除指向旧共享正文的文件软链。`--workspace <绝对路径>` 可重复指定其他 crew。
- 修改既有文件前备份到 main workspace 同级的 `backups/business-knowledge-*/`。新旧正文内容冲突、目标已有真实目录或旧正文并非本次共享软链时拒绝覆盖；按错误说明处理，不自行删除。
- `MAIN_WORKSPACE`、`SALES_CS_WORKSPACE`、`REPO_MAIN` 可覆盖路径。exit 0 成功，exit 1 需处理冲突。

编排和业务知识归 main，channel 配置与实例运维交 IT 的 `awada-channel-setup` / `work-channel-binding`。使用这里列出的 PATH wrapper，不拼内部脚本路径。
