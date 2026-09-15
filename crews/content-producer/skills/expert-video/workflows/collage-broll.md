# Workflow：Collage B-roll（纸拼贴组装动画）

Brief 里写 `workflow: collage-broll`，或甲方要"把这句口播做成拼贴 B-roll""纸拼贴动画""半调拼贴"时使用。把一句约 5 秒的口播压成一个 sharp visual idea，再做成高级编辑风纸拼贴组装动画。

本文是**通用制作流程在纸拼贴 B-roll 上的细化**（三道闸门、隐喻与静帧规范、Gate 3 批量调度），不替代通用流程；原子能力、护栏、工作区与交付约定照 `expert-video` 的 SKILL.md 执行。

## 三道闸门

| 闸门 | 停在哪 | 交付给甲方看什么 |
|------|--------|-----------------|
| Gate 1 隐喻确认 | 只设计视觉隐喻，**不生成图片、不生成视频、不调任何视频模型** | 每条的核心意思、情绪、一句话视觉命题、3–6 个关键物件、建议底色与点色、预期组装顺序 |
| Gate 2 静帧确认 | 隐喻确认后才写 visual spec 与 imagegen prompt，用 `siliconflow-img-gen` 生成静帧 | 带编号的静帧 contact sheet + `gate2-qa.md` |
| Gate 3 视频生成 | 静帧确认后不再问用哪个模型，直接调 `collage-broll gate3` 批量跑 i2v | 逐条 contact sheet + 末帧对照 + `gate3-qa.md` + `video-review` 结论 |

- 每道闸门都要**结束本轮回复**等甲方批；甲方只确认部分编号时，只让通过的条目进下一道。
- Gate 1 / Gate 2 分别对应通用制作流程的 GATE A（文本）/ GATE B（素材）语义：付费生成前必停。
- 甲方已在 Brief 中代理批准某道闸门时，把批准范围记进对应 QA 文件后继续。

## 成功标准

- 一句话只表达一个清晰隐喻；不要把文稿逐字放进画面。
- 一条文稿控制在 3–6 个关键物件；元素过多语意变弱，i2v 组装也不稳定。
- 同一批画面有统一设计语言，但**不强制全部蓝底**。
- 背景是强烈、平坦、均匀的色场，可按语意变化。
- 主体以黑白 halftone photographic cut-outs 为骨架；关键卡片、按钮、胶片、规则册等允许红、黄、青、橙、紫、奶油白等彩色纸张。
- 所有纸片有清晰裁切边、奶油白 keyline、低透明度柔和阴影和纸张颗粒。
- 动作是 assemble-from-empty，不是轻微漂移、晃动或慢 zoom。
- 无字幕、无口播全文、无 logo、无水印、无 UI。
- 默认交付 9:16、5 秒、720×1280、无声 MP4。

批量隐喻优先形成前后叙事（例如先表现手工消耗与经验流失，再表现规范沉淀与人机分工）。

## 不适用

- 需要精确控制图层、遮挡、镜头穿越或可编辑时间线 → 改用分层动画方案，并向甲方说明本 workflow 做不到。
- 只要视频提示词、不要成片 → 直接写 prompt 交付，不走本流程。
- 需要真实人物产品广告或口播演员 → 走 Narration Video，或只按通用制作流程做（不套类型 workflow）。
- 甲方明确要可逐层修改的透明素材 → 本 workflow 默认不拆透明图层。

## 项目目录

自建工作区 `output_videos/<topic-en-slug>/`（甲方不指定、不代建）：

```text
<project-dir>/
├── brief.md                     # 文稿 + Gate 1 隐喻清单
├── visual-spec.json             # Gate 2 视觉规格
├── imagegen-prompts.md          # Gate 2 Seedream prompt 留档
├── gen-jobs.json                # Gate 3 批量调用清单
├── gate2-qa.md                  # 静帧 QA 结论
├── gate3-qa.md                  # 视频 QA 结论
├── still-contact-sheet.jpg      # Gate 2 静帧总图
├── video-contact-sheet-all.jpg  # Gate 3 全部成片逐秒抽帧
├── video-first-frame-all.jpg    # 全部成片实际首帧（验证真的从空色场开始）
├── end-frame-comparison-all.jpg # 确认静帧 vs 视频末帧并排
├── 01-<concept-slug>/
│   ├── gen-prompt.txt           # aigc-video-gen --prompt 内容
│   ├── frames/
│   │   ├── still.png            # Gate 2 确认的完成帧（原图）
│   │   ├── last-frame.png       # 统一裁到 720x1280 的尾帧
│   │   └── first-frame.png      # 纯色空首帧（同底色 hex）
│   └── gen-runs/run-v01/
│       ├── final-5s.mp4         # aigc-video-gen 产物（声画同出）
│       ├── final-5s-noaudio.mp4 # 默认交付版（无声）
│       ├── contact-sheet.jpg
│       ├── video-last-frame.jpg
│       └── end-frame-comparison.jpg
└── 02-<concept-slug>/...
```

## Phase 1：设计视觉隐喻（Gate 1）

先把文稿压成一个视觉命题，提取：

