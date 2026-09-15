---
name: twitter-post
description: 通过 camoufox-cli 浏览器自动化发布推文到 Twitter/X。支持文本、图片、视频、串推、引用、回复、长文（Premium/Blue 25,000 字符）。
---

# twitter-post — 工具说明

> 本文是 `expert-twitter` 专家包内的工具说明书，不独立出现在技能列表中。由相关 Workflow 指引调用。

通过 **camoufox-cli** 持久化 session `twitter` 在 Twitter/X 上发布推文（文本 / 图片 / 视频 / 串推 / 引用 / 回复 / 长文）。

**输入**：推文正文（标准账号 ≤ 280 字符，Premium/Blue ≤ 25,000 字符）、可选媒体文件（图片 ≤ 4 张 / 视频 ≤ 512MB 且 ≤ 2m20s / GIF ≤ 15MB）；引用 / 回复场景另需源推 URL。
**输出**：发布结果 + 推文链接 + 即时 stats（view / reply / retweet / like / bookmark）。

> 纯浏览器操作方案：登录态 + 指纹冻结在持久化 session 的磁盘 profile 里。**严禁** `cookies import` 造登录会话，会触发平台风控。本工具与 `twitter-interact` **共用同一个 session 名 `twitter`**，靠 session 名字符串约定共享同一 profile 目录与登录态——一方登录后另一方不需重登。登录态只在 session profile 里闭环，**不导出 cookie/UA 落中央存储**（不调用 `cookies export` / `identity export`）。

---

## 浏览器方案（重要）

**优先 camoufox-cli，且除了登录外，其他都可以默认的无头方式进行**

> 下面 workflow 步骤（Navigate / Click / snapshot eval / upload）默认用 camoufox-cli 执行。若 camoufox-cli 在 X 上持续触发风控，等 60s 后开新 session 重试；仍触发则报告用户该平台当日风控未解，择日再试。

### 探活与登录（本工具自管，不走 login-manager）

探活方式：开 session open 平台首页 + snapshot 看是否跳登录页。

```bash
# 探活（默认无头模式）
camoufox-cli --session twitter --persistent --json open "https://x.com/"
sleep 3
camoufox-cli --session twitter --json snapshot
# snapshot 看页面是否跳到登录页 / 出现登录按钮 / 推文是否正常可见
# → 没跳登录页、内容正常 = 登录态有效，探活完即 close session（登录态在磁盘 profile，后续操作按需重起无头复用）
# → 跳到登录页 / 出现登录按钮 = 登录态失效，走重登
```

重登流程（失效时）——登录流程按 `browser-guide` skill 走有头手动登录（手机号+验证码 / Twitter APP 扫码），登录完成后**close session**——登录态落磁盘 profile，不留进程占内存。发布操作时用 `--session twitter --persistent` 重起无头即恢复，用完再 close。只在 session 卡死时由调用方手动 `camoufox-cli --session twitter --json close` teardown。

```bash
# X 登录风控对无头 + QR 识别严格，有头人工登录最稳
camoufox-cli --session twitter --persistent --headed --json open "https://x.com/login"
# 告知用户「**Twitter/X** 浏览器已打开，请在窗口里手动完成登录（账号密码 / 手机 APP 扫码），完成后告诉我」
# 等用户回复后 snapshot 验登录态就位
# 登录就位后 close session——登录态落磁盘 profile，按需重起无头复用
```

---

## 通用约束

- 文件上传用 forked camoufox-cli 的 `upload` 命令（`camoufox-cli --session <s> --persistent --json upload <ref> <file>`，底层 Playwright `setInputFiles`，无需 DataTransfer hack）
- 正文输入：**CJK（中文/日文/韩文）内容禁用 `type` 命令**——camoufox-cli `type` 逐字符按键流与 X 编辑器（Draft.js）异步处理存在竞态，中文实测丢字+乱序（2026-09-13 事故，首字被挪到结尾、中段整段消失，含分段 type+停顿仍错乱）。CJK 正文一律走下方「CJK 正文输入与校验闸门」的 eval + `document.execCommand("insertText")` 整段插入；纯 ASCII 短文本仍可用 `type`。**不要用 `fill()`**

### CJK 正文输入与校验闸门

