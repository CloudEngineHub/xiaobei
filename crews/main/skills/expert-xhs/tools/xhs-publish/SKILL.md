---
name: xhs-publish
description: Publish image-text notes and video notes to Xiaohongshu (小红书) via creator COS upload + web_api v2. Supports image posts (up to 18 images), video posts, topics/hashtags. 
---

# 小红书发布（xhs-publish）— 工具说明

> 本文是 `expert-xhs` 专家包内的工具说明书，不独立出现在技能列表中。由相关 Workflow 指引调用。

**用途**：发布图文 / 视频笔记到小红书。**输入**：标题（≤20 字）、正文（≤1000 字，内联 `#话题`）、图片（≤18 张）或视频文件。**输出**：发布结果 + 笔记链接。

通过 creator 平台 COS 上传 + `/web_api/sns/v2/note` 创建笔记，支持图文和视频。**共享 camoufox profile**（session=xhs-browse），login-manager 管消费者域 www 登录，本工具在其上做创作者 SSO；两套 cookie 分别落 `xhs-browse.json` / `xhs-publish.json`，发布时合并。签名走 relay sign 服务。

上传流程：① 取 COS 上传许可证 `creator.xiaohongshu.com/api/media/v1/upload/web/permit` → ② PUT 文件到 COS（大文件自动分片）→ ③ 创建笔记 `edith.xiaohongshu.com/web_api/sns/v2/note`。

---

## 登录态管理（共享 xhs-browse profile，创作者 cookie 自管）

**两步登录**：发布需同时带消费者域 `web_session` + 创作者域 `galaxy_creator_session_id`。两套由共享 camoufox profile（session=xhs-browse）产出——同一台机器只有一个 profile 涉及小红书平台，避免两个 profile 互踢 web_session 导致频繁重登暴露。

login-manager 管 www 登录（`xhs-browse.json`），本技能在其上做创作者 SSO 导出 `xhs-publish.json`，发布时 `publish_xhs.py` 合并两者。探活走创作者域 `personal_info` **裸 GET**，无需 xhs 签名 / OFB_KEY。

### Step 1 — 发布前探活（批量发布只探活一次）

```bash
xhs-publish check
```

- exit 0 = 有效 → 继续发布
- exit 2 = `SESSION_EXPIRED` → 走 Step 2 重登，再探活一次
- exit 1 = crash → 人工排查

### Step 2 — 重登（exit 2 时触发，两步：先 www 后 creator SSO）

1. **先保活消费者域**（共享 profile 内 web_session 必须存活）：
   ```bash
   login-manager check xhs-browse
   ```
   - exit 0 = www 存活 → 直接进步骤 2
   - exit 2 = www 失效 → `login-manager login xhs-browse` 走有头扫码登录 www（用户交互），完成后导出 `xhs-browse.json` + UA
   - exit 1 = crash → 人工排查

2. **创作者 SSO 导出 + 验证**（www 已登录 → 自动 SSO，无需扫码）：
   ```bash
   xhs-publish login-verify
   ```
   脚本闭环（在共享 session=xhs-browse 上）：自检 web_session → open `creator.xiaohongshu.com/login?source=official` 自动 SSO 重定向 → 轮询创作者 cookie 落盘 → 创作者域 `personal_info` 裸 GET 验过才 commit → 写 `~/.openclaw/logins/xhs-publish.json` + `.ua.json` → close session。SSO 未完成 / 验证不过 exit 2、不重试。

> **同时导入 cookie 和 UA**：xhs 的 `a1`/`websectiga` 等设备指纹 cookie 必须配同一指纹的 UA，否则被风控错配。`publish_xhs.py` 已合并读 `xhs-publish.json`（创作者）+ `xhs-browse.json`（消费者）两套 cookie + 对应 `.ua.json`。

> 确保 `Pillow` 已安装（读图片尺寸）：`pip install Pillow`。

---

## 使用方式

通过 PATH 调用 wrapper：`xhs-publish "<正文>" [附件...]`。

### 图文笔记

```bash
xhs-publish --mode image --title "笔记标题" --body "正文内容 #话题1 #话题2" --images img1.jpg img2.jpg img3.jpg
```

### 视频笔记

```bash
xhs-publish --mode video --title "笔记标题" --body "正文内容" --video video.mp4 --cover cover.jpg
```

#### 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `--mode` | 是 | `image` 或 `video` |
| `--title` | 是 | 笔记标题，最多 20 字 |
| `--body` | 是 | 正文，最多 1000 字；`#话题` 自动提取为标签，**最多 10 个**（硬约束）。脚本会自动把 body 里 `#话题` 重写为 `\uFEFF#话题[话题]#\uFEFF`（小红书 web API 识别内联话题的硬性格式：`[话题]` 和首尾两个 `#` 是固定字面量，前后包不可见字符 `\uFEFF` BOM） |
| `--images` | 图文必填 | 图片路径列表，最多 18 张，jpg/png/webp |
| `--video` | 视频必填 | 视频路径，mp4，建议 9:16 |
| `--cover` | 否 | 封面图；视频模式默认取第一帧 |
| `--topics` | 否 | 额外话题名称 |
| `--private` | 否 | 仅自己可见（默认公开） |

> **⚠️ `--body` 必须传实际文字，不能传文件路径或 `$(cat file)`**：exec sandbox 禁用 `$(...)` 命令替换，`--body post.md` 也会被当字面量字符串。把正文直接硬编码进命令。

> **⚠️ `--body` 换行用真实换行，不要在双引号里写 `\n`**：bash 双引号内的 `\n` 是字面量「反斜杠+n」，发布后正文会全是 `\n` 文本。脚本已兜底把字面量 `\n` 自动归一化为真实换行，但传参仍首选真换行：
>
> ```bash
> # ✅ 多行字符串：引号内直接回车换行
> xhs-publish --mode image --title "标题" --body "第一行
> 第二行" --images img.jpg
>
> # ✅ $'...' 转义：\n 被 bash 解释为真实换行
> xhs-publish --mode image --title "标题" --body $'第一行\n第二行' --images img.jpg
>
> # ❌ 普通双引号里的 \n 是字面量，发布后正文全是 \n 文本
> xhs-publish --mode image --title "标题" --body "第一行\n第二行" --images img.jpg
> ```

成功输出：

```json
{"ok": true, "note_id": "xxx", "url": "https://www.xiaohongshu.com/explore/xxx"}
```

---

## 内容规范

- 标题 ≤ 20 字，正文 ≤ 1000 字
- 图片建议 3:4 竖版，最多 18 张；视频建议 9:16，5s–15min
- AI 生成内容需声明（脚本默认声明）；禁止引流、导流
- hashtag 最多 10 个（超出会被静默丢弃或限流）

---

## 调用顺序

1. 探活：`xhs-publish check`（exit 0 = 有效；批量发布只探活一次）
2. 运行 `xhs-publish ...` 发布
3. 看 stdout JSON：`ok: true` → 成功；`error: AUTH_EXPIRED` → 走 Step 2 重登后重试一次；其他 `error` → 原样转述给用户，不自行归因

---

## 错误处理

| 错误 | 原因 | 处理 |
|------|------|------|
| AUTH_EXPIRED | cookie 失效 | 走 Step 2 重登后重试一次 |
| UPLOAD_FAILED | COS 上传失败 | 检查文件格式/大小，重试一次 |
| TITLE_TOO_LONG | 标题超 20 字 | 截断后重试 |
| BODY_TOO_LONG | 正文超 1000 字 | 精简后重试 |
| RATE_LIMIT | 发布频率限制 | 等 30 分钟后重试 |
