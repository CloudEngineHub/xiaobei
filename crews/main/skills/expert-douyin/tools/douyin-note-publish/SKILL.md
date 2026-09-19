---
name: douyin-note-publish
description: 用持久化浏览器发布抖音图文，支持多图、描述话题、精确配乐与图文链接回收。
---

# 图文发布工具

本工具位于 expert-douyin 的 tools 层，由 content-production / editing 调用，不独立注册技能。视频使用 `douyin-video-publish`。

## 输入与输出

- 图片：按传参顺序上传 1–35 张，jpg/jpeg/png/webp/bmp/tif，单张非空且 ≤50MB，建议 3:4 或 4:3。
- 标题：1–20 字；描述（含内联 `#话题`）：≤1000 字。
- `--music`：精确歌曲名；默认搜索，也可加 `--music-category "纯音乐"` 在分类中定位。不传则保留默认原声。重名或无法确认目标歌曲时停止，不猜歌。
- 默认声明 AI 生成；纯实拍且无需 AI 声明时显式传 `--declaration none`。
- 成功返回 `url=https://www.douyin.com/note/<mid>`、`mid`、`content_id`。

## 发布

先 `douyin-note-publish open-page`，用页面头像、用户名或截图确认登录态，再调用：

```bash
douyin-note-publish run --images /path/cover.png /path/page2.png --title "图文标题" --caption "描述 #话题" --music "目标歌曲完整名"
```

未登录时交 `login-manager --platform douyin` 有头重登，之后重新打开上传页。浏览器只复用持久化 session `douyin`，严禁 cookies import。需要有头操作时每次调用都传 `--headed`，直接 camoufox-cli 操作也保持同一模式，避免 daemon 重启。

`run` 内部完成切图文、批量上传、填表并读回校验、选曲并校验、AI 声明、发布、刷新管理页、按标题定位唯一作品、进入图文编辑页取 mid，最后关闭 session。脚本不会通过视频列表首条或置顶视频猜图文链接，也不会在出错后自动重新发布。

## 分步与恢复

可调用 `upload --images ...`、`fill --title ... --caption ... [--music ...]`、`publish`。分步之间中间态保留在同一 session；不要插入其他抖音任务。`publish` 仅表示已跳转管理页，必须接 `get-note-link --title "完整标题"`，拿到链接才记录成功。取链会进入编辑页，只读取 URL，不保存修改。

`get-note-link` 完成后自动关闭 session；分步中途放弃时手动 `camoufox-cli --session douyin --persistent --json close`（有头时加 `--headed`）。

- exit 0：当前步骤成功；完整发布以 `run` / `get-note-link` 返回 note URL 为准。
- exit 1：参数、DOM 或浏览器错误；若已点击发布，先核实管理页，不能直接重跑 run。
- exit 2：明确登录失效，交 login-manager；heartbeat 中只记录并跳过。
- exit 3：发布结果或链接待核实；查看 `/tmp/dy-note-debug-*.json`，仅补取链接，不自动重发。同标题有多个候选时人工核实。

图文和视频共享任务锁与 session，忙时 fail-first，等当前任务结束再操作。单账号视频与图文合计每 24h ≤5 条，触发风控 30 分钟内不重试。审核中也可记录已确认的 note 链接；发布后以 `published-track record --platform douyin --content-type post` 入库，heartbeat 统一取数。