含中文 / 日文 / 韩文的正文必须走本节的 insertText 方案 + 校验闸门；纯 ASCII 短文本可用 `type`，但**发布前校验闸门**与**发布后终验**对**所有正文**强制执行。

**1. 清空回填草稿（open compose 后必做）**：X 重新打开 compose 页可能回填上次草稿，直接 insertText 会叠成两份：

```bash
camoufox-cli --session twitter --json eval '(function(){var el=document.querySelector("[data-testid=tweetTextarea_0]");if(!el){return "NO_BOX";}el.focus();var s=document.execCommand("selectAll",false);var d=document.execCommand("delete",false);return (s&&d)?"CLEARED":"CLEAR_FAILED";})()'
```

**2. 插入正文**（CJK 用 insertText 整段插入；正文含单引号或反斜杠时先转义，避免破坏命令引号）：

```bash
camoufox-cli --session twitter --json eval '(function(){var el=document.querySelector("[data-testid=tweetTextarea_0]");if(!el){return "NO_BOX";}el.focus();var ok=document.execCommand("insertText",false,"<正文>");return ok?"INSERTED":"EXEC_FAILED";})()'
```

**3. 发布前校验闸门（强制——点击 Post / Reply 之前必须执行，非 MATCH 一律不发布）**：

```bash
camoufox-cli --session twitter --json eval '(function(){var el=document.querySelector("[data-testid=tweetTextarea_0]");var t=el?el.innerText:"NO_BOX";var target="<正文>";return t===target?"MATCH":"MISMATCH:"+t;})()'
```

- **选择器必须精确匹配 `[data-testid=tweetTextarea_0]`**——`[data-testid^=tweetTextarea]` 前缀匹配会同时命中 `tweetTextarea_0_label`（占位符层），读到占位符文本、误报 MISMATCH。
- **插入与校验必须分两次 eval 调用（间隔 ≥1s）**——写在同一 eval 里同步执行时，React 未及重渲染，innerText 会混入「What's happening?」占位符（占位符假警报）。MISMATCH 先看是否混有占位符再定性。
- **emoji 是 `<img>` 不是丢字**：✅ 等 emoji 在 DOM 里渲染为 `<img>`，`innerText` 提取时只显示周围空格——校验按「剔除 img 节点后的文本」比对。

**4. 发布后终验（强化，所有发布流程共用）**：点 Post 后导航 profile 页，读最新推文 `[data-testid=tweetText]` innerText 与 status 链接，与目标正文比对（剔除 emoji img 因素）后才算发布成功；不符立即走删除流程（More → Delete → confirmationSheetConfirm）。

### 字符计数规则（X 平台特殊）

- **URL 永远算 23 字符**（不论实际长度）— 在算 limit 时要预先扣除
- **Emoji 算 2 字符** / 个
- 标准 280 字符限制（普通账号）
- Premium/Blue 25,000 字符（"long post"，URL bar 显示"Post all"而非"Post"）

### Anti-automation limit

- 单条帖 ≥ 30 min 间隔（**不是** 15 min——30 min 是平台风险阈值）
- 单日 ≤ 50 帖（含 reply / quote / retweet / 长帖）
- 单周 ≤ 200 帖
- 触发风控后 24h 静默
- 频次跟踪：写到 Workspace 根平台运营文件夹 `twitter/twitter-frequency.json`（每次 post 后 append，不存在则初始化）

---

## Post Types 决策表

| 场景 | 用哪个 Workflow | 入口 URL |
|------|---------------|----------|
| 新推纯文/图/视频 | Workflow: Post Plain Text / Image / Video | `https://x.com/compose/post` |
| 推连续串 | Workflow: Thread | `https://x.com/compose/post` |
| 引用某推+评论 | **Workflow: Quote Tweet** | `https://x.com/compose/post`（从其他推页 quote）|
| 回复某推 | **Workflow: Reply to Tweet** | `https://x.com/<user>/status/<id>`（回复按钮）|
| 长文（>280 字符）| **Workflow: Long Post** | `https://x.com/compose/post`（检测 Premium 蓝标）|
| 标准帖发后取 stats | Workflow: Post Parse Stats | 任意已发推 |

---

## Workflow: Post Plain Text

