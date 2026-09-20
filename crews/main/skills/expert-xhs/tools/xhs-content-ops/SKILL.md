---
name: xhs-content-ops
description: 下载小红书图文笔记（正文 / 图片 / 作者 / 互动数据）。输入笔记 URL 或 note-id + xsec_token，输出 JSON + 本地文件。
---

# xhs-content-ops — 工具说明

> 本文是 `expert-xhs` 专家包内的工具说明书，不独立出现在技能列表中。由相关 Workflow 指引调用。

**用途**：按 URL 或 note-id 下载单篇小红书图文笔记的正文、图片、作者与互动数据（点赞/收藏/评论/分享），供对标分析、DNA 采样、仿写参考使用。

**输入**：笔记 URL（`xhslink.com` / `xhslink.cn` 短链或 `xiaohongshu.com/explore/...` 完整链接），或 `note-id` + `xsec-token`；外加输出目录。
**输出**：stdout JSON（正文 / 图片列表 / 作者 / stats）+ 图片落盘到输出目录。

**边界**：只处理图文笔记。视频笔记（`noteType: "video"`）返回 `VIDEO_NOTE` 错误，转 `viral-chaser` 处理。

---

## 小红书 URL 格式参考

| 页面 | URL |
|------|-----|
| 搜索结果 | `https://www.xiaohongshu.com/search_result?keyword=关键词` |
| 笔记详情 | `https://www.xiaohongshu.com/explore/{feed_id}?xsec_token={token}&xsec_source=pc_feed` |
| 用户主页 | `https://www.xiaohongshu.com/user/profile/{user_id}` |

从搜索结果或页面链接里提取 `note_id` 与 `xsec_token`：`explore/{feed_id}?xsec_token={token}`，feed_id 即 note_id。

---

## 使用方式

通过 PATH 调用 wrapper：`xhs-content-ops <参数>`，无需手动拼接 node 命令或脚本路径。

```bash
# 推荐：直接传 URL（支持 xhslink.com / xhslink.cn 短链和完整 explore 链接，脚本自动解析 note_id + xsec_token）
xhs-content-ops \
  --url <url> \
  --output-dir <output_dir>

# 或：已拿到 note-id 时（必须同时传 xsec_token，否则 HTML 路线拿到空页）
xhs-content-ops \
  --note-id <note_id> \
  --xsec-token <token> \
  --xsec-source <source> \
  --output-dir <output_dir>
```

**参数：**

| 参数 | 必填 | 说明 |
|------|------|------|
| `--url` | 二选一 | 笔记 URL（`xhslink.com` / `xhslink.cn` 短链或 `xiaohongshu.com/explore/...` 完整链接），脚本自动解析 note_id + xsec_token |
| `--note-id` | 二选一 | 小红书笔记 ID（与 `--url` 二选一） |
| `--xsec-token` | `--note-id` 时必填 | xsec_token（用 `--note-id` 时必传，否则 HTML 路线拿空页；用 `--url` 时脚本自动提取） |
| `--xsec-source` | 否 | xsec_source，默认 `pc_feed` |
| `--output-dir` | 是 | 输出目录，**必须工作区相对路径**（如 `xhs/ref/<dna-id>/<sample-id>/` 或 `campaign_assets/<slug>/`），图片和正文保存到此 |

> **⚠️ `--output-dir` 必须用工作区相对路径，不要用 `/tmp`**。后续要用 image 工具读取下载的图片做视觉分析，而 image 工具只能读允许目录（工作区）下的文件，`/tmp` 下的图片会被拒绝（`Local media path is not under an allowed directory`），导致整轮分析白跑。

**输出：** JSON 到 stdout

```json
{
  "ok": true,
  "noteId": "xxx",
  "noteType": "normal",
  "title": "笔记标题",
  "desc": "正文内容",
  "author": "作者昵称",
  "stats": { "likeCount": 100, "collectCount": 50, "commentCount": 20, "shareCount": 10 },
  "images": ["output_dir/img_00.jpg", "output_dir/img_01.jpg"],
  "coverUrl": "https://...",
  "tags": ["话题1", "话题2"]
}
```

---

## 技术路线

- 脚本走**无 cookie SSR HTML 路线**（GET 笔记详情页 HTML 解析 og:meta + `__INITIAL_STATE__`，不走 feed API / relay 签名）；带 xsec_token 的公开笔记无需登录态。
- 无 cookie 抓不到（滑块 / 空页）时才用本机 `xhs-browse` cookie + 同指纹 UA 回退一次（同时读 `~/.openclaw/logins/xhs-browse.json` + `xhs-browse.ua.json`，同一指纹下的 cookie 才不会被风控错配）。
- cookie 回退仍失败 → `exit 2`，走 `login-manager` 重登 `xhs-browse` 后重试。
- 脚本不依赖 relay 签名 / OFB_KEY（HTML 路线无需签名）。

---

## 注意事项

- **控制频率**：批量下载时间隔 5-10 秒，串行执行，不并发。note 详情页连读会触发**速度型软风控**（页面被换成 `website-login/error?error_code=300017/300031` 或「安全限制」文案）——脚本会 cooldown 后单次重试，但根源靠调用方控制节奏，被挡（exit 3）时应显著拉大间隔或暂停。
- **仅处理图文笔记**：遇到视频笔记（返回 `VIDEO_NOTE`），提示转 `viral-chaser`。
- 复合流程（搜索 → 筛选 → 批量下载 → 分析）中每一步都应向用户报告进度。

## 失败处理

| 情况 | 处理 |
|------|------|
| `exit 1` + `NO_XSEC_TOKEN` | 缺 xsec_token；从笔记链接里补提后重试 |
| `exit 1` + `NEED_VERIFY` | 触发滑块；停止重试，走重登流程或换时间再试 |
| `exit 2`（cookie 回退也失败） | `login-manager` 重登 `xhs-browse` 后重试一次 |
| `exit 3` + `SECURITY_BLOCK` | 速度型风控软屏蔽（**非登录失效**，勿重登）。脚本内已 cooldown 单次重试仍被挡；调用方降速（拉大间隔）后晚些重试，勿短间隔连读 |
| 笔记无法访问 | 该笔记可能已删除或设为私密，跳过 |
| 视频笔记 | 转 `viral-chaser` |
