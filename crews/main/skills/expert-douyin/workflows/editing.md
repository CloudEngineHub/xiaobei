# 改片与调整 Workflow

用户说"帮我改改这条""文案重写一下""剪紧一点""换个封面"走这个。

抖音平台不支持替换已发布视频的文件；所有"改"都作用在我们的成片或素材上，改完的成品如需上线是一次**新发布**（重复内容重新发布有去重与风控风险，先跟用户说清再发）。

## 入口判断

先搞清楚改的是哪个层级，不要上来就大改：

| 用户的说法 | 改的层级 | 怎么走 |
|-----------|---------|--------|
| "改下标题 / 简介 / 话题" | 文案层 | 按 DNA `title-cover` 重写，直接给候选 |
| "剪紧一点 / 去口气词 / 把高光剪出来" | 轻剪层 | `talking-head-cut`（去口气词、结巴、静音，按发言内容剪高光） |
| "加 BGM / 加字幕 / 补片头片尾 / 插一段素材" | 加工层 | `video-edit`（audio-mix / subtitles / extract / assemble） |
| "结构调一下 / 把第二段提前 / 换个讲法" | 结构层 | 先出调整方案（新的段落顺序与时点）-> 确认 -> `video-edit` 重剪 |
| "换个封面" | 封面层 | 成片抽帧或 `siliconflow-img-gen` 按 DNA `production-spec`（画面风格）重做 |
| "换个风格 / 方向不对" | 方向层 | 回到 `content-production.md` 从选题重新走 |

## 文案层

标题、简介、话题标签按目标 DNA `title-cover` 重写：

1. 目标 DNA 不确定时先确认（用户指定或默认 `dna-0`）。
2. 标题 ≤ 30 字；简介与话题按 template 策略；禁止引流信息。
3. 给 2-3 个候选并说明各自侧重的标题类型，用户选定后更新 `douyin/outputs/<video-name>/` 的文案记录。

## 轻剪层与加工层

改前确认素材位置（`douyin/outputs/<video-name>/` 下的成片与原始素材）。

- 口播类去口水、剪高光 -> `talking-head-cut`，剪拼结果交给 `video-edit apply-cut`。
- 加旁白 / BGM / 字幕 / 抽段拼接 -> `video-edit`。
- 画面集锦类重剪：`video-edit frames` 抽帧 -> agent 看图写 cut_plan -> `video-edit apply-cut`。

改完成片必须过 `video-review` 闸门，verdict fail 不带病交付。

## 结构层

先出结构调整方案（新的段落顺序、每段时点、删留内容），用户确认后再动剪。
结构调整先核对 `content-idea`（内容创意）与 `video-form`（视频形态）；若口播文案子模块已启用，再按 `narration-script` 核对口播结构。不要把 DNA 扩写成逐镜规则——镜头与剪辑细节归 Content Producer。

## 换封面

1. 用户直接指定封面图 -> 直接使用。
2. 用户说"从片子里选一帧" -> 抽帧候选给用户挑。
3. 用户说"重做一张" -> 按 DNA `production-spec`（画面风格）与本次标题/核心收益，用 `siliconflow-img-gen` 生成，用户确认后替换 `cover.jpg`。

## 改完必做

1. 自己过一遍质量自检（钩子是否兑现、结构是否完整、音画是否同步）。
2. 跟用户说清楚改了什么、为什么这么改。
3. 改片结论属于可复用风格偏好时，按 `style-dna.md` 的反馈回流判定更新 DNA；单次修改不动 DNA。

## 改后发布

用户要求改完后发布 / 重新发布时，走 `content-production.md` 的发布与记录流程（Step 6-7）：

1. **发布**：`douyin-publish open-page` + 登录态判定后 `run`；标题与文案用改后版本。
2. **记录**：`published-track record` 重新入库为新记录（新链接、新发布日期），`dna-meta.json` 沿用该视频目录的 DNA 绑定。
3. 重新发布前提醒用户：旧作品是否自行在平台删除由用户决定，Agent 不代删。
