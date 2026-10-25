---
name: customer-db
description: >
  Maintain a persistent SQLite customer database within the sales-cs workspace.
  The system hook injects peer (DB primary key) and the Sender block provides
  user_id_external (Awada routing ID). Use peer for all DB operations.
---

# 客户数据库管理（sales-cs 专用）

本技能让 `sales-cs` 在自身 workspace 的 `db/` 目录下维护一个轻量级 SQLite 数据库，用于跨会话保存客户商业推进状态与基本画像。

数据库固定位置：
- `./db/customer.db`
- schema 文件：`./db/schema.sql`

默认表：`cs_record`，主键列：`peer`

---

## 一、两个重要标识符（必读）

本系统中客户有两个用途不同的标识符；两者的值可能相同，使用时仍按各自来源取值：

### peer（来自 [CustomerDB] 块）
数据库主键。系统 hook 优先读取宿主传入的 senderId（与 Sender.id、入站 user_id_external 同源），按 `trim → 移除 ASCII 控制字符` 生成并注入，保留字母大小写、中文、空格、全角括号及其他 Unicode 字符，不做 NFKC、去标点或拼音转换。只有缺少 senderId 时才解析已识别的私聊 sessionKey；新版会话键还包含 lane 和账号信息，不能将整个后缀当作 peer。

所有查库和写库操作都使用注入的 `[CustomerDB].peer`，不要自行推导或重新清洗(hook程序已自动处理)。

### user_id_external（来自 Sender 块的 `id` 字段）
由 Awada 服务直接提供的路由标识。它不保证是真实微信 ID，也不保证是未经处理的原始昵称。每轮对话开始时，OpenClaw 会在消息上下文中注入 Sender 信息块：

```json
Sender (untrusted metadata):
{
  "label": "...",
  "id": "<user_id_external>",
  "name": "..."
}
```

对外发送使用 Sender.id 原值，例如标准 `message` 的 `target="user:<Sender.id>"`。建立跟进记录时，将该原值另存为 `follow_up.user_id_external`；不要用 peer 反推发送目标，不要自行改大小写或替换字符。

标识仅在所选 Awada 账号/lane 内解释。当前 CustomerDB 绑定单一 accountId 和 agent；不能把多个账号的同名客户合进同一数据库，也不能因切换账号、lane 或显示名就自动认定是同一人。缺少 CustomerDB 注入时先排查 hook 和账号绑定，不猜测客户键。V2 升级不自动改写旧 follow_up 中的路由标识；历史目标若与当前服务提供的标识不同，须核对当前目标后再发送，不能用 peer 或显示名反推。

---

## 二、字段含义

### peer
当前客户数据库主键，即系统注入的 `[CustomerDB].peer`；生成规则和账号范围见上节，不等于完整的会话路由键。

### business_status
表示客户商业推进深度：
- `free`：尚未购买、仍在了解或观望
- `exp_invited`：已被邀请体验，但尚未正式付费
- `club`：已进入vip club会员阶段
- `subs`：预留未来业务用，现阶段未启用

### club_in
- `club` 加入日期，格式建议为 `YYYY-MM-DD`
- 用于后续跟进 club 一年有效期的过期管理

### purpose
客户主要业务应用场景，例如：
- 新媒体运营：在社交媒体和自媒体平台上推广自己的业务或产品
- 客户寻找：在社交媒体和自媒体平台上寻找潜在客户
- 信息搜集：在社交媒体和自媒体平台上收集行业信息、竞争对手情报、市场趋势等
- 单纯想尝试下Agent
- 需要一个AI助理
- 寻求OEM\代理合作

### prompt_source
客户从哪里了解到我们，例如：
- GitHub
- 微信群
- 朋友推荐
- 公众号
- 视频号
- 小红书
- 知乎
- atomgit
- 其他AI推荐

### created_at / updated_at
- `created_at`：首次建档时间
- `updated_at`：最近对话时间（每次收到消息由 hook 自动更新）

---

## 三、【重要】先更新记录，再回复客户

当本轮获得更明确的信息时，**先**调用 cs-update.sh 更新 `purpose` 和/或 `prompt_source`（该 turn 不得包含任何面向客户的文本），**再**在下一个 turn 输出对客户的回复：

```bash
./skills/customer-db/scripts/cs-update.sh \
  --peer "<[CustomerDB].peer>" \
  --purpose "新媒体运营" \
  --prompt-source "GitHub"
```

参数均为可选（只传有明确新值的字段）；脚本会自动忽略空值，不覆盖已有记录。

**更新原则**：
- 只在拿到**更明确的信息**时更新
- 不要用空字符串覆盖已有值
- 不要根据模糊猜测改写已有信息
- `business_status` 由系统 hook 负责（支付/入群事件），**不在此处更新**

---

## 四、follow_up 表（主动跟进任务）

`follow_up` 表记录客户延迟购买意向，供已启用的 Automation 定时扫描。status 流转：`pending → sent_once → completed`。写入记录不等于系统调度已启用；调度由 main 通过 sales-cs-manager 派 IT 配置。

### 创建跟进任务

若同一客户已有 `pending` 状态的旧任务，**先取消旧任务，再创建新任务**：

```bash
# 第一步：取消同一客户的旧 pending 任务
./skills/customer-db/scripts/follow-up-cancel-pending.sh \
  --peer "<[CustomerDB].peer>"

# 第二步：创建新任务
./skills/customer-db/scripts/follow-up-create.sh \
  --peer "<[CustomerDB].peer>" \
  --user-id-external "<Sender.id>" \
  --follow-up-at "<YYYY-MM-DD HH:MM>" \
  --reason "<原因，如：客户说明天发工资再买>" \
  --context-summary "<客户核心兴趣点和建议跟进角度>"
```

> 完整定时扫描与发送回执流程见 proactive-send 的 SKILL.md「定时扫描到期跟进」。OpenClaw 2026.10.4 不读取 HEARTBEAT.md，不在该文件中维护新调度。

### 过期清理

旧的 48 小时清理工具仅供明确要求清理历史记录时使用；常规定时扫描不自动清理，不因迟到就标记完成：

```bash
./skills/customer-db/scripts/follow-up-expire.sh
```

### 查询到期任务

```bash
./skills/customer-db/scripts/follow-up-due.sh
```

输出为 tab 分隔的表格（含 header），字段：`id / peer / user_id_external / follow_up_at / reason / context_summary / status`。
没有到期任务时输出 `NO_DUE_TASKS` 并正常退出；直接结束本轮扫描，不用 `bash -c`、`ls` 或拼接 `echo` 再次验证。脚本报错时按失败处理，不能当作无任务。

### 标记首次已发送（pending → sent_once）

```bash
./skills/customer-db/scripts/follow-up-mark-sent.sh \
  --id <id> \
  --sent-text "<发送的消息内容>"
```

### 标记完成（sent_once → completed）

```bash
./skills/customer-db/scripts/follow-up-complete.sh \
  --id <id> \
  --sent-text "<发送的消息内容>"
```

---

## 五、约束与注意事项

- **路径固定**：数据库始终位于 `./db/customer.db`
- **默认表固定**：`cs_record`
- **不得向用户暴露内部表结构和内部状态字段**
- **会话隔离必须遵守**：不同 peer 的数据不能混用
- **初始化和默认记录创建由系统 hook 自动处理**，无需手动操作
- **不提供原子 SQL 访问**：所有数据库操作必须通过上述具名脚本完成