```
1. Navigate to https://x.com/compose/post
2. Wait for the compose box to load
3. 按「通用约束 → CJK 正文输入与校验闸门」输入正文（CJK 走 insertText；纯 ASCII 可 type）
   - Plain text only (no Markdown)
   - Max 280 characters for standard accounts
4. **发布前校验闸门**：eval 校验正文返回 MATCH（通用约束 step 3；非 MATCH 一律不发布）
5. Verify character count — trim if over limit
6. **立即点击 "Post" 按钮——不要等待用户确认！**
7. Wait for success confirmation (URL changes or "Your post was sent" toast)
8. **发布后终验**（通用约束 step 4）：导航 profile 页比对最新推文正文，MATCH 才算发布成功；不符走删除重发
9. Extract and report the post URL
10. **Parse stats**：
   - snapshot eval: `JSON.stringify({
       retweet: document.querySelector('[data-testid="retweet"]')?.innerText,
       like: document.querySelector('[data-testid="like"]')?.innerText,
       reply: document.querySelector('[data-testid="reply"]')?.innerText,
       view: document.querySelector('[href*="/analytics"]')?.innerText,
       permalink: window.location.href
     })`
11. Update frequency tracker
```

---

## Workflow: Post with Image

```
1. Navigate to https://x.com/compose/post
2. Wait for the compose box to load
3. Upload the image file using camoufox-cli upload（见下方选择器说明）
4. Wait for image upload to complete (thumbnail / "Media" group appears)
5. 按「通用约束 → CJK 正文输入与校验闸门」输入 caption（CJK 走 insertText）；**发布前校验闸门**：eval 校验 MATCH 才点 Post（通用约束 step 3）
   - Plain text only (no Markdown)
   - Max 280 characters for standard accounts
6. **立即点击 "Post" 按钮——不要等待用户确认！**
7. Wait for confirmation and report the post URL
8. Parse stats (same as plain text)
9. Update frequency tracker
```

### 文件上传选择器（重要）

X compose 页面有**两个** `<input type="file" data-testid="fileInput">` 元素（可见 + 隐藏），直接用 `input[type=file]` 或 `[data-testid=fileInput]` 会触发 Playwright **strict mode violation: resolved to 2 elements**。

**必须用 `>> nth=0` 消歧**：

```bash
camoufox-cli --session twitter --persistent --json upload "[data-testid=fileInput] >> nth=0" /path/to/image.jpg
```

> forked cli 的 `upload` 命令底层走 Playwright `setInputFiles`，穿透 shadow DOM，无需 `locator.drop()` hack。

---

## Workflow: Post with Video

```
1. Navigate to https://x.com/compose/post
2. Click the media icon
3. Upload the video file (MP4 recommended, max 512MB, max 2min 20sec)
4. Wait for video processing — this can take 30–120 seconds or more for larger files. Look for the thumbnail preview to confirm completion.
5. 按「通用约束 → CJK 正文输入与校验闸门」输入 caption（CJK 走 insertText）；**发布前校验闸门**：eval 校验 MATCH 才点 Post（通用约束 step 3）
   - Plain text only (no Markdown)
   - Max 280 characters for standard accounts
6. **立即点击 "Post" 按钮——不要等待用户确认！**
7. Wait for upload confirmation and report the post URL
8. Parse stats (same as plain text)
9. Update frequency tracker
```

---

## Workflow: Thread (multiple posts)

```
1. Navigate to https://x.com/compose/post
2. 按「通用约束 → CJK 正文输入与校验闸门」输入第一条推文（CJK 走 insertText）
   - Plain text only (no Markdown)
   - Max 280 characters for standard accounts
3. Click the "+" icon to add another tweet to the thread
4. 同上输入第二条推文（CJK 走 insertText），**发布前校验闸门**：每条 eval 校验 MATCH 才 Post all（通用约束 step 3）
   - Plain text only (no Markdown)
   - Max 280 characters for standard accounts
5. Repeat for each additional tweet
6. Click "Post all" to publish the full thread
7. Parse stats for the **last** tweet (representative)
8. Update frequency tracker (count = number of tweets in thread)
```

---

## Workflow: Quote Tweet

**场景**：引用别人的推 + 自己的评论（BD / 互动 / 营销场景强）

