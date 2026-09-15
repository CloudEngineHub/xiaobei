# 数据复盘 Workflow（wx_channel）

**wx_channel 的所有数据复盘工作都走这个 workflow**——heartbeat 按量触发的 DNA 评估、用户临时发起的“看看数据 / 复盘一下 / 评估这个 DNA”，统一从这里进。复盘一律**根据数据针对 DNA 做**，没有单条复盘；复盘过程调用跨平台技能 `content-calibrator`（评估引擎：触发规则、账号基线归一化、趋势计算、证据聚合、报告结构）

本 workflow 提供引擎没有的东西：**wx_channel 平台的归因方法**（指标语义、互动路径映射、DNA 维度回溯、平台混杂因素）。

## 入口判断

走本 workflow：
- heartbeat 凌晨任务 Step 3：wx_channel 有 DNA 触发评估时
- 用户：“看看数据怎么样” / “最近复盘一下” / “评估一下 dna-X” / “这个 DNA 最近表现如何”

不走本 workflow：
- 对标账号 / 对标视频分析 → `account-benchmark.md`
- 建 / 更新 DNA → `style-dna.md`
- 单条数据疑问（“这条播放怎么低”）→ 不是复盘，agent 直接取数在账号与 DNA 上下文里回答；若发现指向 DNA 层面的系统性问题，引导用户发起本 workflow 的评估

## wx_channel 归因方法（平台特有，引擎不包含）

### 指标语义

| 指标 | 含义与解读 |
|------|-----------|
| plays | 播放数，漏斗第一层结果；社交推荐 + 算法推荐 + 选题时效共同决定 |
| shares | 分享（转发朋友圈/群聊），**视频号最强社交信号**，权重高于点赞；决定能否进入社交热点池破圈 |
| favorites | 收藏，实用价值信号；清单/教程类内容高 |
| likes | 点赞，轻认可 + 好友曝光触发器（好友点赞进朋友推荐流） |
| comments | 评论，互动设计 + 共鸣点决定；评论热度反哺同圈层点击 |

视频号助手作品管理页只给这 5 项行内指标。**完播率、社交推荐占比、观众来源构成**不在抓取范围内，需要用户提供创作者中心截图后才能作为证据；拿不到时相关漏斗层只能从相对趋势推断，并在报告中注明。

### 互动漏斗 → template 语义段 → DNA 维度映射（视频作品）

| 漏斗卡点 | 先怀疑的 template 语义段 | 可回溯的 DNA 维度 |
|---------|--------------------------|------------------|
| 播放低（曝光/推荐不足） | 选题、短标题与视频描述 | topic-angle、title-cover |
| 完播低（需用户提供完播数据） | 内容创意、制作规格、口播文案 | content-idea、production-spec、narration-script |
| 中段流失 | 内容创意、视频形态与制作指向 | content-idea、video-form |
| 分享低 | 选题、内容创意 | topic-angle、content-idea |
| 评论低 | 内容创意（讨论点）、口播文案 | content-idea、narration-script |
| 收藏少 | 内容创意、制作规格 | content-idea、production-spec |
| 关注少 | 账号运营子模块、业务植入与 CTA | account-bio、content-mix-cadence、interaction-cta |
| 转化少（私信/成交） | 业务植入与 CTA、选题、内容创意 | biz-implant、interaction-cta、topic-angle、content-idea |
| 广告感重（分享跳水、负面评论） | 业务植入与 CTA | biz-implant、interaction-cta |

交叉判断：完播高、分享低 → 内容好看但缺社交价值；分享高、完播低 → 短标题 / 视频描述的承诺与内容兑现不足。

### 平台混杂因素（归因前必排）

1. **账号成熟度**：新号数据天然低、老号天然高；跨账号绝对值不可比，只看同账号比值与走向。
2. **社交推荐池波动**：私域活跃度、好友互动基数变化造成整体水位漂移——同账号全部作品同步涨跌 → 平台/私域因素，不是 DNA 因素。
3. **选题热度**：热点选题自带流量；单条突增先查选题是否踩中时效话题。
4. **发布时间与节假日**：工作日 12-13 点、19-21 点与周末上午是经验高流量时段；长假期间观看习惯变化。
5. **长尾效应**：视频号优质内容凭社交裂变可在发布数月后持续获得曝光——老视频延迟起量是平台常态，发布 3-7 天内数据低不能直接判死。

排不掉混杂的写「观察」，不写「结论」。

## 评估流程

### Step 0 - 确定评估对象

```bash
content-calibrator eval --platform wx_channel --check
```

- **heartbeat 路径**：全部 `triggered=false` → 在 Step 5 汇总里报各 DNA 待评估进度（n/5），本 workflow 结束；有 `triggered=true` → 对每个触发 DNA 走 Step 1。
- **用户路径**：用户点名某 DNA → 该 DNA 未达阈值时用 `--dna-id <id> --force`；未点名 → 先看 `--check`，优先评估已触发 DNA，都未触发时问用户是否强制评估某个 DNA。

### Step 1 - 聚合证据

```bash
content-calibrator eval --platform wx_channel                    # 全部触发 DNA
content-calibrator eval --platform wx_channel --dna-id <id>      # 指定 DNA
```

输出逐条绝对值 + 同账号基线比值 + 每指标趋势走向；`baseline_insufficient` 的记录只作绝对观察。

### Step 2 - 归因分析

按上方「wx_channel 归因方法」执行，同时遵守 `content-calibrator` 的共性归因原则（趋势优先 / 证据可追溯 / 先排混杂）：

1. 判定只看比值与走向，绝对值只作上下文。
2. 逐条排除平台混杂因素，特别注意长尾效应——近 3-7 天发布的数据成熟度不足时降级为观察。
3. 回读 `wx_channel/dna/<dna-id>/<dna-id>.dna.md` / `.template.md` 与待评估作品（`source_folder` 内 `brief.md`、`voiceover.md` 或成片说明），把趋势变化落到 template 语义段与 DNA 维度。
4. 分享率异常（过高或过低）时优先核对转发动机设计是否命中，这是视频号区别于其他平台的第一归因点。

### Step 3 - 报告与标记

1. 写评估报告到 `wx_channel/dna/<dna-id>/evals/{YYYY-MM-DD}.eval.md`，结构按 `content-calibrator` 的评估产物要求（整体判定 / 趋势表 / template 归因 / 逐条建议 / 观察区）。
2. 标记覆盖的记录，防下轮重复评估：

```bash
content-calibrator eval --platform wx_channel --mark-evaluated --ids <本轮记录 id，逗号分隔>
```

### Step 4 - 出口

- 向用户呈现：整体判定 + 逐条优化建议（每条注明目标维度/template 部分与证据篇目）。heartbeat 场景在凌晨汇总里上报，**不唤醒用户**。
- 用户逐条确认后，采纳的建议走 `style-dna.md`「表现反馈」转译进 DNA；**Agent 不得自动更新 DNA**。
- 不涉及风格规则的业务动作（选题方向、栏目增减、发布时段调整、私域发动方式）直接给行动项，不进 DNA。

## 执行纪律

- 复盘不取数：数据新鲜度由每日定时采集任务（`wx-channel-engagement fetch-all`）保证；用户临时发起单次 review 时直接基于库内已有数据做。仅当用户明确要求「先更新数据」时，才单独调用 `wx-channel-engagement fetch` / `published-track` 取数后再进入复盘。
- heartbeat isolated 会话中本流程由**主 agent inline 执行**，不 spawn subagent、不 sessions_yield（评估需连续回读多文件，隔离会话本就无上下文污染）。
