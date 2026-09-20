---
name: douyin-video-publish
description: 通过浏览器自动化发布视频到抖音创作者中心。纯浏览器操作方案。
---

# douyin-video-publish — 工具说明

> 本文是 `expert-douyin` 专家包内的工具说明书，不独立出现在技能列表中。由相关 Workflow 指引调用。

通过 **camoufox-cli** 持久化 session `douyin`（一个且只有一个持久化 session，fail-first 队列：同 session 已有命令在跑时新命令直接 fail）在抖音创作者中心发布视频。

**输入**：本地视频文件（mp4 / mov，时长 ≤ 15 分钟，建议 < 100MB）、标题（≤ 30 字）、描述文案（含话题标签）。
**输出**：发布结果 + 作品链接（`https://www.douyin.com/video/<aweme_id>`）。

> 纯浏览器操作方案：登录态 + 指纹冻结在持久化 session 的磁盘 profile 里。**严禁** `cookies import` 造登录会话，会触发平台风控。

---

## 发布前置与登录异常（必做）

先读并执行[共用登录流程](../_shared/publish-login.md)：`douyin-video-publish open-page` → agent 检查创作者页面登录态 → 已登录才执行 `run`。首次登录、登录弹窗、运行中 exit 2，均按该流程有头登录并交 login-manager 导出验证。

`open-page` 成功不代表已登录；脚本的 `_check_logged_in` 不做自动判断。已点击发布后的任何异常先核实管理页，不因重登直接重发。

---

## 使用方式

### 一键全流程

```bash
douyin-video-publish run \
  --video /path/to/video.mp4 \
  --title "视频标题" \
  --caption "视频描述 #话题1 #话题2"
```

`run` 内部串：upload → fill → publish → get-link。

### 分步调用（agent 按需）

```bash
# 1. 上传视频（返回 session 名，后续步骤用）
douyin-video-publish upload --video video.mp4

# 2. 填标题/描述 + 自主声明
#    fill 命令内部自动完成：填标题 -> 填简介 -> 选自主声明"内容由AI生成" -> 点"确定"按钮
#    自主声明下拉不存在时不阻断（部分账号/页面无此选项）
douyin-video-publish fill --session <s> --title "标题" --caption "描述"

# 3. 点发布（返回发布起始时刻，供 get-link 锁定本次作品）
douyin-video-publish publish --session <s>

# 4. 取视频链接
douyin-video-publish get-link --session <s>
```

### 行为说明

- `run` 在 close session 之前就拿到作品链接；`get-link` 锁定本次发布的作品（按发布时间窗口筛最新），链接不可得时按 exit 3 处理。
- `upload` 会自动清掉「上次未发布的视频」草稿恢复框，给新发布一个干净上传页；旧草稿在场时新视频上传/发布会被带偏。
- `fill` 内置自主声明"内容由AI生成"选择与确认步骤；声明下拉不存在时不阻断。
- **aweme_id 未捕获即 `exit 3`，不再误报发布成功。** 排查材料在 `/tmp/dy-publish-debug-<ts>.json`。

---

## 创作者中心 URL

上传页：`https://creator.douyin.com/creator-micro/content/upload?enter_from=dou_web`

视频管理页：`https://creator.douyin.com/creator-micro/content/manage`（取链接用）

---

## 必做约束

- **用完即 close 持久化 session `douyin`**——登录态 + 指纹冻结在磁盘 profile，不留进程占内存；下次发布 `--session douyin --persistent` 重起无头即恢复。只在 session 卡死时 `camoufox-cli --session douyin --json close` teardown。
- 同 session 已有命令在跑时，新命令 fail-first（返回 `session douyin 正忙,请等待当前操作完成后再试`）——读到这条文本就等当前操作完成再重试，不要盲试。
- **严禁 `cookies import`**：不开临时 session 再 import cookie，会触发平台风控。执行过程中任何时候发现登录态已失效，走 `login-manager` 有头重登流。
- 限频：单抖音号每 24h ≤ 5 条发布；触发风控立即降级，30 分钟内不重试。

### Exit codes

| code | 含义 | 调用方动作 |
|------|------|-----------|
| `0` | 发布成功，aweme_id 已捕获 | 继续发布后的记录流程 |
| `1` | 参数错 / crash / DOM 改版（按钮/input 未找到）/ 上传转码超时 | 排查后重试 |
| `2` | 未登录或登录态失效 | 走 `login-manager --platform douyin` 有头重登后重试 |
| `3` | 发布流程走完但未捕获到 aweme_id——发布可能未真正成功 | **人工到管理页核实是否真有新作品**；把 `/tmp/dy-publish-debug-*.json` 回传给研发定位真实发布 API |

---

## Pitfalls

### pitfall: douyin_login_required_on_creator_center

- **触发**：访问 `creator.douyin.com` 未登录态
- **症状**：页面跳到 `creator.douyin.com/login` 或出现登录弹窗
- **workaround**：agent 根据页面或 exit 2 判断后，按共用登录流程处理；不要依赖脚本自动识别登录弹窗。

### pitfall: real_name_auth_required

- **触发**：未实名认证的账号
- **症状**：创作者中心提示"请先完成实名认证"才能发布
- **workaround**：用户自己走实名认证流程（脚本帮不上）

### pitfall: video_too_long_or_wrong_format

- **触发**：上传非 mp4 / mov 格式，或视频时长超限
- **症状**：上传后转码失败 / 客户端拒收
- **workaround**：转 mp4 + 检查时长（抖音支持最长 15 分钟）

### pitfall: dom_changes_creator_center

- **触发**：抖音创作者中心前端改版
- **症状**：selector 找不到（input / button 位置变化）
- **workaround**：部署后真机验证更新 selector

### pitfall: upload_transcode_timeout

- **触发**：视频上传后转码超时（大文件 / 网络波动）
- **症状**：轮询标题表单超时，脚本报 `视频上传/转码超时（标题表单未出现）`
- **workaround**：检查视频大小（建议 < 100MB）；超时后截图排查是 DOM 改版还是转码慢；确认 DOM 已渲染后可用分步命令（`fill` / `publish`）手动继续

### pitfall: ai_declaration_confirm

- **触发**：选完自主声明"内容由AI生成"后未点"确定"按钮
- **症状**：声明弹窗卡住，发布按钮被遮挡，无法点发布
- **workaround**：`fill` 命令已内置点"确定"步骤；分步手动操作时选完声明后必须点"确定"

### pitfall: rate_limit_after_burst_publish

- **触发**：短时间内连续发布多条
- **症状**：平台风控 / 上传被拒 / 提示"操作过于频繁"
- **workaround**：每天 ≤ 5 条；触发后 30 分钟内不重试