- **核心意思**：观众最终要看懂什么
- **情绪**：冷静、惊讶、紧迫、豁然开朗、荒诞、反讽
- **动作动词**：打开、连接、漏掉、装订、归档、点亮、压缩、分叉、组装
- **可视化隐喻**：机器、时钟、胶片、档案柜、控制台、规则册、漏斗、轨道、棋子

输出格式：

```text
1. 核心意思：经验每次都在重复消耗
   视觉隐喻：熟练剪辑师围着巨大的胶片时钟逐帧裁切，时钟走完一圈却只得到一小段成片
   关键物件：胶片时钟、剪辑师、剪刀、短胶片
   色彩：焦橙底，奶油白与浅青点色
   组装顺序：时钟 → 人物与剪刀 → 胶片 → 最终短输出
```

输出后停下等确认。

## Phase 2：生成彩色拼贴静帧（Gate 2）

### visual-spec.json

```json
{
  "script_meaning": "",
  "visual_metaphor": "",
  "style_signature": "flat bold color field, mixed black-and-white halftone cut-outs and colored cardstock accents, crisp cut edges, cream keylines, soft paper shadows, editorial paper collage",
  "aspect_ratio": "9:16",
  "color_field": {
    "background_hex": "",
    "accent_colors": [],
    "paper_grain": "fine uncoated-paper fiber"
  },
  "elements": [{ "what": "", "role": "", "motion": "", "placement": "" }],
  "composition": { "layout": "", "negative_space": "", "final_frame": "" },
  "motion_plan": "structure first, subject or cards second, action and result last",
  "avoid": "typography, readable letters, numerals, logos, watermark, UI, subtitles, glossy 3D, photoreal environment"
}
```

### 色彩规则

不要把 cobalt blue 当唯一默认值。按语意挑强色场，一批作品保持"同设计语言、不同底色"：

| 色场 | 语意 |
|------|------|
| 焦橙 / 红 | 时间消耗、劳动、紧迫 |
| 芥末黄 | 工具、警示、经验漏失 |
| 墨绿 | 认知、审美、系统重置 |
| 深紫 | 规范、沉淀、长期记忆 |
| 青绿 | 判断、协作、自动执行 |

主体以黑白半调为主，局部彩色纸张必须服务信息层级，不为彩色而彩色。

### imagegen prompt（siliconflow-img-gen / Seedream）

```bash
siliconflow-img-gen --prompt "<下面整段>" --image-size 1600x2848 --out-dir <project>/01-<slug>/frames/
```

Prompt 用英文（Seedream 对英文响应更好）：

```text
Use case: ads-marketing
Asset type: final still frame for a 9:16 image-to-video B-roll clip
Primary request: Create a finished editorial paper-collage image expressing [一句话视觉命题].
Scene/backdrop: perfectly flat [颜色] paper field [hex] with subtle uncoated paper fiber.
Style/medium: premium editorial stop-motion paper collage; black-and-white halftone photographic cut-outs mixed with selective [点色] colored cardstock.
Composition/framing: vertical 9:16 locked poster frame; central subject within the middle 70 percent; generous clean color-field negative space; 3–6 large separable paper groups for later assemble-from-empty animation.
Materials/textures: visible printed halftone dots, crisp machine-cut edges, thin warm-cream paper keylines, soft low-opacity physical drop shadows.
Constraints: [本条隐喻必须一眼看懂的关系].
Avoid: no typography, no readable letters, no numerals, no logos, no watermark, no UI, no subtitles, no glossy 3D, no photoreal environment, no clutter.
```

Seedream 不支持参考图锁风格，"同设计语言"靠同一批复用同一 `style_signature` 字串 + 同一 `color_field` 范围。

### 静帧 QA

检查：隐喻是否一眼看懂 / 主体是否集中 / 是否有假字、logo、水印、UI / 是否保留足够纯色场便于从空场组装 / 是否 3–6 个清晰大组而非满屏碎片 / 同批是否统一质感但有色彩变化。

通过的原图复制到 `<item>/frames/still.png`，拼 contact sheet 后交甲方确认，结论写 `gate2-qa.md`。要求重生部分静帧时，新版 contact sheet 递增命名（`still-contact-sheet-v2.jpg`），保留旧版便于对比。

```bash
ffmpeg -y -pattern_type glob -i "<project>/*/frames/still.png" \
  -vf "scale=270:480,tile=5x1" -frames:v 1 <project>/still-contact-sheet.jpg
```

段数 > 5 时分多行（`tile=5x2`、`5x3`…）。

## Phase 3：i2v 生成视频（Gate 3）

### 1. 准备首尾帧

```bash
# 尾帧：确认静帧统一裁到 720x1280
ffmpeg -y -i <item>/frames/still.png \
  -vf "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280" \
  <item>/frames/last-frame.png

# 首帧：与尾帧同底色的纯色空纸面（assemble-from-empty 的核心）
ffmpeg -y -f lavfi -i color=c=0x<HEX>:s=720x1280 -frames:v 1 <item>/frames/first-frame.png
```

