# Workflow：Collage B-roll（纸拼贴组装动画）

Brief 里写 `workflow: collage-broll`，或甲方要"把这句口播做成拼贴 B-roll""纸拼贴动画""半调拼贴"时使用。本文指导**从 Brief 生产纸拼贴 B-roll 的 script**（隐喻清单）及这一步之后的自检（隐喻自检，GATE A 质检标准），并附该类型的制作约定（方法论移植自 gbro-collage-broll：半调纸拼贴 + assemble-from-empty）；闸门收敛为 GATE A / GATE B 两道——**GATE A 检隐喻清单（即本类型的 script），GATE B 检静帧 contact sheet（即素材）**。不替代通用流程；原子能力、护栏、工作区与交付约定照 `expert-video` 的 SKILL.md 执行；本文与通用流程冲突处以本文为准，但闸门与护栏不让步。

## 类型定义

把一句约 5 秒的口播文稿压成一个 sharp visual idea，做成高级编辑风**半调纸拼贴（halftone paper-collage）组装动画** B-roll：

- 强烈、平坦、均匀的纯色纸面色场 + 黑白 halftone 照片剪贴为骨架 + 彩色卡纸点缀服务信息层级
- 动作是 assemble-from-empty：元素从空场逐件滑入、卡位、组装（stop-motion 质感），不是轻微漂移、晃动或慢 zoom
- 默认交付 9:16、5 秒、720×1280、无声 MP4，可直接垫在口播下面

逐条文稿 → 逐条隐喻 → 逐条独立成片。批量隐喻优先形成前后叙事（例如先表现手工消耗与经验流失，再表现规范沉淀与人机分工）。

## 输入契约（Brief 侧）

| Brief 字段 | 要求 |
|-----------|------|
| 文稿 | 甲方交付：口播形态给 `voiceover.md`（绝对路径），其余给 Brief 内文稿字段，逐条可独立成句。**落稿锁定不重写**——隐喻是文稿的视觉转译，不是改写；发现文稿无法转译（一句话塞多个隐喻、超时长带）报 Brief owner |
| form | 画幅 / 时长 / 分辨率 / 声音；未指定按默认（9:16、5s、720P、无声） |
| gates | GATE A / GATE B 批准人；代理批准时写明批准范围 |
| acceptance | 验收标准（未指定按「交付」节默认） |

## 阶段裁剪表（相对通用制作流程）

| Stage | 处置 | 本文对应 |
|-------|------|---------|
| 0 Brief intake | 照走 | 核对文稿逐条可拆、规格齐；缺字段向 Brief owner 澄清 |
| 1 script-write | **重定义** | Phase 1 隐喻设计——产物落 `script/script.md`（隐喻清单），就是本类型的"分场剧本" |
| 2 script-self-eval | **重定义** | 隐喻自检（见 Phase 1），任一条不过必返工 |
| 3–5 storyboard / shot-decompose / character-register | **裁剪** | 单镜固定机位、无人物角色，不建 storyboard / shot_decompose / characters |
| GATE A | 照走 | 呈交隐喻清单 |
| 6–9 slot-plan → delivery-promise-lock | **由静帧生成替代** | Phase 2：visual-spec + Seedream 静帧 + 静帧 QA；AIGC 素材的来源记录 = prompt + 模型 + 生成时间 |
| GATE B | 照走 | 呈交静帧 contact sheet |
| 10 render-shot | **重定义** | Phase 3：i2v 首尾帧组装（`collage-broll render` 批量调度） |
| 11 mix-audio | **裁剪** | 默认无声交付；甲方要 aigc 原声时交付带声版 |
| 12 assemble | **裁剪** | 逐条独立成片，不拼接 |
| 13a video-review | 照走（强制） | 无声版 `audio_absent` warning 是预期，放行；带声版出 `audio_absent` 是 critical |
| 13b motion-audit | 照走 | 抽查组装过程逐件进入而非整体淡入 |
| 13c normalize | 无声片豁免 | 带声版必跑 |
| 14a make-cover | 按需 | B-roll 垫片通常无封面，Brief 要求才做 |
| 15 交付 | 照走 | 回报产物绝对路径 |

## Phase 1 隐喻设计（Stage 1 重定义）

先把每条文稿压成一个视觉命题，提取：

- **核心意思**：观众最终要看懂什么
- **情绪**：冷静、惊讶、紧迫、豁然开朗、荒诞、反讽
- **动作动词**：打开、连接、漏掉、装订、归档、点亮、压缩、分叉、组装
- **可视化隐喻**：机器、时钟、胶片、档案柜、控制台、规则册、漏斗、轨道、棋子

**不要把文稿逐字放进画面。** 默认一条文稿只做一个隐喻，控制在 3–6 个关键物件；元素过多语意变弱，i2v 组装也不稳定。

`script/script.md` 每条格式：

```text
1. 核心意思：经验每次都在重复消耗
   视觉隐喻：熟练剪辑师围着巨大的胶片时钟逐帧裁切，时钟走完一圈却只得到一小段成片
   关键物件：胶片时钟、剪辑师、剪刀、短胶片
   色彩：焦橙底，奶油白与浅青点色
   组装顺序：时钟 → 人物与剪刀 → 胶片 → 最终短输出
```

