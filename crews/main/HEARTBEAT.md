# 心跳/定时任务

## 凌晨复盘任务

### 执行约束

1. **无时间限制**:任务执行不受深夜时间限制,必须执行完 HEARTBEAT 清单全部内容

2. **遇到技术故障时处理方案**:

   - **spawn IT Engineer**协助解决:调用 `sessions_spawn`,将问题现象、错误信息、当前任务上下文完整传递给 IT Engineer,请它协助解决。**spawn 后 fire-and-forget,严禁 `sessions_yield` 等待**——IT Engineer 的结果通过 announce 异步回来,若没回来按下一条跳过继续(见下方约束 3);
   - 仍无法解决 → **跳过当前任务,继续执行后续步骤**,不要卡住整个 HEARTBEAT

   不可:
      - ❌ 呼唤用户协助解决,HEARTBEAT 在深夜执行,喊用户也没用
      - ❌ 不可中断任务,通过以上三步依然无法进行的任务则跳过,继续执行后续步骤,绝对不允许中断HEARTBEAT!

3. **⛔ cron/heartbeat isolated session 中禁止 `sessions_yield`,原则上也不 spawn subagent**:

   本任务由 cron 以 `session_target=isolated` 启动,**本身已是独立上下文**,不占主 agent 上下文、不阻塞主 session。再 spawn subagent 是零收益纯增复杂度,且 `sessions_yield` 会**直接 abort 当前 run**,cron 将 yield 视为 run 结束并标记 outcome,session 变 inactive;subagent 完成后的 announce 找不到可唤醒的活跃 session,retry 3 次后 give-up,**后续 Step 全部丢失**。

   - 所有 Step 1–5 **顺序内联执行**,评估报告等产出主 agent 自己写,不 spawn subagent、不 `sessions_yield`。
   - 唯一允许 spawn 的是约束 2 的「故障兜底 spawn IT Engineer」,且必须 fire-and-forget(不 yield)。

4. **⛔ 登录失效一律「跳过 + 记录 + 汇总上报」，严禁硬行恢复登录**

   任何平台的取数端登录失效（`SESSION_EXPIRED` / 探活失败 / 浏览器跳登录页等）时，**必须**：
   - 立即**跳过该平台**本轮取数，不再尝试任何取数动作；
   - 把平台名记入 `EXPIRED_PLATFORMS`，在 Step 5 统一汇报，由用户**白天**重新登录；
   - **不得**在凌晨心跳里扫码登录、不得唤醒用户。

   **严禁的"硬行恢复"动作**（任一都可能触发平台风控/限流/封号）：
   - ❌ 用 CDP `Network.setCookies` 把本地存的 cookie **注入**浏览器去"造"一个登录会话
   - ❌ 反复刷新/重导航 profile 页试图"刷出"登录态

   > 本规范下方 Step 2 / Step 5 已写明，但 **2026-06-29 凌晨 Agent 未遵守**：xhs-browse 浏览器无登录态时，Agent 用 CDP 注入 22 个 cookie 强造会话后批量抓取，**当日触发小红书风控、账号被处罚**。故在此特别前置强调。

5. **⚠️ 小红书 (xhs) 封号风险显著高于其他平台**

   - xhs 对「会话凭空 materialize + 短时批量签名请求」极度敏感，**一次** CDP 注入 cookie + 批量 feed 抓取就可能触发风控/限流/封号。
   - xhs 任何登录失效迹象 → **立刻整段跳过 xhs**，不要尝试任何恢复，记入 `EXPIRED_PLATFORMS` 等白天重新登录。
   - 取数走 `xhs-engagement`；

---

### 工作流程

#### Step 1: 通过 published-track 读取待取数的已发布内容

> **取数范围仅限完全支持 Expert 架构的 4 个平台**：douyin / xhs / wx_mp / wx_channel。kuaishou / bilibili 等其余平台不取数（发布记录照常入库，仅不抓互动数据），见 Step 2 第 5 条。

```bash
# 对纯 HTTP 脚本平台（douyin），查询近期记录（取数时效窗口内，见 Step 2）
published-track query --platform douyin --limit 50
```

列出取数时效窗口内的记录，准备在 Step 2 中逐条更新互动数据。**xhs / wx_mp / wx_channel 三个 camoufox 平台无需本步查询**——它们的 `fetch-all` 会自己查 DB 全量行并与后台首页匹配（见 Step 2 第 2/3/4 条）。