```
1. Navigate to source tweet URL（如 https://x.com/username/status/1234567890）
2. Click "Repost" icon → 选择 "Quote"（不是 "Repost"）
   - ⚠️ 区分 "Repost"（纯转推，无评论）vs "Quote"（引用+评论）
3. Compose box 打开，**已自动填入引用卡片**
4. Click into text area below the quoted card
5. 按「通用约束 → CJK 正文输入与校验闸门」输入评论（CJK 走 insertText）；**发布前校验闸门**：eval 校验 MATCH（通用约束 step 3）
6. Verify character count
7. **立即点击 "Post" 按钮**
8. Wait for confirmation, report post URL
9. Parse stats (same as plain text)
10. Update frequency tracker
```

**Pitfall**：
- ❌ 选 "Repost" 而不是 "Quote" → 推出去没评论，BD 场景失去意义
- ❌ 评论超过 280 字符 → 按钮变灰，**不**自动转 Long post
- ❌ 评论里直接放 raw URL（占 23 字符）→ 实际可发字符更少

---

## Workflow: Reply to Tweet

```
1. Navigate to source tweet URL（如 https://x.com/username/status/1234567890）
2. Click "Reply" icon（不是 reply 文本框）
3. Compose box 打开，**自动显示 reply context**
4. 按「通用约束 → CJK 正文输入与校验闸门」输入回复（CJK 走 insertText）；**发布前校验闸门**：eval 校验 MATCH（通用约束 step 3）
5. Verify character count
6. **立即点击 "Reply" 按钮**（不是 "Post"）
7. Wait for confirmation, report reply URL
8. Parse stats (replies can also get view counts)
9. Update frequency tracker
```

**Pitfall**：
- ❌ 选 "Reply" 时落入 quote 模式（X 旧 UI 行为）→ 不会加 reply 关系
- ❌ 串太长（> 280）→ 按钮变灰
- ❌ 频率过高 → 风控（见 Anti-automation limit）

---

## Workflow: Long Post

**前置**：用户是 **Premium / Blue** 订阅（X 蓝标）。普通账号本工作流**不适用**。

**检测 Premium**：
```
snapshot eval: document.querySelector('[data-testid="icon-verified"]') !== null
// 或 UI 中是否有 "Premium" 字样
```

```
1. Navigate to https://x.com/compose/post
2. Wait for compose box to load
3. 按「通用约束 → CJK 正文输入与校验闸门」输入内容（CJK 走 insertText）；**发布前校验闸门**：eval 校验 MATCH 才 Post all（通用约束 step 3）
4. **注意**：URL 仍 23 字符，Emoji 仍 2 字符
5. 按钮文字从 "Post" 变成 "**Post all**"（X 长帖是 1 个"post all"动作，但内容被服务端分页）
6. Click "Post all"
7. Wait for confirmation (URL changes)
8. Extract permalink (实际是 thread 形式：tweet + 续贴)
9. Parse stats for **first** tweet
10. Update frequency tracker (count = 1，long post 算 1 次)
```

**Pitfall**：
- ❌ 普通账号硬塞 25K → 按钮变灰 / 截断
- ❌ 不验 Premium 状态 → 普通账号调本工作流失败率高
- ⚠️ Long post 实际上服务端分页（thread-like），permalink 拿的是 first tweet

---

## Workflow: Post Parse Stats

> post 后立即拿 stats（view / reply / retweet / like），用于复盘。

```
1. After post success (any workflow ending with "Wait for confirmation")
2. 已在推文页面，URL = https://x.com/<user>/status/<id>
3. Wait 3-5s for X to populate stats
4. snapshot eval:
   const stats = JSON.stringify({
     retweet: document.querySelector('[data-testid="retweet"]')?.innerText,
     like: document.querySelector('[data-testid="like"]')?.innerText,
     reply: document.querySelector('[data-testid="reply"]')?.innerText,
     view: document.querySelector('a[href*="/analytics"]')?.innerText,
     bookmark: document.querySelector('[data-testid="bookmark"]')?.innerText,
     permalink: window.location.href
   })
5. Output: { ok, permalink, stats: { retweet, like, reply, view, bookmark } }
```

**注意**：
- view 数 Premium 账号可见；普通账号无
- 30 min 后 stats 才稳定（X 算法）
- 嵌入 evaluate 走 `document.querySelector('selector')?.innerText` —— selector 可能因 X UI 改版变，部署后真机验证