### 隐喻自检（Stage 2 重定义，任一条不过必返工）

1. 一句话只表达一个清晰隐喻？
2. 关键物件 3–6 个，不是满屏碎片？
3. 文稿没有逐字进画面（无字幕、无口播全文）？
4. 底色与点色按语义色场表选，有理由（见 Phase 2 色彩规则）？
5. 批量时前后叙事成立，或每条独立成立？

## GATE A：呈交隐喻清单

文本闸门——**停，结束本轮回复**，发 Brief owner 审：

- 呈交：条数、每条一句话视觉命题、色彩方案、组装顺序概览
- 甲方只确认部分编号时，只让通过的条目进 Phase 2；未通过条目改隐喻重审
- 甲方已在 Brief 代理批准时，把批准范围落 `gates/gate-a.md` 后继续

## Phase 2 生成静帧（GATE A 批准后）

先写自包含的 `script/visual-spec.json`，再写 imagegen prompt。

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

### imagegen prompt（awk-img-gen / 百炼）

```bash
awk-img-gen --prompt "<下面整段>" --image-size 1536x2688 --out-dir <project>/render/<item-slug>/frames/
```

> 尺寸注意：百炼上限总像素 2048×2048，旧火山 9:16 预设 `1600x2848` 超限会被脚本拒绝；9:16 一律用 `1536x2688`。

Prompt 语言：下面模板是英文可照用；qwen-image / wan2.7 中文同样好，**要渲染的文字必须原句完整写入**（见 awk-img-gen 封面最佳实践）。整段落 `script/imagegen-prompts.md` 留档：

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

同设计语言：优先用 awk-img-gen 参考图编辑（`--image` 传同批已过 QA 的静帧，1–3 张）锁风格；不用参考图时靠同一批复用同一 `style_signature` 字串 + 同一 `color_field` 范围。

### 静帧 QA

检查：隐喻是否一眼看懂 / 主体是否集中 / 是否有假字、logo、水印、UI / 是否保留足够纯色场便于从空场组装 / 是否 3–6 个清晰大组而非满屏碎片 / 同批是否统一质感但有色彩变化。

通过的原图复制到 `render/<item-slug>/frames/still.png`，拼带编号的 contact sheet。要求重生部分静帧时，新版 contact sheet 递增命名（`still-contact-sheet-v2.jpg`），保留旧版便于对比。QA 结论写 `review/still-qa.md`。

```bash
ffmpeg -y -pattern_type glob -i "<project>/render/*/frames/still.png" \
  -vf "scale=270:480,tile=5x1" -frames:v 1 <project>/review/still-contact-sheet.jpg
```

段数 > 5 时分多行（`tile=5x2`、`5x3`…）。

## GATE B：呈交静帧 contact sheet

素材闸门——**停，结束本轮回复**，发 Brief owner 看：

- 呈交：静帧 contact sheet（带编号）、静帧 QA 结论、每条色彩与隐喻的对应关系
- 部分通过：只让通过的条目进 Phase 3；要改的静帧重生并重新确认
- 授权与来源记录一并呈交（AIGC 素材 = prompt + 模型 + 生成时间，留档见工作区）
- 甲方已在 Brief 代理批准时，把批准范围落 `gates/gate-b.md` 后继续

## Phase 3 i2v 组装视频（Stage 10 重定义）

### 1. 准备首尾帧

```bash
# 尾帧：确认静帧统一裁到 720x1280
ffmpeg -y -i render/<item>/frames/still.png \
  -vf "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280" \
  render/<item>/frames/last-frame.png

# 首帧：与尾帧同底色的纯色空纸面（assemble-from-empty 的核心）
ffmpeg -y -f lavfi -i color=c=0x<HEX>:s=720x1280 -frames:v 1 render/<item>/frames/first-frame.png
```

甲方明确要求不从完全空白开始时，首帧才保留一个基础物件。

### 2. 写动画 prompt（中文，声画同出）

动作顺序默认：`基础结构 → 人物或关键卡片 → 连接件 → 动作 → 最终结果`。

```text
画面从纯色空场开始，依次滑入 [基础结构] → [人物/卡片] → [连接件] → [动作]，最终定格在已确认的完成构图。固定机位，无切镜、无 zoom、无变形。画面无文字、无 logo、无水印、无 UI。音频：纸片滑入的嗒嗒声 + 卡位时的咔嗒声 + 最终定格的短促 BGM 收尾。
```

每条 prompt 明确首帧是空首帧、尾帧是确认过的完成帧；最终构图必须贴近 last-frame，不让模型自由改造尾帧。

### 3. 批量生成

写 `render/gen-jobs.json`（每条含 `prompt` / `first_frame` / `last_frame` / `output` / `ratio` / `resolution` / `duration`），然后：

```bash
collage-broll render --batch <project-dir>/render/gen-jobs.json
collage-broll render --batch <project-dir>/render/gen-jobs.json --dry-run   # 先看调度计划
```