---

#### Step 2: 依次获取已发布内容的互动数据并更新到 published-track

按平台分两类情况：取数范围内的 4 个 Expert 架构平台（第 1–4 条）逐平台取数；其余平台（第 5 条）一律跳过。第 1 条纯 HTTP 平台按 id 逐条取数；第 2/3/4 条 camoufox 平台**每平台只跑一次 `fetch-all`**——打开后台列表**首页**一次，解析页内全部作品，匹配 DB 全部行逐行写库，首页没有的行报 `NOT_ON_FIRST_PAGE` 跳过（这是设计，见「取数时效窗口」）。

1. **douyin（抖音）** —— 走 `published-track fetch-metrics`（纯 HTTP+cookie 链路：login-manager 探活 → fetch-retro-data.ts → 写库），对 Step 1 查出的每条记录按 id 逐条调：

   ```bash
   published-track fetch-metrics \
     --platform <platform> --id <rowid>
   ```

   脚本封装了完整流程，返回统一 JSON 结果。**xhs / wx_mp / wx_channel 不走这个脚本**——机制不同，见下方第 2/3/4 条。

2. **小红书 (xhs)** —— **走 `expert-xhs` 包内 `xhs-engagement` 技能**（PATH wrapper 同名），camoufox 抓 creator 创作服务平台后台方案，与第 1 条 douyin 的纯 HTTP+cookie 链路机制完全不同，两条路独立、不耦合：

   ```bash
   xhs-engagement fetch-all
   ```
   > ⚠️ 不要调 `published-track fetch-metrics --platform xhs`——该子命令对 xhs 直接 exit 1 报错提示走 xhs-engagement。两条链路独立维护，避免机制错配。

3. **微信公众号 (wx_mp)** -- **走 `expert-wx-mp` 包内 `wx-mp-engagement` 工具**（PATH wrapper 同名），camoufox 抓创作者中心方案，与第 1 条 douyin 的纯 HTTP+cookie 链路完全不同，两条路独立、不耦合：

   ```bash
   wx-mp-engagement fetch-all
   ```
   > ⚠️ 不要调 `published-track fetch-metrics --platform wx_mp`——该子命令对 wx_mp 直接 exit 1 报错提示走 wx-mp-engagement。两条链路独立维护，避免机制错配。

4. **微信视频号 (wx_channel)** —— **走 `expert-wx-channel` 包内 `wx-channel-engagement` 工具**（PATH wrapper 同名），camoufox 抓视频号助手后台方案，与 wx_mp 同源（camoufox + 解析 innerText）、与第 1 条 douyin 的纯 HTTP+cookie 链路机制完全不同，两条路独立、不耦合：

   ```bash
   wx-channel-engagement fetch-all
   ```
   > ⚠️ 不要调 `published-track fetch-metrics --platform wx_channel`——该子命令对 wx_channel 直接 exit 1 报错提示走 wx-channel-engagement。两条链路独立维护，避免机制错配。

5. **其他平台**（kuaishou / bilibili 等）—— **不在取数范围**。自动取数仅覆盖完全支持 Expert 架构的 4 个平台（douyin / xhs / wx_mp / wx_channel）；kuaishou / bilibili 等其余平台只保留发布记录（`record` / `query` 照常支持），**不抓互动数据**，直接跳过，不要尝试任何取数动作。

##### 取数时效窗口

**发布超过 30 天的内容不再每天抓取互动数据**——数据已稳定，边际变化可忽略，反复抓只浪费配额/增加风控暴露。按平台类型：

- **camoufox 后台方案**（xhs / wx_mp / wx_channel）：`fetch-all` **永远只打开并解析后台列表首页，不翻页**——首页本身就是天然窗口，页内有什么解析什么；首页之外的老作品报 `NOT_ON_FIRST_PAGE` 自然跳过，**这是设计不是 bug**，不要加翻页逻辑去补抓老内容，也不要按天数过滤 DB 行（少操作一次页面就少一次风控暴露）。
- **纯 HTTP 脚本方案**（douyin）：Step 1 查询时加 `publish_date >= date('now', '-30 days')` 过滤，超过 30 天的行直接跳过不调 `published-track fetch-metrics`。

**DNA 评估（Step 3）不受此限**

##### 通用规则