---

## Frequency Tracker

```python
# <Workspace 根>/twitter/twitter-frequency.json
{
  "last_post_at": "2026-07-05T09:30:00+08:00",
  "today_count": 5,
  "week_count": 23,
  "platform": "twitter"
}
```

**每次 post 成功后 append**：
1. 读 JSON（不存在则初始化 0/0）
2. 距 last_post_at < 30 min → **警告用户** + 询问是否继续（仍可继续，但 mark as high-risk）
3. 距 last_post_at < 5 min → **强制建议延后**（强烈风控风险）
4. today_count += N（thread 算 N 条）
5. today_count > 50 → **拒绝 + 告知用户明早再发**
6. week_count > 200 → 同上
7. 写入 JSON

---

## Content Limits

| Type | Limit |
|------|-------|
| Text (standard) | 280 characters (URL=23, Emoji=2) |
| Text (Premium/Blue) | 25,000 characters (long post) |
| Images | Up to 4 per post |
| Video | Max 512 MB, max 2m 20s |
| GIF | Max 15 MB |
| Reply | 280 characters |
| Quote Tweet | 280 characters (in comment) |
| Thread | Unlimited tweets, each ≤ 280 |

---

## Error Handling

| Situation | Action |
|-----------|--------|
| Login page appears | Session expired — inform user to re-login via browser |
| Character limit exceeded (280) | Trim content or use thread format |
| Character limit exceeded (Premium 25K) | Trim or use thread |
| Media upload fails | Retry once; check file format and size |
| Upload strict mode violation (2 elements) | **用 `[data-testid=fileInput] >> nth=0` 消歧**（见 Workflow: Post with Image） |
| "Something went wrong, but don't fret" after Post | **先过发布前校验闸门判因**：MISMATCH → 正文损坏/丢失，走清草稿 → insertText → MATCH 后重发；MATCH → X 服务端瞬时错误（实测与字数无关，第 3 次同内容重发成功），reload compose 页 → 清空回填草稿 → insertText → 复验 → re-click Post，**最多 3 次，每次重试必须重走校验闸门**。3 次仍失败才报告用户。仅当校验确认字数超限（URL=23 / emoji=2 计数偏差）时才精简正文。 |
| 重新 open compose 回填上次草稿 | 插入前先清空（focus → `execCommand("selectAll")` → `execCommand("delete")`），否则直接 insertText 会叠成两份 |
| 校验 innerText 混入 "What's happening?" 占位符 | 插入与校验必须**分两次 eval 调用（间隔 ≥1s）**——同次调用 React 未及重渲染会混入占位符；MISMATCH 先看是否混有占位符再定性 |
| 校验判读 emoji 缺失（✅ 变空格） | emoji 在 DOM 渲染为 `<img>`，innerText 只显示周围空格——**不是丢字**；终验以 profile 页 `[data-testid=tweetText]` innerText + 时间线 `img` 节点共同判读 |
| Rate limit error | **Wait 30 min minimum** (not 15) + check frequency tracker |
| Post button greyed out | Content is empty or over limit — check before clicking |
| Frequency tracker warns high-risk | Ask user: continue or defer to tomorrow? |
| Quote 按钮选成 Repost | Undo（出现"Reposted"提示 → click "Undo" → 重新选 Quote）|
| Reply 按钮消失 | Refresh page（X UI 偶发 bug）|
| Long post 按钮文字不是 "Post all" | 用户不是 Premium → 切换到 standard 280 流程 |

---

## Notes

- Do NOT mention internal tool names or errors in any post
- All post content must comply with X's terms of service
- If posting on behalf of company: verify the content tone matches the company voice in MEMORY.md
- 抓 stats 仅在 post 成功页有效；不要在 compose 页面（还没有 stats）
- Quote / Reply 都要先**确认是哪种按钮**（X UI 把 "Repost" 和 "Quote" 放一起）
- 频率统计：本工具只采集 stats，不做评分

---

## 参考

- [X Help: Types of Posts](https://help.x.com/en/using-x/types-of-posts) — Reply / Quote / Long post 定义
- [X Algorithm 2026](https://www.teract.ai/resources/twitter-algorithm-2026) — reply weighted 27x like, 30 min 关键窗口