甲方明确要求不从完全空白开始时，首帧才保留一个基础物件。

### 2. 写动画 prompt（中文，声画同出）

动作顺序默认：`基础结构 → 人物或关键卡片 → 连接件 → 动作 → 最终结果`。

```text
画面从纯色空场开始，依次滑入 [基础结构] → [人物/卡片] → [连接件] → [动作]，最终定格在已确认的完成构图。固定机位，无切镜、无 zoom、无变形。画面无文字、无 logo、无水印、无 UI。音频：纸片滑入的嗒嗒声 + 卡位时的咔嗒声 + 最终定格的短促 BGM 收尾。
```

每条 prompt 明确首帧是空首帧、尾帧是确认过的完成帧；最终构图必须贴近 last-frame，不让模型自由改造尾帧。

### 3. 批量生成

写 `gen-jobs.json`（每条含 `prompt` / `first_frame` / `last_frame` / `output` / `ratio` / `resolution` / `duration`），然后：

```bash
collage-broll gate3 --batch <project-dir>/gen-jobs.json
collage-broll gate3 --batch <project-dir>/gen-jobs.json --dry-run   # 先看调度计划
```

内部串行逐条调公共 `aigc-video-gen` i2v（视频生成是异步轮询任务，并行会撞平台并发限），候选链 fallback 与 decisions.log 由 `aigc-video-gen` 自带。退出码 2 = 部分 job 失败：只重跑失败条目，已通过的不重跑。

开工前先跑 `collage-broll check-setup` 自检 ffmpeg / ffprobe / AWK_API_KEY / 视频平台 key / Python 版本。

> `aigc-video-gen` 要求输出相对路径落在 `output_videos/` 下，**调用时 workdir 必须是 Content Producer workspace 根**；i2v 报错先查首尾帧是否真存在、是否 720x1280。

### 4. 强制无声交付

```bash
ffmpeg -y -i <run>/final-5s.mp4 -map 0:v:0 -c:v copy -an <run>/final-5s-noaudio.mp4
```

默认交付 `final-5s-noaudio.mp4`，保留 `final-5s.mp4` 作中间产物。甲方明确要带声时直接交付 `final-5s.mp4`。

## 视频 QA

不要只看尾帧，必须检查组装过程与最终落位。

```bash
ffmpeg -y -i <run>/final-5s-noaudio.mp4 -vf "fps=1,scale=270:480,tile=5x1" -frames:v 1 <run>/contact-sheet.jpg
```

通过标准：

- 首帧接近纯色空场（边缘轻微提前露出纸片可接受）
- 中段能看到结构、人物或卡片逐步进入，而不是整体淡入
- 没有切镜、zoom、3D 化或写实场景漂移
- 没有假字、logo、水印或 UI
- 最终帧与确认静帧一致；轻微姿态或细节漂移只要不影响隐喻语义即判通过，不为此重跑
- 成片为 720×1280、5 秒

另抽视频末帧与确认静帧并排生成 `end-frame-comparison.jpg`；批量项目再合三张总览图（`video-contact-sheet-all.jpg` / `video-first-frame-all.jpg` / `end-frame-comparison-all.jpg`）。逐条 QA 结论（含带瑕疵通过的理由）写 `gate3-qa.md`。

### 技术自检（强制）

视觉 QA 后必须再跑公共 `video-review`，verdict=pass 才交付：

```bash
video-review <run>/final-5s-noaudio.mp4
```

视觉 QA 评美与语义，`video-review` 评技术合规（ffprobe 全字段 / 抽帧黑帧扫 / 音频电平 / 时长分辨率一致性），互补不重叠。fail 按 critical 项修或重生对应 job；warn 向甲方复述由其决定。

> 默认无声交付时 `audio_absent` warning 是预期，可放行；带声版出 `audio_absent` 是 critical（声画同出该出声没出声），退回重生成。

### 常见问题

| 症状 | 处理 |
|------|------|
| 首帧边缘提前露出 | 轻微可接受；严格空场需求改用更坚定的 first-frame（纯色 + 边缘 padding） |
| 组装感弱 | 缩短元素数量，prompt 改为明确的逐件"滑入 / 卡位"顺序 |
| 尾帧漂移 | 强化 prompt 里"最终定格在已确认的完成构图"（i2v 的 last-frame 权重高） |
| 出现假字 | 回到静帧重生，不要用视频 prompt 修补 |
| 个别视频失败 | 只重跑对应 job |
| i2v 报错 | 查首尾帧是否 720x1280、是否真存在、workdir 是否 workspace 根 |

## 交付

- 每条 `<item>/gen-runs/run-v01/final-5s-noaudio.mp4`（甲方要带声则 `final-5s.mp4`）
- 每条 contact sheet、批量总 contact sheet、末帧对照图
- `gate2-qa.md` / `gate3-qa.md` / `video-review` 结论
- 一句说明每条文稿如何转成视觉隐喻
- 回报产物**绝对路径**

成片问题来自 i2v 生成限制（组装感弱 / 尾帧漂移）时直接说明；只有需要精确图层控制时才建议换方案，并向甲方报清代价。