内部串行逐条调公共 `aigc-video-gen` i2v（视频生成是异步轮询任务，并行会撞平台并发限），候选链 fallback 与 decisions.log 由 `aigc-video-gen` 自带。退出码 2 = 部分 job 失败：只重跑失败条目，已通过的不重跑。

开工前先跑 `collage-broll check-setup` 自检 ffmpeg / ffprobe / AWK_API_KEY / 视频平台 key / Python 版本。

> `aigc-video-gen` 要求输出相对路径落在 `output_videos/` 下，**调用时 workdir 必须是 Content Producer workspace 根**；i2v 报错先查首尾帧是否真存在、是否 720x1280。

### 4. 强制无声交付

```bash
ffmpeg -y -i render/<item>/gen-runs/run-v01/final-5s.mp4 -map 0:v:0 -c:v copy -an \
  render/<item>/gen-runs/run-v01/final-5s-noaudio.mp4
```

默认交付 `final-5s-noaudio.mp4`，保留 `final-5s.mp4` 作中间产物（aigc 声画同出的原声版；甲方明确要带声时直接交付它）。

## 视频 QA（Stage 13）

不要只看尾帧，必须检查组装过程与最终落位。

```bash
ffmpeg -y -i render/<item>/gen-runs/run-v01/final-5s-noaudio.mp4 \
  -vf "fps=1,scale=270:480,tile=5x1" -frames:v 1 render/<item>/gen-runs/run-v01/contact-sheet.jpg
```

通过标准：

- 首帧接近纯色空场（边缘轻微提前露出纸片可接受）
- 中段能看到结构、人物或卡片逐步进入，而不是整体淡入
- 没有切镜、zoom、3D 化或写实场景漂移
- 没有假字、logo、水印或 UI
- 最终帧与确认静帧一致；轻微姿态或细节漂移只要不影响隐喻语义即判通过，不为此重跑
- 成片为 720×1280、5 秒

另抽视频末帧与确认静帧并排生成 `end-frame-comparison.jpg`；批量项目再合三张总览图落 `review/`（`video-contact-sheet-all.jpg` / `video-first-frame-all.jpg` / `end-frame-comparison-all.jpg`）。逐条 QA 结论（含带瑕疵通过的判定理由）写 `review/collage-video-qa.md`。

### 技术自检（强制）

视觉 QA 后必须再跑公共 `video-review`，verdict=pass 才交付：

```bash
video-review render/<item>/gen-runs/run-v01/final-5s-noaudio.mp4
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

## 工作区

自建工作区 `output_videos/<topic-en-slug>/`（甲方不指定、不代建），在通用流程标准树上裁剪：

```text
<project-dir>/
├── brief.md / voiceover.md        # 甲方交付（Brief + 落稿锁定文稿）
├── script/
│   ├── script.md                  # Phase 1 隐喻清单（本类型的"分场剧本"）
│   ├── visual-spec.json           # Phase 2 视觉规格
│   ├── imagegen-prompts.md        # imagegen prompt 留档
│   └── decisions.json             # 决策审计链
├── gates/
│   ├── gate-a.md / gate-b.md      # 闸门批准记录（含批准人与批准范围）
├── render/
│   ├── gen-jobs.json              # Phase 3 批量 i2v 调用清单
│   └── <item-slug>/
│       ├── frames/                # still.png（确认原图）/ last-frame.png / first-frame.png
│       └── gen-runs/run-v01/      # final-5s.mp4 / final-5s-noaudio.mp4 / contact-sheet.jpg /
│                                  # video-last-frame.jpg / end-frame-comparison.jpg
└── review/
    ├── still-qa.md                # GATE B 静帧 QA 结论
    ├── still-contact-sheet.jpg    # GATE B 呈交物（重生递增 v2/v3…）
    ├── collage-video-qa.md        # Phase 3 逐条视频 QA 结论
    └── video-contact-sheet-all.jpg / video-first-frame-all.jpg / end-frame-comparison-all.jpg
```

## 交付

- 每条 `render/<item-slug>/gen-runs/run-v01/final-5s-noaudio.mp4`（甲方要带声则 `final-5s.mp4`）
- 每条 contact sheet、批量总 contact sheet、末帧对照图
- `review/still-qa.md` + `review/collage-video-qa.md` + `video-review` 结论
- 一句说明每条文稿如何转成视觉隐喻
- 回报产物**绝对路径**

成片问题来自 i2v 生成限制（组装感弱 / 尾帧漂移）时直接说明；只有需要精确图层控制时才建议换方案，并向甲方报清代价。

## 不适用

- 需要精确控制图层、遮挡、镜头穿越或可编辑时间线 → 改用分层动画方案，并向甲方说明本 workflow 做不到
- 只要视频提示词、不要成片 → 直接写 prompt 交付，不走本流程
- 需要真实人物产品广告或口播演员 → 走 Narration Video，或按通用制作流程做
- 甲方明确要可逐层修改的透明素材 → 本 workflow 默认不拆透明图层