- **必须传 `--id <rowid>`**（脚本类平台）：`<rowid>` 取自 Step 1 查询结果里的 `id` 字段。同一 `source_folder` 可能对应多条记录（同内容重复发布到不同帖子），按 `--id` 逐条抓取/写库才能让每次发布各自独立统计；若只传 `--source-folder`，脚本会只抓一行指标却批量写进所有同 folder 行，造成重复发布之间互相污染。
- **SESSION_EXPIRED**：脚本返回 `ok=false, error=SESSION_EXPIRED`（exit 2）时，**跳过该平台**本轮取数，记入 `EXPIRED_PLATFORMS`，Step 5 统一汇报，由用户白天重新登录。**凌晨不唤醒用户、不扫码登录、不私拉会话**（见约束 4/5）。
- **xhs 风控显著高于其他平台**：xhs 任何登录失效迹象 → 立刻整段跳过 xhs，不尝试任何恢复。取数走 `xhs-engagement`（creator 后台方案，复用 `xhs-browse` session），**严禁** CDP 注入 cookie / `cookies import` 造会话。
- **⛔ 取数失败时必须原样报告脚本 stderr + exit code，禁止自行归因**：脚本的 stderr 是排查的唯一可靠依据。Agent 不得根据 DB 字段（如 `publish_url` 是否为空）脑补错误原因、不得改写/概括 stderr 成自己的话。例：`wx-mp-engagement fetch` exit 1 stderr=`error: 发表记录页未找到标题匹配的 row id=3`，就报这个原文，不要脑补成 "publish_url 无效"。错误归因错误会误导排查方向。

---

#### Step 3: content-calibrator DNA 表现评估（按量触发）

数据采集每天跑，但 DNA 评估**按量触发**——每个（平台, DNA）的成熟待评估记录（发布 ≥3 天 且 `perf_evaluated=0`）累积 **≥5 条**才评估一轮。先跑廉价阈值检查（各启用平台各一次）：

```bash
content-calibrator eval --platform <platform> --check
```

返回 JSON：`{dnas: [{dna_id, pending, triggered}]}`
- 全部 `triggered=false` → 本轮评估跳过，不消耗后续 token
- 有 `triggered=true` 的 DNA → 进入 Step 3a

**对于douyin/wx_mp/wx_channel/xhs平台** → 走该平台专家包内的 review workflow

> 触发的 DNA 属于哪个平台，就按该平台专家包的 review workflow 执行完整复盘（聚合、平台归因、写报告、标记全在 workflow 内；**workflow 不取数**——本轮数据已在 Step 2 采集就位）：

> - **wx_mp** → expert-wx-mp 的 Review Workflow（`skills/expert-wx-mp/workflows/review.md`）
> - **douyin** → expert-douyin 的 Review Workflow（`skills/expert-douyin/workflows/review.md`）

**对于其他平台** → 尚未匹配DNA系统，直接跳过此步

**Agent 不得自动更新 DNA**——评估建议经 Step 5 上报，用户逐条确认后走对应平台专家包的 style-dna workflow 回写。

---

#### Step 4: 用户咨询回复

> 现阶段暂时跳过

巡检如下平台：，针对项目咨询类的留言、回复、私信进行简短回复,如:

```
项目那里下载?
怎么用?
代码仓在哪里?
支持 xxx 功能吗?
...
```

---

#### Step 5: 汇总执行情况报告用户

汇总执行情况，反馈用户。报告内容：

1. 各平台数据更新情况（成功/跳过/失败数量）
2. **取数端登录态失效列表**（如有）：
   > ⚠️ 以下**取数端**登录态已失效，数据未能更新。请白天通知小贝重新登录：
   > - douyin（抖音）
   > - xhs-browse（小红书浏览端）
   > - wechat-channel（微信视频号)

3. DNA 表现评估摘要（如有）：列出本轮评估的 DNA（平台 / dna-id / 覆盖篇数）+ 整体判定（改善 / 平稳 / 下滑）+ 关键归因；无触发 DNA 时写「无 DNA 达到评估阈值」并附各 DNA 待评估计数。
4. **DNA 优化建议待确认（如有）**：列出评估报告中的逐条建议（建议内容 + 目标维度/template 部分 + 证据篇目）。**Agent 不得自动更新 DNA**。用户白天逐条确认后，指示走对应平台专家包的 style-dna workflow 回写 DNA。
5. 用户咨询回复摘要。

发送后本次定时任务结束。
