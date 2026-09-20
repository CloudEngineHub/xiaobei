---
name: douyin-note-publish
description: 用持久化浏览器发布抖音图文，支持多图、描述话题、上传后读取推荐音乐并选曲与图文链接回收。
---

# 图文发布工具

本工具位于 expert-douyin 的 tools 层，由 content-production / editing 调用，不独立注册技能。视频使用 `douyin-video-publish`。

## 输入与输出

- 图片：按传参顺序上传 1–35 张，jpg/jpeg/png/webp/bmp/tif，单张非空且 ≤50MB，建议 3:4 或 4:3。
- 标题：1–20 字；描述（含内联 `#话题`）：≤1000 字。
- 上传前只确定配乐风格或原声意图，不指定歌名。上传完成后读取页面实际推荐候选，根据内容选择合适配乐。
- 默认声明 AI 生成；纯实拍且无需 AI 声明时显式传 `--declaration none`。
- 成功返回 `url=https://www.douyin.com/note/<mid>`、`mid`、`content_id`。

## 发布前置与登录异常（必做）

先读并执行[共用登录流程](../_shared/publish-login.md)，图文与视频使用相同登录态和恢复步骤：

1. `douyin-note-publish open-page`，用 snapshot / 截图检查头像、用户名及创作者页面。
2. 未登录或运行中 exit 2：有头打开创作者中心，等用户完成登录，再执行 `login-manager --platform douyin` 导出验证；该命令本身不代用户登录。
3. 验证成功后重新 `open-page` 并检查页面。若此前已点击发布，先核实管理页 / 补取链接，不重跑发布。

同 session 的有头参数保持一致；登录期间不调用默认无头发布命令。详细命令、登录验证失败、限流及异常恢复见共用流程。

## 发布

页面确认已登录后，按顺序执行；候选必须在上传完成后读取：

```bash
douyin-note-publish upload --images /path/cover.png /path/page2.png
douyin-note-publish music-list
# 阅读返回的 name / author / duration，根据作品内容选择候选，复制其 choice
douyin-note-publish music-select --choice "上一步实际返回的choice"
douyin-note-publish fill --title "图文标题" --caption "描述 #话题"
douyin-note-publish publish
douyin-note-publish get-note-link --title "图文标题"
```

`upload` 等全部图片上传完成后才返回。`music-list` 打开音乐面板并读取当前候选，不预设歌名或搜索不存在的歌曲。需要其他分类时通过浏览器页面切换推荐 / 热门榜 / 纯音乐等实际可见分类，再运行 `music-list`。每次读取会更新候选编号；页面刷新、候选变化后必须重新读取。

`music-select` 仅接受当前页面返回的 `choice`，校验歌曲名、作者、时长及对应卡片，激活后只点击该卡片内的“使用”，确认面板关闭且表单“修改音乐”旁显示目标歌曲。验证失败停止，不能继续发布。`publish` 再次核对已选配乐。

只有明确决定使用原声时，跳过两个音乐命令，使用 `publish --original-sound`；也可调用 `run --original-sound --images ... --title ... --caption ...` 完成原声发布。不要为了省略选曲默认使用原声。`run` 不支持预先指定音乐。

## 分步与恢复

中间态由脚本保存在同一浏览器 session / 页面；不要插入其他抖音任务。刷新后重新读取候选、选择并验证。`publish` 仅表示已跳转管理页，必须接 `get-note-link`，拿到链接才记录成功。取链最多刷新并搜索 4 次，每次搜索后先等 5 秒，再轮询候选最多 30 秒，超时后间隔 3 秒重新搜索。在管理页标题与正文合并区域定位唯一标题前缀候选，判定与点击在同一次浏览器操作中完成；列表刷新暂时为空时继续等待。进入图文编辑页核验完整标题一致后读取 URL，不保存修改。多个候选或编辑页标题不符时停止；不通过列表首条或置顶视频猜链接，不自动重新发布。

`get-note-link` 完成后自动关闭 session；分步中途放弃时手动 `camoufox-cli --session douyin --persistent --json close`（有头时加 `--headed`）。

- exit 0：当前步骤成功；完整发布以 `run` / `get-note-link` 返回 note URL 为准。
- exit 1：参数、DOM 或浏览器错误；若已点击发布，先核实管理页，不能直接重跑 run。
- exit 2：明确登录失效，交 login-manager；heartbeat 中只记录并跳过。
- exit 3：发布结果或链接待核实；查看 `/tmp/dy-note-debug-*.json`，仅补取链接，不自动重发。同标题有多个候选时人工核实。

图文和视频共享任务锁与 session，忙时 fail-first，等当前任务结束再操作。单账号视频与图文合计每 24h ≤5 条，触发风控 30 分钟内不重试。审核中也可记录已确认的 note 链接；发布后以 `published-track record --platform douyin --content-type post` 入库，heartbeat 统一取数。
