# 小贝系统视频能力重新规划 — 调研与开发计划

> 起草日期：2026-07-25（周六）
> 状态：调研期历史文档（未进入开发），**不作为当前实现依据**
> 2026-09-10 注：本文提到的 `video-producer` / `collage-broll` / `manim-explainer` / `design-full` 四个技能已整合为 `crews/content-producer/skills/expert-video`（含 `video-producer` / `collage-broll` 两个 tool 与 reversal-ad / narration-video / collage-broll 三个 workflow）与 `expert-design`（含 `design-full` tool 与 web-page / app-ui / brand-visual 三个 workflow），`manim-explainer` 已删除；main 与 content-producer 的分工与 Brief 交接契约以 `docs/expert-pack-dna-architecture.md` 4.7 / 4.9 节为准。
> 用途：本文件用于**沉淀调研结果**与**规划出发点**，最终据此生成开发计划。开发计划不在本文件撰写，等调研结束另起一份。

---

## 1. 规划出发点（用户钦定，调研期不得改动）

### 1.1 main agent 与 content-producer 在视频生产上的分工界限

小贝 main agent 与 content-producer 在视频生产上的职责边界如下：

| 维度 | main agent（小贝） | content-producer |
|------|------------------|------------------|
| 平台运营 | ✅ 全部负责：发送数据监控等 | ❌ 不负责 |
| 视频生产 | ⚠️ 受限 | ✅ 主力 |
| 出脚本 | ❌ 不负责 | ✅ 负责 |
| 基于已有/用户素材进行组装 | ✅ 负责 | ✅ 也可调用（基础能力） |
| 为组装目的使用 AIGC 或 **Stock Footage 模式**下载补充 | ✅ 负责 | ✅ 也可调用（基础能力） |
| 基于用户素材做简单剪辑（去口气词、高光剪辑、录制操作视频） | ✅ 负责 | ❌ 不负责（已交给 main 的 ui-demo 等） |
| 其余视频能力（含出脚本） | ❌ 不负责 | ✅ 负责 |

**核心约束**：main agent 的视频能力**仅限**以下三种场景：

1. 基于已有素材或用户给定素材进行**组装**；
2. 为上述组装目的，使用 AIGC 或 **Stock Footage 模式**进行下载补充；
3. 基于用户提供的素材进行**简单剪辑**（如去口气词、高光剪辑、录制操作视频）。

其余视频能力——包括出脚本的能力——**全部归 content-producer**。

### 1.2 技能调动已完成的部分

用户已执行下列技能调动（调研期视为现状，不要再规划调动）：

- `youtube-publish`、`bilibili-publish` 两个技能暂时调整出代码仓，后面根据市场反馈再看。
- `ui-demo` 已调整至 main agent
- main agent 的 `video-produce` 技能调整到 content-producer，作为基础能力

### 1.3 待后续规划的部分

- content-producer 的视频制作工作流程、约定、技能等，**后面还要再次规划**。本文件不直接撰写该流程，仅在调研 todo 里列出该调研事项。
- 目前 `crews/main/skills/video-product` 中保留的 AIGC 能力要抽到 `skills/` 中，作为公共能力同时提供给 main agent 和 content-producer。**调研期只调查抽什么、怎么抽**，实际抽取由后续开发计划执行。

### 1.4 main agent 的 video-produce 技能需要完全重构

重构思路：

- **借鉴**：https://github.com/bigbrother666sh/MoneyPrinterTurbo/tree/main（MoneyPrinterTurbo，一站式 AI 短视频生成工具）
- **保留按现有 SKILL.md**：工作区管理约定、素材补充方案、合成成品、制作封面、用户确认这些环节**按目前 SKILL.md**不改。
- **scripts 清理**：scripts 中用不到的脚本可以删除（content-producer 那里已有完整备份，删了不丢）。

> 调研记录：当前 `crews/main/skills/video-product/scripts/` 下的脚本清单为 `assemble.py / check.py / compress_preview.py / extract_and_concat.py / gen.py / review.py / state.py / tts.py`，共 8 个。重构后应保留哪些、删哪些，需要结合 MoneyPrinterTurbo 的能力拆解后才能定。

---

## 2. 现状盘点（调研结果，持续追加）

### 2.1 main agent 现有视频相关技能清单

调研日期 2026-07-25，扫 `crews/main/skills/` 下所有 SKILL.md：

| 技能 | 描述 / 用途 | 是否与本次重构相关 |
|------|------------|------------------|
| `video-product` | 当前 SKILL.md frontmatter `name: TODO:rename`，描述"将已有视频素材拼接成完整视频，支持通过 AIGC 或者 pexels-footage、pixabay-footage 进行素材补充以及按需补充配音配乐" | ✅ 本次重构的核心目标 |
| `ui-demo` | 录制产品 UI demo 视频（patchright 录屏 + 鼠标覆盖层 + 字幕），三阶段 Discover→Rehearse→Record | ✅ 已迁至 main，属于"录制操作视频"能力范畴 |
| `youtube-publish` | YouTube Data API v3 上传视频 | ⚠️ 平台运营能力，不在 video-produce 重构内但与之相关 |
| `bilibili-publish` | B 站上传 | ⚠️ 同上 |
| `viral-chaser` | 下载分析抖音/B 站/小红书爆款视频，**仅产出追爆报告**，视频生产需另行委托 content-producer | ⚠️ main 的 viral-chaser 与 content-producer 的衔接关系，重构后需重新明确 |

main agent 其余发布/运营技能（douyin-publish / wechat-channels-publish / weibo-publish / wx-mp-publisher / wx-mp-engagement / xhs-publish / xhs-content-ops / xianyu-ops / zhihu-publish / wxwork-moments 等）属平台运营范畴，按出发点 1.1 仍归 main agent，不在本次重构内。

### 2.2 content-producer 现有视频相关技能清单

扫 `crews/content-producer/skills/`：

| 技能 | 描述 / 用途 | 与本次的关系 |
|------|------------|------------|
| `video-product` | 仅占位符 SKILL.md，scripts/stages 是 main agent 的完整副本 | ✅ 出发点 1.3 明示"后面还要再次规划" |
| `siliconflow-video-gen` | SiliconFlow Video API（Wan2.2 T2V/I2V），异步提交→轮询→下载 | ✅ 可能并入公共能力 |
| `siliconflow-tts` | SiliconFlow MOSS-TTSD-v0.5 TTS | ⚠️ TTS 备选，可能并入公共能力 |
| `collage-broll` | 纸拼贴组装动画（gbro 适配版），三闸门审批，最终用 gen.py i2v 出片 | ⚠️ 高级 B-roll 能力，属 content-producer 范畴 |
| `html-video` | html-video 引擎模板驱动视频生成（23+ 模板），TTS/BGM 由 openclaw MiniMax 扩展提供 | ⚠️ 模板驱动路径，属 content-producer 范畴 |
| `manim-explainer` | Manim 科学动画 | ⚠️ 属 content-producer 范畴 |
| `design-system-picker` | 设计系统选择 | ⚠️ 属 content-producer 范畴 |
| `init-workspace` | content-producer 工作区初始化 | ⚠️ 属 content-producer 范畴 |

### 2.3 公共 skill（`skills/`）现状

扫 `skills/` 下与视频生产相关的公共技能：

| 技能 | 描述 / 用途 | 与本次的关系 |
|------|------------|------------|
| `siliconflow-img-gen` | 火山方舟 Seedream 图像生成 / 编辑（默认 doubao-seedream-4.5，fallback doubao-seedream-5.0-lite） | ✅ 出发点 1.4 提到的"制作封面"用此，已是公共能力 |
| `pexels-footage` | Pexels 版权免费图片/视频素材下载 | ✅ 出发点 1.1 提到的 Stock Footage 模式之一，已是公共能力 |
| `pixabay-footage` | Pixabay 版权免费素材下载 | ✅ 同上（未细读，但 SKILL 列表已确认存在） |
| `smart-search` / `browser-guide` / `web-form-fill` / `email-ops` / `wxwork-drive` / `complex-task` | 与视频生产无直接关系 | ❌ 不在本次范围 |

### 2.4 main agent `video-product` scripts 现状摘要

逐脚本调研（已读各脚本头部）：

| 脚本 | 行数 | 用途摘要 | MoneyPrinterTurbo 借鉴后是否仍需要 |
|------|------|---------|----------------------------------|
| `assemble.py` | 457 | 把 artifacts/ 下片段按数字前缀顺序拼接为成片；无外部音频则保留各段原音轨，有外部音频则替换 | **保留**——合成成品环节按现有 SKILL.md 不变 |
| `gen.py` | 675 | 直连百炼 happyhorse / 火山 Seedance 生成视频片段（声画同出），百炼按模式走候选链，火山走 Fast→Normal→Mini | **抽到公共 skills/**——AIGC 补充能力应公共化（出发点 1.3） |
| `tts.py` | 457 | SiliconFlow MOSS-TTSD-v0.5 TTS；与 content-producer 的 `siliconflow-tts` 脚本是同一份 | **抽到公共 skills/** 或并入 `siliconflow-tts`——避免重复 |
| `compress_preview.py` | 161 | 把视频压到 ≤16MB 用于聊天逐段确认（产物仅用于确认不参与合成） | **保留**——逐段确认是 main agent 视频生产工作流的一部分 |
| `extract_and_concat.py` | 545 | 从 MP4 抽片段（head/tail/slice）并可选拼接为一片；支持多段拼接 | **保留**——是"基于用户素材做简单剪辑"的核心脚本（出发点 1.1 第 3 条） |
| `check.py` | 472 | 检查素材质量与时长缺口（仅 Stock Footage 模式） | ⚠️ 待 MoneyPrinterTurbo 调研后定——可能保留也可能被借鉴方案替代 |
| `review.py` | 485 | 成片自检闸门：ffprobe 校验 + 4 位置抽帧黑屏扫描 + 音频电平 + 时长/分辨率一致性 | **保留**——成片自检是 main agent 交付前的强制闸门 |
| `state.py` | 184 | 项目状态机：固定阶段链 script→gate0→calibrate→assets→assemble→review→cover→deliver | ⚠️ 重构后阶段链会变（不再有 script/gate0/calibrate），脚本需重写或大幅简化 |

### 2.5 当前 SKILL.md 工作流摘要（main agent video-product）

当前 SKILL.md 描述的工作流（重构前的现状）：

1. 工作区目录准备（`output_videos/<topic-en-slug>/`，固定子目录结构 raw_materials/downloads/generations/artifacts/previews）
2. AIGC 补充生成视频片段（按需）—— 百炼 happyhorse / 火山 Seedance，含候选链 fallback
3. Stock Footage 模式（无 AIGC 可用或用户要求时）—— pexels-footage → pixabay-footage
4. 补配音配乐（用户素材需要时）—— OpenClaw 内置 TTS 优先，回退 tts.py
5. 合成成品（assemble.py）
6. 制作封面（siliconflow-img-gen，封面必须含标题文字）
7. 用户确认

**当前 SKILL.md 严重越界的地方**（按出发点 1.1 应砍掉）：

- frontmatter `description` 写的是"将已有视频素材拼接成完整视频"——OK
- 但 SKILL.md 正文里实际上**没有出脚本的环节**，而是引用了 stages/ 下的 step2-script.md（人物叙事脚本、三段式结构、声画同出音色设定、片段规划、slideshow-risk 自检、Gate 0 contact sheet、content-calibrator 打分、预算估算……）——这些都是 content-producer 范畴，**当前竟然寄生在 main agent 的 video-product 里**，是历史包袱
- 出发点 1.1 明示"出脚本的能力全部归 Content Producer"——所以重构后 SKILL.md 必须把整个 stages/ 拆掉，stages/ 在 main agent 这一侧应整体删除（content-producer 那里有完整备份）

### 2.6 viral-chaser 与 content-producer 的衔接

**已定（用户 2026-07-25 拍板）**：viral-chaser 衔接按上一轮已改的形态——viral-chaser **只管出脚本**，制作明确委托 content-producer。本节调研结束，不再作为开放问题。

> 调研差异记录：当前仓内 `crews/main/skills/viral-chaser/SKILL.md`（行 50）仍是旧措辞"仅产出追爆报告，不生成脚本，不制作视频，如需据此生成视频需另行委托 content-producer"。用户表示"上一轮已改好且已同步本地"——可能改动在别处或本地未推。此项**不在本调研范围**，仅作差异备忘，不在调研 todo 里列。

### 2.7 content-producer `video-product` 当前形态

`crews/content-producer/skills/video-product/SKILL.md`：

```markdown
TODO: 这里的stages和scripts作为原子能力，供video producer其他技能调用过程和整合
```

scripts/ 与 stages/ 是 main agent 的完整副本（含 gen.py / assemble.py / review.py / state.py / tts.py / check.py / compress_preview.py / extract_and_concat.py，以及 stages/ 下 input-sources.md / model-selection.md / prohibitions-notes.md / step2-script.md / step3-user-assets.md / step4-assets.md / step5-compose.md）。

按出发点 1.3，content-producer 侧的 SKILL.md 工作流"后面还要再次规划"——本调研文件不直接撰写该工作流，但调研 todo 里要列出该事项。

#### 2.8 CP 侧五技能职责矩阵

| 技能 | 职责定位 | 视频生产路径 | 与 main 重构的重复风险 |
|------|---------|------------|---------------------|
| `collage-broll` | 把一句 ~5s 口播压成 editorial 纸拼贴组装动画（gbro 适配版） | Gate1 隐喻 → Gate2 siliconflow-img-gen 静帧 → Gate3 调公共 `aigc-video-gen` i2v 首尾帧插值出 5s 720x1280 无声/带声 MP4 | ❌ 无重复——属 CP 高级 B-roll，main 不做拼贴动画 |
| `html-video` | html-video 引擎模板驱动视频（23+ 模板，Content-Graph IR） | content-graph.json → 素材预获取（用户预置/video_generate/siliconflow-video-gen/pixabay/pexels）→ project-set-var 注入 → MiniMax TTS+BGM → hv.sh project-render | ⚠️ 素材预获取链与 main Stock Footage 重叠，但 html-video 是模板渲染范式，main 是 ffmpeg 直拼范式，**范式不同不重复** |
| `manim-explainer` | Manim 技术 explainer 动画（图/流程/架构/指标） | 定义视觉论点 → 拆 3–6 场 → 写 Manim 代码 → render-manim.sh 三档质量（low/medium/high）渲染 → 可 hand off 给 fragment-assembly + siliconflow-tts | ❌ 无重复——Manim 是科学动画，main 不做 |
| `design-system-picker` | 从内置 14 套设计系统库匹配风格规范（Stripe/Vercel/Linear/Notion/Apple/Supabase/Shopify/Figma/Spotify/Tesla/Framer/Airbnb/BMW/IBM/Starbucks） | `pick.sh "<风格描述>"` → 匹配 → 读 `./design-systems/<name>.md` 8 段规范（Visual Theme/Color/Typography/Components/Layout/Depth/Do's&Don'ts/Responsive） | ❌ 无重复——这是设计规范选择，不是视频生产，main 不做设计 |
| `init-workspace` | 为单项设计任务创建标准目录 + brief 模板 | `init.sh <任务名>` → `design_assets/YYYY-MM-DD-<任务名>/{brief.md,prompts.json,source/,output/}` | ⚠️ 与 main 的 `output_videos/<topic-en-slug>/` 工作区约定不同目录——**各自范式自洽，不强行统一** |

#### 2.9 CP 侧视频生产的三条平行路径

CP 侧已有视频生产不是一条链，是**三条平行路径**，按内容类型择：

1. **拼贴动画路径**（collage-broll）：口播文稿 → 纸拼贴组装动画，走 Gate1/2/3 三闸门，最终调公共 `aigc-video-gen` i2v 出片
2. **模板驱动路径**（html-video）：Content-Graph IR → 23+ 模板 → hv.sh 渲染，TTS/BGM 走 MiniMax 扩展
3. **科学动画路径**（manim-explainer）：Manim 代码 → render-manim.sh 三档渲染，可 hand off 给 fragment-assembly + siliconflow-tts

**三条路径的共同基础设施**：
- 视频生成：公共 `aigc-video-gen`（本轮已抽，collage-broll Gate3 已改调）+ CP 专属 `siliconflow-video-gen`（Wan2.2，html-video 素材预获取链用）
- TTS：公共 `siliconflow-tts`（本轮已抽，优先 OpenClaw 内置 → 本脚本回退）+ MiniMax 扩展（html-video 走的）
- 图像：公共 `siliconflow-img-gen`（collage-broll Gate2 / 封面）
- 素材：公共 `pexels-footage` / `pixabay-footage`（html-video 素材预获取链兜底）
- 设计规范：CP 专属 `design-system-picker`（设计任务前调）
- 工作区初始化：CP 专属 `init-workspace`（设计任务前调，落 `design_assets/`）

#### 2.10 与 main 重构的重复风险复核

| 维度 | main 重构后 | CP 现状 | 重复？ | 处置 |
|------|------------|---------|-------|------|
| 视频生成 AIGC | 公共 `aigc-video-gen` | 公共 `aigc-video-gen`（collage-broll Gate3）+ CP `siliconflow-video-gen` | ✅ 公共部分共享，不重复；CP 专属 siliconflow-video-gen 是另一家平台不合并 | 已落地 |
| TTS | 公共 `siliconflow-tts` | 公共 `siliconflow-tts` + MiniMax 扩展 | ✅ 公共部分共享，不重复；CP MiniMax 是另一条 TTS 路属 CP 范畴 | 已落地 |
| Stock Footage | 公共 `pexels-footage` / `pixabay-footage` | 同 | ✅ 完全共享，不重复 | 已落地 |
| 图像/封面 | 公共 `siliconflow-img-gen` | 同 | ✅ 完全共享，不重复 | 已是公共 |
| 工作区约定 | `output_videos/<topic-en-slug>/` | `design_assets/YYYY-MM-DD-<task>/`（init-workspace）+ `output_videos/<slug>/`（collage-broll 沿 xiaobei 路径契约） | ⚠️ CP 内部两套目录并存——设计任务走 design_assets，视频任务走 output_videos | **不强行统一**——main 用 output_videos，CP 视频也用 output_videos（collage-broll 已如此），CP 设计用 design_assets，各自自洽 |
| 简单剪辑 | main 专属 `extract_and_concat.py` + 去口气词 + 高光剪辑（待写） | CP 无 | ❌ 无重复——CP 不做基于已有素材的轻剪辑 | 已定 4.4 |
| 脚本生成 | main 不出脚本 | CP 范畴（待后续规划） | ❌ 无重复 | 已定 4.1 |

---

## 3. 调研

用户 2026-07-25 钦定 3 条调研原则：

1. **UI 层面完全不看**——只吸收能力，最终落地为 openclaw 的 Skill。被调研项目的 WebUI、API controller、前端组件、CLI 交互等 UI 范式全部跳过，不调研、不借鉴。
2. **大模型/AIGC 模型的 Provider 适配层完全不看**——模型的调用适配统一按上一轮抽出的公共模块（如 `skills/aigc-video-gen/`、`skills/siliconflow-img-gen/`、`skills/siliconflow-tts/`、未来 CP 侧的 llm skill 等）。被调研项目里 `services/llm.py`、`services/voice.py` 的七条 TTS 路径、`services/material.py` 里的 Pexels/Pixabay/Coverr API key 轮转、各种 SDK 适配——**只看算法不抄适配层**。
> - 落地成 Skill 时，调的是本仓已有公共模块，不重新引入被调研项目的 SDK 适配层
3. **重点是看"怎么出脚本"**——尤其是像 MoneyPrinterTurbo 这种素材匹配算法（脚本 → 关键词 → 时长 → 素材挑选）。其余如视频合成技术细节、字幕烧录方式等次之。

### 3.1 MoneyPrinterTurbo

- 一站式 AI 短视频生成工具
- 用户只提供视频**主题**或**关键词**，自动生成：视频脚本 → 匹配素材 → 生成字幕和背景音乐 → 合成高清短视频
- 四种使用方式：AI Agent / WebUI / API / CLI
- 代码按控制器、服务、模型等职责分层（`app/` 目录）
- 调研代码仓一律放：`~/wiseflow-pro/` 下

#### 能力特性（从 README 摘录）

| 能力 | MoneyPrinterTurbo 实现 | 与出发点 1.1 的契合度 |
|------|---------------------|-------------------|
| AI 自动生成视频脚本 | 内置 | ❌ 出脚本归 content-producer，main agent 借鉴时**不能照搬** |
| 自定义脚本 | 支持 | ⚠️ main agent 不出脚本但可接收用户/content-producer 给的脚本？待定 |
| 多种高清尺寸 | 竖屏 9:16 / 横屏 16:9 | ✅ 可借鉴 |
| 批量视频生成 | 一次生成多个挑最满意的 | ⚠️ 与 main agent"逐段确认"工作流冲突，是否借鉴待定 |
| 视频片段时长设置 | 可调素材切换频率 | ✅ 可借鉴 |
| 多语言视频脚本 | 支持 | ❌ 出脚本归 content-producer |
| TTS | Edge TTS / Azure Speech / SiliconFlow / Google Gemini / 小米 MiMo / ElevenLabs / Chatterbox | ✅ 可借鉴备选方案（main agent 当前 tts.py 只接 SiliconFlow） |
| 字幕生成 | 可调字体/位置/颜色/大小/描边/背景 | ⚠️ 当前 main agent assemble.py **不烧字幕**——是否引入待定 |
| 背景音乐 | 随机或指定，可调音量 | ⚠️ 当前 main agent 靠 gen.py 声画同出模型出 BGM，不单独混 BGM——是否引入待定 |
| 本地素材 / Pexels / Pixabay / Coverr | 支持四种素材来源 | ✅ Stock Footage 模式可借鉴（当前 main agent 只有 Pexels + Pixabay） |
| 跨平台发布 | TikTok / Instagram / YouTube Shorts 一键发布 | ❌ 发布归各 publish 技能，不在 video-produce 内 |
| 主流模型接入 | Kimi / Moonshot / OpenAI / Gemini / DeepSeek / 通义千问 / Azure / 火山方舟 / xAI / MiniMax / 小米 MiMo / Cloudflare AI Gateway / 魔搭 / AIHubMix 等 | ⚠️ 视频生成模型当前 main agent 只接百炼 + 火山，文本模型走 agent 本身——是否借鉴待定 |

#### 借鉴判定

**⚠️ 不建议引入到 main**——理由四：

1. **main 不出脚本**——MPT 的批量差异靠"同脚本不同素材顺序"，main 没脚本就没了批量的意义前提。main 的"组装"是用户给定素材清单，顺序由 agent 定，shuffle 反而破坏用户意图
2. **main 走逐段确认**——`compress_preview.py` + SKILL.md 明示"逐段发用户确认"，单产物已是慢流程；批量 N 产物会把每段确认膨胀 N 倍，用户体验崩
3. **声画同出模型无批量差异**——main 的 gen.py 走百炼/火山声画同出，同 prompt 同 seed 出同产物，批量要靠 prompt/shuffle 变；MPT 的素材 shuffle 范式不适用 gen.py 声画同出
4. **"挑最满意"在 main 范式下退化为 review.py**——main 已有 `review.py` 成片自检闸门（ffprobe + 抽帧黑屏扫描 + 音频电平 + 时长分辨率一致性），verdict pass/fail/warn，**这已是"挑"的逻辑**——不及格的修或重，及格的交付。引入"多产物挑最满意"无增量价值

**借鉴结论**：
- ❌ `video_count` 批量机制不引入 main——与逐段确认 + 声画同出 + review.py 范式冲突
- ❌ random shuffle 差异产生不引入——破坏用户素材顺序意图
- ✅ **`_run_pipeline` 的固定阶段链思路可参考**——main 重构时若重写 state.py（已定 4.5 删），可仿此"script→terms→audio→...→final"的阶段定义写 SKILL.md 工作流文（仅参考思路，不抄代码，也不上脚本化状态机——4.5 已定 main 用不上 state.py）

---

## 4. 开放问题与待决项（调研中暴露、需要用户拍板的疑点）

> 这一节是调研过程中暴露的、不在出发点里明示、需要用户决策的疑点。**等调研 todo 全部完成后，统一发起 `request_user_input` 一次性问清**，避免逐条打断。

### 4.1 main agent video-produce 重构后接受"脚本"的边界

**已定（用户 2026-07-25 拍板）**：main agent **不接受任何脚本输入**。出脚本/探讨脚本一律走 content-producer，main agent 顶多在 viral-chaser 之后把活儿转给 content-producer。用户有脚本或需要探讨脚本 → 直接找 content-producer，不经过 main agent。

**落地约束**：
- 重构后 SKILL.md 的输入接口**只接受素材清单**（用户给定的素材、已有素材、或为组装目的经 AIGC/Stock Footage 补的素材），**不接受 script.md 类形态**
- viral-chaser → content-producer 的衔法保持上一轮已改形态，main agent 不在中转脚本
- "脚本规划表"那种东西在 main agent 侧不该出现，重构时连带把寄生在 stages/ 下的 step2-script.md 等砍干净（参见 2.5 节）

### 4.2 AIGC 抽到公共 skills 的命名与边界

**已定（用户 2026-07-25 拍板："你看着起吧"）**：命名由我方自定，按 `skills/` 现有"平台-能力"风格（pexels-footage / pixabay-footage / siliconflow-img-gen）起名。调研 todo F 由此变为"自定命名后备案"，不再作为开放问题阻塞。

落地约定（我方拟）：
- 抽公共的 AIGC 视频生成 skill 命名为 **`aigc-video-gen`**（不绑平台——脚本内含百炼+火山双平台 fallback，绑平台名会误导）
- 与 content-producer 已有 `siliconflow-video-gen` 的关系：`siliconflow-video-gen` 是 CP 侧接 SiliconFlow Wan2.2 的独立实现，调的是另一条 API、另一家平台，**不复用不合并**，保留 CP 侧原样；公共 `aigc-video-gen` 只抽 main agent 当前 `gen.py`（百炼 happyhorse + 火山 Seedance 候选链）

### 4.3 TTS 重复实现去重

**已定（用户 2026-07-25 拍板）**：main agent 的 `scripts/tts.py` 与 content-producer 的 `siliconflow-tts/scripts/tts.py` 是同一份代码——合并抽到公共 `skills/`，并在技能文档里强制写明：

> **优先使用 OpenClaw 内置 TTS 工具**（`tts_generate` 或 agent 内置语音合成能力）。
> OpenClaw 内置 TTS 不可用时，回退到本地脚本（要求环境变量已经配置 `SILICONFLOW_API_KEY`）。

落地约定：
- 公共 skill 命名沿用 **`siliconflow-tts`**（与 CP 侧现名一致，减迁移成本）
- main agent 的 `crews/main/skills/video-product/scripts/tts.py` 删除，改调公共
- CP 的 `crews/content-producer/skills/siliconflow-tts/` 整目录上移到 `skills/siliconflow-tts/`，CP 侧改用公共引用

### 4.4 简单剪辑能力的脚本归属

出发点 1.1 第 3 条提到 main agent 可做"去口气词、高光剪辑、录制操作视频"。

- 已有 `extract_and_concat.py`（剪头/尾/中段+拼接）✅ 覆盖了基础剪辑
- 已有 `ui-demo` 技能 ✅ 覆盖了"录制操作视频"

**已定（用户 2026-07-25 拍板）**："去口气词"与"高光剪辑"都归 **main agent**——它们都属于"用户提供素材后的轻剪辑"，main agent 直接做，**不外发** content-producer。content-producer 主要负责"从头生产一整个工作（视频、视觉等）"，这类基于已有素材的轻剪辑不在 CP 职责里。

**落地约束**：
- 这两项能力属本次重构范围内（不是只调研），开发计划里须列脚本/能力产出项
- "去口气词"——需 ASR（语音转写）+ 口语词检测 + 精定位 + 删除。viral-chaser 已有火山 ASR 调用可借鉴，但目的不同（分析 vs 剪辑），脚本要另写
- "高光剪辑"——需看完整视频、识别高光、抽取拼接。目前无脚本，需另写

### 4.5 state.py 阶段链重构

当前 state.py 的阶段链是 `script → gate0 → calibrate → assets → assemble → review → cover → deliver`，其中前三段（script/gate0/calibrate）都是 content-producer 范畴的事，重构后应砍掉。

**已定（用户 2026-07-25 拍板）**：`state.py` **main agent 用不上**——main agent 不出脚本、不走 Gate 0、不打分定稿，原有阶段链里前三段（script/gate0/calibrate）在 main 侧根本不存在，后五段（assets/assemble/review/cover/deliver）可由 SKILL.md 工作流文字直接表述，不需要脚本化状态机。

**落地约束**：
- `crews/main/skills/video-product/scripts/state.py` 在重构时**直接删除**（CP 侧的完整备份保留，CP 后续规划自己的状态机时可用）
- 不替代、不新写——main agent 视频生产工作流靠 SKILL.md 步骤文表述，不用脚本化 checkpoint
- 调研 todo 里不再为 state.py 列任何项

### 4.6 viral-chaser 与重构后 main agent 的衔接

参见 2.6 节。**已定**：viral-chaser 衔接按上一轮已改形态（viral-chaser 只管出脚本，制作委托 content-producer），main agent 不在中转。本节闭合，不另起开放问题。

### 4.7 封面制作的归属

**已定（用户 2026-07-25 拍板）**：封面制作**各自负责**——main agent 与 content-producer 都是直接调公共 `siliconflow-img-gen`，不额外抽公共封面 skill。具体封面制作要求（必须含标题文字、尺寸、设计感等）各自写在各自的对应技能文档里，不强行统一。

**落地约束**：
- 不抽 `video-cover-gen` 之类的公共 skill
- main agent 的封面要求继续写在 `crews/main/skills/video-product/SKILL.md` 的"制作封面"节
- content-producer 的封面要求由后续 CP 工作流规划时自行撰写（出发 1.3 范畴）
- 调研 todo 里不再为封面归属列任何项

---

## 5. 技能开发规范（强制）

### 5.1 规范正文

**SKILL.md 与 crew 专属 scripts（`crews/<crew>/skills/<skill>/scripts/` 下的脚本注释）是给 crew 看的工作指令**。crew 不知道产品上下游与开发判断——**禁写开发方案的词**：

- **开发判断**——"本轮据调研结论落地"、"决策 4.5 已定"、"范式配套"、"有意的边界"之类
- **产品功能取舍**——"不引入 faster-whisper 与 main stdlib 范式一致"、"用 ffmpeg 不引 moviepy"之类
- **参考来源**——"借鉴 OpenMontage Backlot"、"borrowed from MoneyPrinterTurbo"、"抄 Smart-Cut 的多层检测判据"之类

这些只能写 `docs/`（调研文档、开发计划文档），不能写进技能内。

### 5.2 判据

crew 是执行者，他只需知"调哪个脚本、传什么参数、产物落哪、verdict 含义"，不需知"为什么这么设计、参考了谁、与什么范式配套"。开发判断/取舍/参考来源对 crew 是噪音——既不帮他执行，又可能误导他质疑工作指令。

### 5.3 落地位置

| 内容类型 | 写哪 | 例 |
|---------|------|---|
| crew 工作指令（调脚本、参数、产物、verdict） | SKILL.md + scripts 注释 | "review.py verdict=pass 才交付" |
| 开发判断/产品取舍/参考来源/调研结论 | `docs/` | "MPT 字幕走 faster-whisper，不引入 main" |

---

## 5.5 main 侧落地记录与公共技能依赖（2026-07-26，写给 CP 侧负责人）

> main 侧调整已落地（master commit `30fa4c1`）。本节记录落地形态、video-edit 对公共技能的依赖清单，并答复 §9.1 的疑问。

### 5.5.1 落地形态

- `highlight-cut` → **`talking-head-cut`**（口播/演讲/访谈类轻剪辑，按口播场景重命名；B 类薄 wrapper → `cut_plan.py`）
- `video-product` → **`video-edit`**（定位收敛为"已有素材加工 + 拼接"；首个 C 类分发器 wrapper：`video-edit <extract|assemble|audio-mix|subtitles|frames|apply-cut|preview>`）
  - 新增脚本：`audio_mix.py`（旁白/BGM 混音）、`burn_subtitles.py`（SRT/ASS 烧录）、`sample_frames.py`（带时间戳抽帧，配合 agent 看图写 cut_plan.json 做画面精彩集锦）
  - `apply_cut.py` 从口播技能移入 video-edit（通用"按 cut_plan.json 剪拼"原语，两条集锦流程共用）
  - 已删：`gen.py` / `tts.py`（改引公共技能，见下）、`state.py`（决策 4.5）、`check.py`（随出脚本环节退出 main）
- 公共 `video-review`：补薄 wrapper，`review.py` 兼容单文件入参（原先只认 project-dir，SKILL.md 里的单文件调用是坏的）

### 5.5.2 video-edit 依赖的公共技能清单

| 公共技能 | video-edit 用在哪 | 状态 |
|---------|-----------------|------|
| `skills/aigc-video-gen` | 素材补充：AIGC 生成视频片段（决策 4.2） | ✅ **已抽入 master**（2026-07-26 main 侧从 `f5c99a1` 提取，见 5.5.3） |
| `skills/siliconflow-tts` | audio-mix 旁白：内置 `tts_generate` 不可用时的回退（决策 4.3） | ✅ **已抽入 master**（同上；采用 CP 演进版 tts.py，含 markdown 清洗与 ASR 自检） |
| `skills/video-review` | 成片自检强制闸门 | ✅ 已在 master（本轮补 wrapper + 单文件支持） |
| `skills/pexels-footage` / `skills/pixabay-footage` | Stock Footage 素材补充 | ✅ 已在 master |
| `skills/siliconflow-img-gen` | 制作封面 | ✅ 已在 master |

main 侧 `video-edit/SKILL.md` 与 README 按决策 4.2/4.3 引用 `aigc-video-gen` / `siliconflow-tts` 之名——两者已随 5.5.3 的提取落入 master，引用不再悬空。

### 5.5.3 答复 §9.1：gen.py 没丢，现成抽取成果在分支上

- main 侧本轮**没有**在 master 抽 `aigc-video-gen`——只删了 `gen.py`/`tts.py` 并改为引用公共之名。
- **现成的抽取成果在 `origin/fix/it-engineer-channel-layering` 分支 commit `f5c99a1`**（2026-07-25 更早一轮尝试，未合 master），包含完整的：
  - `skills/aigc-video-gen/`（SKILL.md + `aigc-video-gen.sh` wrapper + `scripts/gen.py`，内容与原 main `gen.py` 同源）
  - `skills/siliconflow-tts/`（SKILL.md + wrapper + `scripts/tts.py`，从 CP 上移版，含"内置 TTS 优先"说明）
- **已落地（2026-07-26，main 侧执行，与 §9.1 闭环）**：`git checkout f5c99a1 -- skills/aigc-video-gen skills/siliconflow-tts` 提入 master。核对结论：`gen.py` 与删除前 main 版本字节级一致；`tts.py` 采用 CP 演进版（markdown 清洗 + 绝对路径支持 + ASR 自检，为原 main 版超集）；两个 wrapper 均为标准 readlink 薄转发；已清理 SKILL.md/wrapper 内的 GLM 乱码字（嫗选链/荛围/谰火山等）与旧 `video-product`、A.1/A.3 阶段编号引用，siliconflow-tts 示例改 PATH 风格。
- **留给 CP 侧核对**：CP 侧 7 处 `aigc-video-gen` 引用与 `collage-broll` Gate3 调用形态是否与公共 SKILL.md 的 `aigc-video-gen <flags>` PATH 风格一致；`crews/content-producer/skills/siliconflow-tts/` 按决策 4.3 应删除本地副本改引公共（main 侧未动 CP 目录）。

另：§9.2 提到的 main 侧 `video-assembler` 目录是 f5c99a1 那轮的旧名残留（仅剩 gitignore 掉的 `__pycache__`，master 从未采用），已清理删除，勿按其做判断。

---

# 第二部分：content-producer 侧调研（2026-07-26）

> 以下 §6–§8 由 content-producer 侧负责人撰写。main 侧调整同期由另一路进行，两侧不改对方章节。
> 调研范围仍受 §3 三条钦定原则约束：**不看 UI、不看 Provider 适配层、重点看"怎么出脚本"**。

## 6. 四项目能力调研

### 6.0 调研对象与代码仓位置

| 项目 | clone 位置 | License | 定位一句话 |
|------|-----------|---------|-----------|
| OpenMontage | `~/wiseflow-pro/OpenMontage` | **AGPLv3** | agent-first 制片流水线：12 pipeline / 52 tool / manifest+stage-director 治理 |
| ViMax（HKUDS） | `~/wiseflow-pro/ViMax` | MIT | 学术派 agentic 视频生成：脚本→分镜→机位树→一致性→AIGC 出片 |
| HyperFrames（HeyGen） | `~/wiseflow-pro/hyperframes` | Apache-2.0 | HTML→MP4 确定性渲染引擎 + 19 个 agent skill |
| html-video（nexu-io） | `~/wiseflow-pro/html-video` | Apache-2.0 | 引擎之上的 meta-layer：素材+意图 → content-graph → HTML 分镜 → MP4 |

> 备注：`~/wiseflow-pro/html-video` 的 origin 是 `bigbrother666sh/html-video`（用户 fork），不是 nexu-io 上游；本轮读的是 fork 的 `main`（HEAD `90a036a`）。`~/wiseflow-pro/OpenMontage`、`html-video` 本轮之前已 clone，`ViMax`、`hyperframes` 本轮新 clone（`--depth 1`）。

---

### 6.1 OpenMontage — 制片治理层

#### 6.1.1 架构（三层知识结构）

```
Layer 1  tools/ + pipeline_defs/*.yaml     "有什么"——可执行能力 + 编排
Layer 2  skills/**.md（156 个）             "怎么用"——本项目的约定与质量线
Layer 3  .agents/skills/（84 个目录）        "它怎么工作"——外部技术知识包
```

**没有代码 orchestrator**——agent 本身就是 orchestrator。Python 只提供工具与持久化，所有创作决策/编排逻辑/评审标准都在可读的 YAML manifest + Markdown skill 里。这与本仓 skill 范式完全同构，是最值得整体借鉴的一点。

#### 6.1.2 pipeline manifest 的字段设计（可直接映射到我们的 stages/）

12 条 pipeline 共用同一套阶段链：`research → proposal → script → scene_plan → assets → edit → compose → publish`。每个 stage 在 manifest 里声明：

| 字段 | 含义 |
|------|------|
| `skill` | 该阶段的"导演技能"文件路径 |
| `produces` | 本阶段产出的 artifact 名 |
| `required_artifacts_in` / `optional_artifacts_in` | 前置依赖 artifact |
| `tools_available` / `required_tools` / `optional_tools` | 本阶段允许调的工具白名单 |
| `checkpoint_required` | 是否必须落 checkpoint |
| `human_approval_default` | 是否必须人工批准才能进下一阶段 |
| `review_focus` | 评审要看的点（自然语言清单） |
| `success_criteria` | 可判定的通过条件（schema 有效 / 数量下限 / 误差范围） |
| `sub_stages` + `condition` | 条件子阶段（如 reference-driven 才跑 sample 试片） |

顶层 `orchestration` 段还声明 `budget_default_usd` / `max_revisions_per_stage: 3` / `max_send_backs: 3` / `max_wall_time_minutes: 20`——**给 agent 的返工与耗时上限**，这是我们目前完全没有的东西。

#### 6.1.3 stage-director 技能的固定骨架

每个 `<stage>-director.md` 都是同一骨架，可作为 CP `stages/*.md` 的模板：

```
When to Use            —— 我是谁、我拿到什么、我产出什么
Prerequisites 表       —— Schema / 前置 artifact / playbook / Layer3 技能，四列
Process 分步           —— Step 1..N，每步带表格化判据
Self-Evaluate          —— N 维自评打分，任一维 <3 必须返工重写
Submit                 —— 调哪个函数落盘校验
Common Pitfalls        —— 反面清单
Gate Reminder (Binding) —— 闸门提醒（见下）
```

**Gate Reminder 的措辞值得整段照搬语义**：本阶段需人工批准 → 评审通过后落 `status="awaiting_human"` checkpoint、呈现摘要、**然后结束本轮回复，不许在同一条回复里开始下一阶段**；并且**批准是逐闸门的，早先的一句"你继续"不覆盖本闸门**。这一条正是我们的 crew 最容易违反的行为。

#### 6.1.4 script-director：出脚本的可量化判据（★ 最高优先吸收）

- **叙事弧的时间预算**：`HOOK 0–5s`（问题/大胆断言/反直觉事实；**禁**"在本视频中我们将学习…"、**禁**"大家好，欢迎回来…"）→ `SETUP 5–15s`（造知识缺口，让观众**必须**要答案）→ `BUILD`（递进揭示，用 "therefore / but" 转折而**不是** "and then"——South Park 规则）→ `CLIMAX`（"啊哈"时刻，兑付 SETUP 埋的缺口）→ `LANDING 最后 5s`（复述核心 + CTA，**不许**在这里引入新信息）。
- **词预算表**（中文脚本需按字数重标定，但方法论直接可用）：

| 语速档 | wpm | 用在 |
|--------|-----|------|
| Conversational | ~150 | 默认 |
| Contemplative | ~120 | 复杂题材，需要留处理时间 |
| Energetic | ~180 | 短视频、高能量 |
| Technical | ~130 | 代码走查、架构深潜 |

  30s→65–75 词 / 60s→130–150 / 90s→195–225 / 120s→260–300。**超预算 20% 必须狠砍**——理由写得很实：TTS 语速是固定的，写多了要么语音赶要么成片超时。

- **enhancement_cues（视觉指令）六型 + 密度规则**：`overlay`（术语/定义/标签）/ `diagram`（流程、架构）/ `stat_card`（惊人数字或对比）/ `animation`（必须靠运动才能懂的概念）/ `code_snippet` / `broll`（真实世界情境）。**每 8–10 秒至少一条**，60 秒视频至少 6–8 条；判据是"视觉不变观众就走"。
- **结构化 TTS 交付指令**：不写散文式 `speaker_directions`，而是写 `delivery_cues` 对象：`pace` / `energy` / `emphasis_words[]` / `pause_before_seconds` / `pause_after_seconds` / `delivery_note` / `provider_text`（内嵌 SSML `<break time="0.6s"/>`）。硬规则：**每个口播段至少给两条具体 cue**；**只写 TTS 真能实现的指令**——"边笑边说""看向镜头""手指屏幕"这类一律禁止。
- **`pronunciation_guides`**：技术词/缩写/外来词给音标（`{"word":"FAISS","phonetic":"FACE"}`）。中文场景对应的是多音字、英文缩写读法、专有名词读法。
- **自评 8 维**：Hook 力 / 字数准确度 / 叙事流（是 therefore-but 还是 and-then）/ 视觉指令密度 / 语音表演明确度 / 术语管理 / 高潮兑付 / CTA 具体性。
- **反面清单**里最狠的一条：**字数超标是第一号失败模式**。

#### 6.1.5 documentary-montage：素材检索匹配算法（★ 远超 MoneyPrinterTurbo）

这是 §3 原则 3 点名要看的"素材匹配算法"的最佳答案。分两条路：

- **Fast path（推荐，≤30 slot / 逐幕生产）**：`direct_clip_search` 多 provider 并发搜 + 每条 query 下 2–3 条片 → 看缩略图人工核对 → 手工映射 slot。无 CLIP embedding、无 corpus 索引。
- **Standard path（50+ slot）**：`corpus_builder` 建带 CLIP embedding 的检索索引 → `clip_search.rank_for_slot` 逐 slot 排序取胜者。

**scene-director 侧（写 slot 的一方）的可抄判据**：

| 调性 tone | 平均 hold | 每 60s 的 slot 数 |
|-----------|----------|------------------|
| elegiac 挽歌 | 4.0s | ~15 |
| reverent 庄重 | 3.5s | ~17 |
| dreamlike 梦幻 | 3.0s | ~20 |
| wry 戏谑 | 2.0s | ~30 |
| urgent 紧迫 | 1.2s | ~50 |

- 结构（shape）四型：`list`（N 个等长 slot 无拐点）/ `before-after`（N/2 + 1 个 pivot + N/2）/ `three-act`（30% setup → 40% turn → 30% release）/ `single-image expansion`（1 锚图 + N 变体）。**先把 slot 数算出来再写第一个 slot。**
- **slot description 模板**：`<主体>, <动作/姿态>, <环境>, <光线>, <年代/质感提示>`。禁情绪词、禁意图动词。判据一句话：**"你要是想不出一张具体的照片，CLIP 也想不出。"**（反例："回家的感觉" / "一个温暖的时刻" / "某人象征性地穿过门"；正例："一个女人静立在门廊上，手靠近门把，午后散射光，浅景深"）
- **description 与 query 是两个职责，必须分开写**：description 是喂 CLIP 排序的语义长文本；query 是喂 stock API 的搜索短语，**5 词以内**，每 slot 写 2–3 条：literal（最直白的搜索词）/ lateral（同一想法换角度或换尺度）/ association（相邻概念，只给 hero slot 写）。
- **hero slot**：每条片子必有 2–3 个全片依赖的 slot（开场镜、转折镜、收尾镜），标 `hero: true`，享受更长 hold、更大候选池（k=30 而非 k=12）、3 条 query。
- **留余量给下游**：把 slot 描述写到"能让研究助理在电话里认出来，但松到还能让你惊喜"——如果既定死了描述又定死了具体片子，就是把下游的创作选择权提前吃掉了。

**asset-director 侧（挑素材的一方）的可抄判据**：

- 心智模型三条：**先建后挑**（不许对不含该 query 家族候选的 corpus 做排序）；**只增不换**（corpus append-only，检索弱就加 query 重建，不推倒重来）；**按 slot 挑不按片挑**（用 `exclude_ids` 全局累加，防同一素材占两个坑）。
- corpus 规模：**slot 数的 8–12 倍**（15 slot 的片子要 ~150 候选）。`per_source` 每 query 4–8 条足够，20+ 只增噪音。
- **建完先体检**（`operation=stats`），三种失败模式：`rows < 50` 太小要长；`per_source` 严重偏斜（如 vintage 命题里 98% 来自现代图库）要定向补；**`mean_motion_score < 1.0` 说明全是静态片，成片会像幻灯**。
- **CLIP 余弦阈值（ViT-B/32）**：`≥0.30` 强匹配可用 / `0.22–0.30` 需人判 / **`<0.22` 不许硬挑**——改写 query、定向补 corpus、重排，**每 slot 最多两轮**；三轮还上不去 0.22 就报告"开放素材库里拍不到"，请用户改 slot 或自供素材。
- `tag_weight=0.3`：视觉 embedding 70% + 来源标签 embedding 30%；图库标签强而画面噪时提到 0.5，标签是长散文（如 Prelinger 档案）时降到 0.15。
- **按判断挑不按分数挑**——四个维度压过分数：年代契合 / 运动契合（片长撑不住目标 hold 就不能用）/ 相邻构图（slot_02 是雨中屋顶全景，slot_03 首选也是雨中屋顶全景，就取第二名）/ **情绪语域（0.42 的分数压不过调性错位——挽歌命题里塞进霓虹拉斯维加斯是错的）**。
- `diversify(diversity=0.5)` 对时间线顺序的入选列表做冗余检查：被丢掉的说明有两个 slot 视觉上是双胞胎，把被丢的那个 slot 带 `exclude_ids` 重排。
- **`rejected_picks` 必须落盘**（slot_id + clip_id + score + reason），下游剪辑阶段觉得某个 pick 不对时靠它直接取第二名。
- **provenance 是发布环节的不可谈判项**：每条片必带 `provider` / `original_url` / `license`。
- **儿童/童话内容的 source override**（很实用的一条经验）：`sources` 锁定 `pixabay_video` 单源——因为 Pixabay 社区库里有海量 Midjourney/SD 工作流产出的 AI 奇幻动画（发光森林、魔法生物），对儿童留存**显著优于真实素材**；并且**禁止真实素材与奇幻素材混用**（风格冲突会破坏沉浸感），"哪怕 CLIP 分更高也要拒"。附一张 10 行的 query 改写表（`garden flowers morning` → `enchanted fairy tale garden glowing magical`）。找不到就换奇幻关键词再试两轮，仍空则报给用户，**不许静默换成真实素材**。

#### 6.1.6 两个质量闸门算法（★ 高优先吸收，我们现有 review 只覆盖技术层）

**（a）slideshow_risk —— 六维幻灯风险打分（在 compose 之前跑，评的是"计划"不是"成片"）**

六维各 0–5 分，**分越低越好**：`repetition`（版式/背景/镜头语法重复）/ `decorative_visuals`（画面在装饰而非表意）/ `weak_motion`（有运动但无叙事目的）/ `weak_shot_intent`（没写为什么这么取景）/ `typography_overreliance`（太多段落是文字优先）/ `unsupported_cinematic_claims`（宣称电影感但结构不支撑）。

均值判定：`<2.0 strong` / `<3.0 acceptable` / `<4.0 revise` / **`≥4.0 fail——不许进 compose`**。

具体扣分判据（可直接搬成我们的检查项）：同一 scene type 占比 >70% 记 +2.0；描述去重率 <60% 记 +1.5；同一 shot size 占比 >60% 记 +1.5；`text_card/stat_card/kpi_grid` 类占比 >60% 直接给 4.0 并判"这视频就是会动的幻灯"；有运动但没写 `shot_intent` 的镜头占比 >50% 记警；宣称 cinematic 却零 `hero_moment`、或有运动的镜头 <30%、或定义了打光的镜头 <30%，每条 +1.8。

**（b）delivery_promise —— 交付承诺分类与锁定（防"静默降级"这个最伤的失败模式）**

八类承诺，每类三条规则：

| promise | 允许静图兜底 | 要求视频生成 | 最低 motion_ratio |
|---------|------------|------------|------------------|
| motion_led | ❌ | ✅ | **0.70** |
| source_led | ✅ | ❌ | 0.30 |
| data_explainer | ✅ | ❌ | 0.00 |
| teacher_explainer | ✅ | ❌ | 0.00 |
| screen_demo | ✅ | ❌ | 0.00 |
| avatar_presenter | ❌ | ✅ | 0.30 |
| hybrid | ✅ | ❌ | 0.20 |
| localization | ✅ | ❌ | 0.00 |

**最关键的判据（我们必须抄）**：计算 `motion_ratio` 时，`text_card / stat_card / chart / bar_chart / line_chart / pie_chart / kpi_grid / comparison / progress / callout` 这一类归为 **"动画幻灯"（slide grammar），不计入真实运动**；只有 `video / animation / avatar` 与 `.mp4/.mov/.webm/.avi/.mkv` 素材算真实运动。也就是说——**"给静图加转场"不算动态**。

流程约束：**promise 在提案期确定并锁定**；compose 期兑付不了必须**停下来问**，不许静默替换。用户没显式批准 `still_led` 兜底时，非运动素材过半即判违规。

#### 6.1.7 其余值得记的机制

- **reference-driven 创作**（贴一条你喜欢的片子作为起点）：分析 transcript / 节奏 / 场次 / 关键帧 / 风格 → 输出 2–3 个**差异化**概念 + 诚实的工具路径 + 目标时长下的成本估算 + **一段 10–15 秒试片**，然后才进全量生产。回答用户的是"保留了什么（节奏/钩子/结构/调性）、改变了什么（题材/视觉处理/角度/口播方式）、要花多少钱、用现有工具实际会长成什么样"。
- **提案期给 3 个概念选项**（结构/钩子/受众必须真的不同）+ **逐项列明的成本估算** + **不同价位的备选生产路径**，并明确"质量/成本的权衡摊开给用户看"。
- **决策审计链**：provider 选择、风格/playbook 选择、音乐、音色、渲染 runtime、任何 fallback 或降级，全部记录**考虑过的备选 + 置信度 + 理由**，跨阶段累积。
- **预算治理四步**：`estimate`（执行前估）→ `reserve`（调用前锁额）→ 执行 → `reconcile`（记实际花费）；三种模式 `observe`（只记）/ `warn`（超了记日志）/ `cap`（硬上限）；单动作超阈值（默认 $0.50）暂停确认；总预算默认 $10。
- **source media inspection**：用户自供素材必须先逐文件 probe（分辨率/编码/声道/时长）并写出对计划的影响，**禁止凭文件名臆测内容**。
- **7 维打分选型器**（任务契合 30% / 输出质量 20% / 控制力 15% / 可靠性 15% / 成本效率 10% / 延迟 5% / 连续性 5%）——按 §3 原则 2，**Provider 适配层不吸收**，但"用加权打分 + 记录落选者"这个**决策方法**可以用在"三条路径怎么选"上。

---

### 6.2 ViMax — 生成内核层（★ "怎么出脚本"的主力参考）

#### 6.2.1 三条工作流与 DAG

`idea2video`（模糊想法）/ `script2video`（明确剧本）/ `novel2video`（长篇小说改编）+ `AutoCameo`（用户照片入戏且保持一致）。

```
idea2video:  input_idea → project_brief → characters → script → storyboard
             → shot_decomposition → camera_tree → frame_prompts → keyframes
             → video_clips → final_video
script2video: input_script → characters → storyboard → ...（同上）
novel2video:  novel_text → compressed_novel → events → relevant_chunks
             → scenes → global_characters → scene_scripts
```

#### 6.2.2 出脚本：intent router + 三套档位化脚本模板（★★ 最该吸收）

先用一次 LLM 调用把想法**路由**成三类，再套对应的 system prompt（各带专属 guidelines + 长 few-shot 实例）：

| 档位 | 判据 | 该档位的核心 guidelines |
|------|------|----------------------|
| **narrative** 叙事 | 以人物、情节、主题、对白为中心 | 三幕结构、人物弧（动机/缺陷/成长）、视觉化叙事、情绪节拍、悬念递进、对白自然且推进情节；对白格式 `Name says: "…"`，**禁 voiceover 格式** |
| **motion** 动作 | 以动作、速度、载具、格斗、编排、体育为中心 | **技术精确性**（反复重述"two seats F-18""前座/后座"，宁冗余不含糊，读起来像技术手册）、**动能清晰**（轨迹/矢量/加速感/受力结果）、**空间一致**（谁在哪、怎么移动过去的）、**可分镜的节拍序列**、对白极简、**默认最多出现 1 个角色**、少人物特写多外景 |
| **montage** 蒙太奇 | 以一串镜头靠意象/节奏/并置传达情绪弧为中心 | 情绪弧要有升级或解决且写明每次变化的**成因**、每场写多镜以强化蒙太奇、**总量不少于 500 词且每段不超过 50 词**、纯段落体、声音设计稀疏精确、只在情绪转折处给对白、**限制复杂外部动作**、只写影响或揭示情绪的细节 |

**三档共有的硬约束（反复强调到三次）**：

1. **`No metaphors allowed!!!`**——并给出具体反例（"一阵风穿过它，像幽灵的触碰"、"一辆看起来不像车更像被剥掉机翼的战斗机的 F1"）。
2. **不许在脚本里写机位/剪辑术语**（`cut to`、`close-up`）——"用分镜描述来写，不要用机位视角来写"。机位是后面 storyboard 阶段的事。
3. 对白必须用 `:" "` 引号格式，每句**不太短也不太长**。

#### 6.2.3 出脚本：两段式 + 润色专家

- `develop_story`（idea → 故事）：输出结构固定——故事标题 / **显式复述"本故事面向〈受众〉，属〈类型〉"** / 100–200 词一段式梗概（含核心情节、中心冲突、结局）/ 主要人物简介 / 全文叙事（未指定场次则按"起-承-转-合"自然分段；指定 N 场则分 N 个带小标题的场次且各场篇幅相对均衡）。守则里有一条很实用：**Show, Don't Tell**（"他握紧拳头，指甲深陷掌心"而不是"他很愤怒"）。
- `write_script_based_on_story`（故事 → 分场剧本）：**场次划分原则 = 同一时间 + 同一地点**，时间或地点一变就新起一场；每场必须是一个连续的戏剧动作单元且有独立冲突或推进。"**所有描述必须是可拍的**"——用具体动作代替抽象情绪（"他转过身避开眼神接触"而不是"他感到羞愧"）。
- `script_enhancer`（润色 + 连续性专家）——两条极具工程价值的规则：
  - **为精度允许冗余**："重要对象/人物/座位反复重述以消除歧义，**准确性优先于文气，冗余是可接受的**"；禁用简称（除非已在该位置点名过，否则不许写"the pilot"）。
  - **每次对白都重复角色的音色描述**（`SLING (male, late 20s, Texan accent softened by military precision…)`）——这是为了让下游 TTS/声画同出模型每段都拿到一致的音色约束。**这正好解决我们"声画同出音色漂移"的老问题。**

#### 6.2.4 分镜与一致性机制（★★ CP 的 AIGC 路径可直接吸收）

**（a）storyboard_artist.design_storyboard — 一场剧本 → 镜头表**

- 每个镜头必须有明确叙事目的（建立环境 / 展示人物关系 / 呈现反应）。
- **机位复用规则**：设计新镜头时先想能否用已有机位拍；只有 shot size、角度、焦点**显著不同**才新增机位；**某机位一旦发生大幅运动，此后不可再复用**。
- 角色名在视觉描述里用尖括号 `<Alice>`，在对白和 speaker 字段里不用尖括号。
- **必须写明元素在画面中的位置与朝向**（"A 在画左，面朝右，身前有张桌子，桌子略偏画面中心左侧"）；**不许描述看不见的元素**（门关着就不许写门后的人）；镜头对着人物时要写清焦点在哪个身体部位。
- 安全内容：用声音或暗示替代，敏感元素做替换（番茄酱代血）。
- 每镜每角色**最多一句台词**，每句台词对应一个镜头。
- **每个镜头描述必须自包含，不得互相引用。**

**（b）decompose_visual_description — 一条镜头描述拆三件（★ 直接对应我们的 i2v 能力）**

拆成 **首帧静照 / 尾帧静照 / 运动描述**：

- 首尾帧必须是**纯快照**——"他正要站起来"不合格，要写"他坐在椅上，微微前倾"。
- 运动描述里必须区分**摄影机运动**（dolly / pan / zoom，用专业术语）与**画面内元素运动**。
- **运动描述里不许用角色名，必须用外观特征指代**：`"Alice 在走"` 不合格，要写 `"Alice（短发、绿裙）在走"`——因为 i2v 模型不认名字只认画面特征。
- 尾帧必须与首帧 + 运动描述逻辑自洽（运动里说的动作都要在尾帧静照里体现）。
- 第一个镜头必须用尽可能广的视角建立整体环境；**机位数量尽可能少**。
- **`variation_type` 三档 + `variation_reason`（成本/质量的判据化决策）**：
  - `large`：构图与焦点剧烈变化（如全景平滑推到特写、无人机穿城），通常伴随大幅机位运动；
  - `medium`：新角色入画、角色从背面转为正面（面向镜头）；
  - `small`：表情变化、既有角色的移动与姿态变化（走/坐下/起身）、中等机位运动（pan/tilt/track）。
  - **落地规则：`small` 只生成首帧走单图 i2v；`medium`/`large` 生成首帧+尾帧走首尾帧插值。** 这条直接决定我们每个片段调 `aigc-video-gen` 时是传 1 张还是 2 张图。

**（c）camera_tree — 机位树 + 跨机位连续性（★ 最巧的一招）**

- 把同 `cam_idx` 的镜头归组成 Camera，再让 LLM 判定每个机位的**父机位**（父画面尽可能包含子画面），输出 `parent_cam_idx` / `parent_shot_idx` / `reason` / `is_parent_fully_covers_child` / **`missing_info`（子镜头里父镜头没覆盖到的元素，如"Alice 的正面"）**。
- 判据：**宁近勿远**（Wide→Medium→Close-up；**禁全景直接跳特写**，除非万不得已）；父子的 shot size 尽量相近；时间邻近（父镜头 index 尽量靠近子机位的首镜）；无环；**只允许一个根，且第一个机位必须是根**；没有更广视角时取"重叠视野最大/信息重叠最多"的镜头当父，正反打互为父子时取 index 小的当父。
- **新机位首帧不是从零生成的**：拿父机位首帧 + prompt "两个镜头，之间是 cut to，两镜风格须一致" 生成一段**转场视频**，再用 PySceneDetect `ContentDetector` 切场、取**第二段的首帧**作为新机位画面（切不出第二段则退化为取转场视频的最后一帧）。然后把这张图作为"构图与背景正确但部分元素错误"的主参考，配合角色三视图把 `missing_info` 里的元素替换掉，**并明确要求不许改背景**。
- 代码层还做了**成环校验与自环校验**（会导致帧生成死锁），校验失败即 raise 让上层重问。

**（d）角色一致性**

- `character_portraits_registry`：每个角色生成 **front / side / back 三视图**作为身份锚点；side/back 由 front 编辑生成，失败则**回退复制 front** 而不是让整条流水线崩；**画外音等不可见角色不生成三视图**（对着没有外形描述的角色要三视图会反复失败）。
- `CharacterInScene` 把特征拆成 **`static_features`（脸部/体型，跨场不变）** 与 **`dynamic_features`（服装配饰，逐场可变）** + `is_visible`。
- 跨场/跨事件融合：同一人不同名要合并成唯一 id 并记 `active_scenes: {场次 → 该场用名}` 映射；**同名但特征差异大（童年 vs 成年）必须拆成两个角色**（"意味着需要两个演员"）；带完备性校验——不许漏、不许多、索引越界即重试。
- `best_image_selector`：多候选图三轴择优——**Character Consistency**（性别/族裔/年龄/五官/体型/外形/发型 7 项）、**Spatial Consistency**（左右位置/布局/透视，"参考图里 A 在左 B 在右，生成图不许反过来"）、**Description Accuracy**；附加"优先选没有白边/黑边/额外画框的"。

#### 6.2.5 工程化机制（★ 直接解决我们"要不要状态机"的问题）

- **artifact-file-as-checkpoint**：每一步先查产物文件是否存在，存在就 load 并打印 `🚀 Loaded … from existing file`，不存在才生成并落盘。产物清单：`characters.json` / `story.txt` / `script.json` / `storyboard.json` / `shots/<i>/shot_description.json` / `camera_tree.json` / `shots/<i>/first_frame.png` / `shots/<i>/last_frame.png` / `shots/<i>/*_selector_output.json` / `shots/<i>/video.mp4` / `final_video.mp4`。
  → **天然可恢复、可断点重跑、可人工改 JSON 再续跑，比脚本化状态机轻得多。** 这正是 §4.5 判 main 不需要 `state.py` 之后，CP 侧应该采用的形态：**用产物文件的存在性当 checkpoint，不引状态机脚本。**
- **`plan_text_artifacts()`——只跑到文本产物为止**（characters / storyboard / shot_descriptions / camera_tree），**在任何付费生成之前停下**，让 agent loop 暂停给用户审。这是"闸门"的最自然实现：闸门 = 一个只产出文本的函数边界。
- **LLM 输出校验即重试**：角色索引越界、机位树成环、返回列表长度与机位数不符 → 直接 raise，让 `tenacity` 重问（camera_tree 还会删掉坏缓存文件再重试一次）。
- **依赖编排**：帧生成任务与视频生成任务同时起，视频任务 `await` 对应帧的 `asyncio.Event`；被其他机位依赖的镜头进 `priority_tasks` 先跑。
- **agent 侧硬约束（`prompts/agent.md` 全文只 4 行，值得整段学）**：
  > 除非有 tool result 或 `.working_dir` 状态**证明**，不许声称 planning / render / 文件改动发生过；不许声称 render 已开始，除非渲染工具报告了 started 或 completed。
- **`prompts/workflow.md` 的闸门写法**：调任何 planning tool 之前，用户必须**明确指名**跑哪条 workflow；"做个短片""帮我策划个脚本"这类**不算确认**，必须先问一句；**起草/讨论脚本属于对话协助，不许调 tool**；起草完要用户确认那份脚本才能进 `script2video`；`idea2video` 默认**小规模**（1 场 3–5 镜），**不许把模糊想法擅自扩成多场多镜**；产物目录必须落在会话目录下，禁止读写根级目录。

---

### 6.3 HyperFrames — 渲染引擎层 + skill 组织范式

#### 6.3.1 引擎本体

- composition 就是**一个 `index.html`**：DOM 用 `data-*` 声明时序（`data-composition-id` / `data-start` / `data-duration` / `data-track-index` / `data-volume` / `data-width` / `data-height`）+ `class="clip"`；动画用 GSAP/CSS/Lottie/Three.js/Anime.js/WAAPI 任一，通过 **frame adapter 变成 seekable**；媒体播放由框架接管。
- 渲染 = headless Chrome **逐帧 seek** + ffmpeg 编码 ⇒ **同输入同输出（确定性）**，适合 CI 与回归测试。无 build step，`index.html` 直接能在浏览器里播。
- 与 Remotion 的差异（其 README 自陈）：authoring 是 HTML 而非 React；无需打包；agent 交接是纯 HTML 文件而非 JSX 工程；库时钟动画天生 seekable；Apache-2.0 而非 source-available。

#### 6.3.2 skill 三层架构（★★ 对 CP 最有价值的部分）

**1 个 router + 10 个 creation workflow（按需安装）+ 8 个 domain skill（按需加载）**，19 个 skill 一共 ~39K 行。

- **router `/hyperframes`**（仅 109 行，是"必读入口"）：
  - **§1 从项目状态起手**——一张表，**首个匹配行即执行，不再评估下面的行**：显式 port Remotion / 对已有项目的具体操作（inspect/validate/preview/render/publish）/ 对已有项目的具体编辑 / `BRIEF.md` 已存在 / 有 `hyperframes.json` 或 `STORYBOARD.md` / 全新创作。每一行都明确"跳过意图访谈"或"跑意图访谈"。
  - **§2 路由表按 priority 1–10 匹配**，且**匹配的是"请求的交付物"，不是顺口提到的某个词或文件类型**。每条路由有一个独立的 `references/routes/<workflow>.md` 记录 input/output/trigger 契约，**候选不满足契约就继续往下匹配，不许硬凑**。
  - **专门一节"消歧"**：短动效 vs 通用视频、URL 来源该走哪条、已有素材加字幕 vs 加设计信息卡、音乐当床 vs 音乐驱动节奏、"我要 storyboard" 改的是评审流程不是 workflow、超长片一律落 general-video。
  - **§3 路由一次就走**：意图访谈结尾**写 `BRIEF.md`，`BRIEF.md` 是 workflow 唯一读的路由产物**，之后不再回 router；"后面任何'路由当初要求了什么'的问题，一律从 BRIEF.md 回答"。
  - **§5 domain skill 按需加载表** + 一句硬规则：**"domain skill 永不接管端到端交付物，只加载当前 workflow 需要的。"**
  - **版本自愈**：项目 `package.json` 里 pin 了 CLI 版本，恢复项目时先跑一次只读探测 `upgrade --project . --check`；落后就升级并用 `check` 验证；**升级绝不静默**（要在本轮总结里点名旧版号和新版号）；check 失败就回滚并说明留在哪个版本、为什么。
- **`/media-use`（Agent Media OS，151 个文件）——最该吸收的抽象**：
  - **一个动词 `resolve`**：`--type <bgm|sfx|image|icon|logo|voice|grade|lut> --intent "<描述>" --project <dir>`，返回**一行** `resolved <id> → <path> (<type>, <metadata>)`；**所有检索噪音留在磁盘上，不进 agent 上下文**。
  - 新建之前先 `--candidates` 列出可复用资产**自己判断契合度**——跨项目资产复用 + ledger 记录。
  - `logo` 有明确降级链 `svgl → simple-icons → GitHub avatar → favicon`，且**永不重绘**。
  - **"media opportunity pass"（主动提议，但有严格纪律）**：只在检出**具体信号**时提——有字幕/文案但无配音 → 提 TTS；emoji 或用 `<div>` 假装图标 → 提换真图标；占位图/过小/明显放大过的图 → 提换图或升采样；硬切转场无音效 → 提转场音效；超过 ~10s 无音乐床 → 提 BGM；曝光/色偏 → 提校正；照片类素材观感平淡或跑题 → 提一个具体的预设或定制处理；有意义的媒体入场却很死 → 提一个 seek-safe 的入场处理。纪律四条：**有信号才提（不许泛泛而谈）**、**给具体方案带默认值让人选 all/some/none**、**一个项目只问一次**（说了"就这样"就别再提）、**只提议不静默改**——尤其调色，一次"灰世界校正"会毁掉刻意的夕阳或霓虹。
  - 反面清单：不要为了记录曝光/阴影/对比/暖调而生成 `.cube` LUT（LUT 只在用户自带或所选处理本身拥有它时才用）；不要用 CSS/SVG overlay 重造引擎已支持的 vignette/grain/blur/pixelate（会绕过 Studio 控件与规范的预览/渲染 shader 路径）。
- **`frame.md`**：每个品牌都有 `design.md`，但没有一份是为镜头写的。`frame.md` 是缺失的**翻译层**——把面向网页的设计规范**为画框反转**：同样的 token、同样的规则，但重写成"agent 不用猜比例、不去抓网页 chrome"的形态，输出是 `DESIGN.md` 的超集。原子（色彩/字体等）神圣不可动，组合自由，**数值来自脚本**。仓里带 12 套 frame-preset，每套 ~280 行 `FRAME.md`。
  → **这与 CP 现有 `design-system-picker`（14 套网页设计系统规范）正好互补**：我们现在挑到的是"网页设计规范"，缺的恰恰是"为镜头反转"这一层。
- **CLI dev loop**：`init / lint / check / snapshot / preview / render / publish / doctor`，另有 `keyframes` 诊断（对**已渲染出来的运动**做诊断）。这条"先 lint 再 check 再 preview 再 render"的顺序是我们 html-video 路径应当照抄的执行纪律。

---

### 6.4 html-video — 创作链路层（本仓 CP 已有同名技能）

#### 6.4.1 定位与竞品判断

**引擎之上的 meta-layer**：一个 `render(input, ctx)` 适配器契约，任何后端满足即可接入；加一个引擎，**所有模板、所有 agent、整套 studio 工作流免费获得**。当前 HF 是唯一已 shipped 的 adapter（headless Chromium 录制 + ffmpeg libx264），Remotion / Motion Canvas / Revideo / Manim 在路线图上（`packages/adapter-remotion` 目录已存在但未完成）。

其 `research/2026-05-26-competitive-landscape.md` 已用 GitHub API 核过数据，结论：HTML→Video 赛道**真竞品只有四个**——HyperFrames（21,297★ / Apache-2.0）、Remotion（~21K / source-available，4 人以上公司付费）、Motion Canvas（~16K / MIT / 作者明确不做服务端渲染）、Revideo（3.7K / MIT / Motion Canvas fork + 服务端渲染 API）；其余所谓 alternative（rendiv / open-motion / htmlrec / clawmotion / frameforge / reelgen，★ 都是个位数到几十）**全是个人 toy 项目，没有用户基础**。

#### 6.4.2 护城河 = asset-to-storyboard 创作链路

一句判断很关键：**HF / Remotion / Motion Canvas 都假定用户是开发者、已经知道自己想做什么；html-video 假定用户只有素材 + 一句话意图。**

两段式工作流（RFC-04）：

```
Stage 1 资产上传   用户: N 张图 + 文字段落 + 数据表 + 音频(可选) + 一句话意图 → AssetBundle
Stage 2 分镜生成   agent: 按意图+资产 选模板、编排 scenes → Storyboard（一组 HTML 分镜 + scene metadata）
Stage 3 分镜审核   用户: 浏览器里逐 scene 看，inline 改文字 / 换图 / 删 scene / 调时长 / 重排
Stage 4 MP4 导出   每 scene 调 EngineAdapter.render() → ffmpeg concat 跨 scene 拼接 + 整体音轨 mux
```

- 数据结构：`Asset`（**content-addressed，id = sha1(content)**；type: image/text/data/audio/video/reference-link；带 `userCaption` 与 `userTags`）→ `AssetBundle`（+ `intent` 一句话 + `UserPreferences`：aspect / durationTargetSec / mood / brandColors / fontFamilies / language / **commercial 是否商用**）→ `Storyboard`（scenes[] + globalAudio[] + defaultTransition + estimatedDurationSec + **status 状态机 `draft → ready-for-review → approved → rendered`**）→ `Scene`（template{id,engine} + variables + **assetRefs** + startSec + durationSec + transitionToNext + **`agentNote`（agent 给这个 scene 的解释，用户审稿时看得到）** + previewHtmlPath + previewPosterPath）。
- **EngineAdapter 增 `renderToHtml()`**：出 HTML 分镜而不是 MP4，用于审批阶段的快速预览；未实现则 core 兜底（先 render MP4 再抽 1 帧包一个 video tag，慢但能用）。
- **反面清单（可直接抄成 CP 的工作纪律）**：
  - ❌ 用户批准分镜之前不许 render MP4
  - ❌ **即使用户说"你看着办"，也不许跳过分镜预览环节**
  - ❌ 不许悄悄加用户没提的 scene——先提议，确认后再改
  - ❌ 不许在没有明确要求的情况下重复 render 同一个 storyboard（很慢）
- 目录约定：`.html-video/{bundles/<id>/{bundle.json,assets/<asset_id>.*},storyboards/<id>/{storyboard.json,scenes/<scene_id>/{scene.json,preview.html,poster.png,source/}},outputs/}`，放在项目根、与 `.git/` 平级、默认 gitignore。

#### 6.4.3 content-graph IR（RFC-06）

- **数据模型**：`nodes` 三型 `entity`（品牌实体，带自由 props 如 logo 路径、品牌色）/ `data`（要可视化的数字、百分比、时间序列）/ `text`（标题/引语/说明/正文），每个 node 带 `frameIntent`（"intro"/"data-bar"/"image-pan"/"quote"/"outro"/"list"，自由文本，由 frame-composer 映射到模板选择）与 `durationSec`（缺省 3s）。`edges` 三型 `sequence` / `contrast` / `dependency`，带 `reason`（人类可读理由，帮 frame-composer 选版式线索）。顶层 `intent` 六值 `single-frame / explainer / data-viz / promo / comparison / other` + `synopsis`（一句话"这视频讲什么"）。
- **`validate()` 六类错误**：`duplicate-node-id` / `edge-from-unknown-node` / `edge-to-unknown-node` / `self-edge` / `cycle` / `empty-graph` / `invalid-kind`；**除环之外收集全部错误，一次往返把反馈给足 agent**。
- **设计理由（其 notes 里写得很清楚，四条都对 CP 成立）**：
  1. **中间 JSON 是真理之源**：同一份内容可换不同视觉风格而不用重跑 chat agent；改一个数据点只刷新受影响的帧；JSON 可 commit / diff / 分享 / 版本控制。
  2. **确定性与语义性分层**：文本里的**结构事实**（数字/列表/标题/时间线/对比关系）用**规则**抽，只有**语义解读**（这帧讲什么、什么风格）才喂 LLM。收益三条——大幅降 token、结构提取可复现（同输入同输出）、**LLM 失败时结构事实仍然可用**。
  3. **图先建、再 topo-sort 成线性播放顺序**：视频是线性帧序列，但帧之间的语义关系应该先建成图，再选最佳顺序——时间线类按时间排、数据对比类按重要度排、教学类**按依赖排**（概念 A 必须出现在概念 B 之前）。
  4. **multi-agent 专人专事**：`intent-parser` / `content-extractor` / `structure-builder` / `style-resolver` / `frame-composer` / `validator`——每个独立 prompt，可单独迭代、可并行、可缓存。
- **单帧走快路径**跳过 content-graph（"我就要一帧"场景），多概念/时间线/对比才走 graph。这个二分很实用。
- 一句可直接借的设计原则（改写自 Understand-Anything 的 "Graphs that teach > graphs that impress"）：**"教得清楚的视频 > 看着炫的视频。"**

#### 6.4.4 template manifest（RFC-02）—— 模板作为 agent 可检索单元

每个模板一个目录，固定 `template.html-video.yaml`：

- 标识：`spec_version` / `id`（kebab-case 全局唯一）/ `name` / `description`
- **引擎归属**：`engine` + `engine_version`（peerDep semver）+ `source_entry`（engine-native 入口）
- **检索元数据**：`category` / `subcategory` / `tags` / **`best_for`（短句意图描述）+ `not_for`（反向标记，防 agent 错配）**
- **输出能力**：`formats` / `resolution.supported_aspects` / `fps` / `duration`（`variable` 跟 inputs 走 or `fixed`；`min_sec`/`max_sec`）/ `alpha` / `audio.expected_inputs`
- **`inputs.schema`（JSON Schema Draft 2020-12）**——agent 可 introspect 到底该填哪些文本/数据槽位
- **许可证可溯源**：SPDX id + `attribution_required` / `redistribution_allowed` / `commercial_use` 三个显式布尔 + `assets_attribution` 指向上游源 URL；RFC-04 追加 `scene_role`（intro/data/cta/outro）与 `assets_consumed`（声明吃哪类 asset）
- 21 个模板**license-clean by construction**：fork 保留原许可证，仓根 `templates/NOTICE.md` 记录每个来源与 SPDX，**没有明确宽松许可证的一律不进仓** ⇒ 可直接用于商业作品无需审计。**这条对 CP 尤其重要——CP 产出的是要发布的商业内容。**

#### 6.4.5 源抓取（article / repo → video）

三种入口：Web 文章 URL（服务端抓取并 flatten 成 Markdown，**微信公众号这类服务端渲染页开箱可用**）/ GitHub repo（走公开 API 取 description + 顶层结构 + README）/ 纯 prompt。抓来的内容是视频**真正据以构建**的材料，而不是套在罐头模板外的装饰——1500 词文章会变成一条多场次解说，每一句都能追溯回原文某处。

> 这条能力与本仓 `smart-search` / `wx-mp-hunter` / `viral-chaser` 的取数链路重叠度很高，**不需要吸收其抓取实现**，但"抓来的材料要能逐句追溯回源"这条**判据**值得写进 CP 的脚本阶段。

---

## 7. 四项目关联分析

### 7.1 它们不是四个平行竞品，是一条依赖链上的四层

| 层 | 项目 | 职责 | 对 CP 的意义 |
|----|------|------|------------|
| **L4 制片治理** | OpenMontage | 阶段链 / 闸门 / 预算 / 选型 / 自检 / 审计 | CP 主链的**流程与判据**来源 |
| **L3 创作链路** | html-video | 素材+意图 → content-graph → HTML 分镜 → 审 → MP4 | CP 模板路径的 **IR 与审批形态**来源 |
| **L2 渲染引擎** | HyperFrames | HTML + `data-*` → 确定性 MP4；19 skill 的组织范式 | CP 模板路径的**执行底座** + **skill 架构范式** |
| **L1 生成内核** | ViMax | 脚本 → 分镜 → 机位树 → 一致性 → AIGC 出片 | CP AIGC 路径的**出脚本与一致性**来源 |

### 7.2 实证关联（有代码/文档证据，非推测）

1. **OpenMontage ⊃ HyperFrames（vendored + 双 runtime）**
   - OM 把 HF 19 个 skill 里的 **12 个 vendored 进 `.agents/skills/`**，`PROVENANCE.md` 明确记录来源 commit `3351fb1a` / tag `v0.7.17` / 2026-06-27。
   - **刻意不 vendor** 的 7 个是 `embedded-captions` / `faceless-explainer` / `general-video` / `pr-to-video` / `product-launch-video` / `slideshow` / `talking-head-recut`，理由写得很直白：**"这些是 HF 自己的 workflow 路由，会跟 OpenMontage 的 pipeline 路由竞争或重复。"**
     → **这条对 CP 是直接的方法论警示**：吸收外部项目的 skill 时，**原子能力（domain skill）可以整体吸收，工作流路由（workflow skill）不能吸收**——否则会跟自家路由打架。
   - HF 是 OM **两个渲染 runtime 之一**（另一个 Remotion）；runtime 在 proposal 期锁定为 `render_runtime`，**静默切换 runtime 属治理违规（CRITICAL）**。
2. **html-video ⊃ HyperFrames（唯一 shipped adapter + 模板来源）**：HF 是 html-video 目前唯一跑通的引擎适配器，且其 21 个模板中有若干直接来自 HF 的 Apache-2.0 模板（`templates/NOTICE.md` 记录）。
3. **OpenMontage ∥ html-video（同在 HF 之上，但加的东西不同，可叠加）**：OM 加的是**制片治理**（谁批、多少钱、够不够好、有没有静默降级）；html-video 加的是**引擎抽象 + 素材到分镜的创作链路**（用户只有素材和一句话时怎么办）。两者互不覆盖，**理论上可以叠着用**——这恰好说明 CP 需要的是"OM 的治理 + html-video 的创作链路"，而不是二选一。
4. **ViMax ⊥ 其余三者（正交互补）**：ViMax 完全不碰 HTML 渲染（走 image-gen + video-gen + moviepy concat）；其余三者完全不碰角色一致性与跨机位连续性。**两边的能力集几乎零交集**——这正好对应 CP 现有的"AIGC 路径 vs 模板路径"分裂，ViMax 补前者，HF/html-video 补后者。
5. **HF 与 Remotion 的关系被三方同时确认**：HF README 自陈"受 Remotion 启发"并给出对比表；OM 同时跑两个 runtime 并写了决策矩阵；html-video 把 Remotion adapter 列在路线图并写了 RFC-08。三方共识是——**HTML 授权模式（Apache-2.0）+ agent 可直接写 = HF 胜出的原因；Remotion 的优势在成熟的 Lambda 分布式渲染**。对我们：本地渲染场景选 HF 无疑。

### 7.3 四个项目独立收敛到的三条结论（因此可信度最高，应作为 CP 重构的地基）

1. **中间结构化产物是真理之源，agent 不靠记忆靠文件。**
   OM 的 `artifacts/` + 21 个 JSON Schema；ViMax 的 `.working_dir/<session>/**.json`（"artifact 授权中心"）；html-video 的 `content-graph.json` + `.html-video/`；HF 的 `BRIEF.md` + `hyperframes.json` + `STORYBOARD.md`。四者形态不同、结论一致。
2. **在花钱之前设审批闸门。**
   OM 的 `human_approval_default` + pre-compose validation；ViMax 的 `plan_text_artifacts()` **只跑到文本产物、停在任何付费生成之前**；html-video 的 storyboard 审批 gate（`status: ready-for-review → approved`）；HF 的 intent interview → `BRIEF.md` 确认。
3. **不许静默降级 / 不许静默替换 / 不许声称没做过的事。**
   OM：delivery promise 锁定 + runtime lock + "静默换 runtime 是 CRITICAL 违规" + "用户说不要音乐就别因为'成片显得薄'偷偷加"；html-video："不许悄悄加用户没提的 scene""哪怕用户说你看着办也不许跳过分镜预览"；HF："CLI 升级绝不静默，要在总结里报旧版新版""只提议不静默改，尤其调色"；ViMax："没有 tool result 或 working_dir 状态证明，不许声称 planning/render/文件改动发生过"。

### 7.4 术语对齐表（同一概念的四种叫法，读源码时别混）

| 概念 | OpenMontage | ViMax | HyperFrames | html-video |
|------|-------------|-------|-------------|-----------|
| 意图/立项产物 | `brief` / `proposal_packet` | `project_brief` | `BRIEF.md` | `AssetBundle.intent` + `UserPreferences` |
| 分镜/镜头计划 | `scene_plan`（含 `metadata.slots[]`） | `storyboard` + `shot_descriptions` | `STORYBOARD.md` | `Storyboard.scenes[]` / `content-graph` |
| 最小可视单元 | scene / slot | shot | clip / composition | scene / frame |
| 交付形态承诺 | `delivery_promise` | workflow 三选一 | `BRIEF.md` 的 `workflow` + `flow` | `content-graph.intent` |
| 素材台账 | `asset_manifest`（带 provenance） | `character_portraits_registry` | `/media-use` ledger | `AssetBundle.assets[]`（content-addressed） |
| 成片自检 | post-render self-review + slideshow_risk | 无（靠 best_image_selector 前置） | `lint` / `check` / `keyframes` 诊断 | 无（靠 storyboard 人审） |

**观察**：`成片自检` 一行只有 OM 做全了，`素材台账` 一行只有 HF 抽成了统一抽象，`一致性` 只有 ViMax 做了。**没有任何一个项目四项齐全**——CP 的机会正在这里。

---

## 8. CP 侧可吸收清单（调研判定）

> 本节只记**吸收/不吸收的判定与理由**，不写落地方案。实际落地（改哪个 SKILL.md、加哪个脚本、stages 怎么拆）由后续开发计划撰写。
> 判定分三档：**A 直接吸收** / **B 改造吸收** / **C 不吸收**。

### 8.1 出脚本能力（§3 原则 3 的重点，CP 独占职责）

| # | 能力 | 来源 | 判定 | 理由 |
|---|------|------|------|------|
| 1 | **intent router → narrative/motion/montage 三档脚本模板** | ViMax | **A** | 直接解决"CP 出脚本靠什么套路"。三档判据清晰、各带专属 guidelines，可整体译成中文写进 stages。MIT 可用。 |
| 2 | **三条硬约束：禁隐喻 / 禁机位术语 / 对白引号格式** | ViMax | **A** | 全是为下游 AIGC 服务的约束（隐喻会被图像模型直译、机位术语会与 storyboard 阶段冲突），我们同样需要。 |
| 3 | **develop_story → write_script_based_on_story 两段式 + 场次划分原则（同时间同地点）** | ViMax | **A** | 我们现在 step2-script 是一步到位，缺"故事→分场"的中间态。 |
| 4 | **script_enhancer：为精度允许冗余 + 每次对白重复角色音色描述** | ViMax | **A** | 后者直接解决声画同出的**音色漂移**问题，成本极低收益极大。 |
| 5 | **叙事弧时间预算（HOOK 0-5s / SETUP / BUILD / CLIMAX / LANDING 5s）+ therefore-but 规则 + 开场禁语** | OpenMontage | **B** | 方法论吸收，AGPL 不许抄原文，需用我们自己的话重写。适用于解说型内容，与 ViMax 三档（叙事型）互补。 |
| 6 | **词/字预算表 + 超 20% 必砍** | OpenMontage | **B** | wpm 表是英文的，中文要按字数重标定（需实测我们 TTS 的中文语速）。方法论直接可用。 |
| 7 | **enhancement_cues 六型 + 每 8-10s ≥1 条密度规则** | OpenMontage | **B** | 我们脚本里目前没有结构化的视觉指令槽位，这是"脚本→分镜"衔接的关键接口。 |
| 8 | **结构化 delivery_cues（pace/energy/emphasis_words/pause/provider_text 带 SSML）+ 只写 TTS 能实现的指令** | OpenMontage | **B** | 需按我们实际 TTS 通道（OpenClaw 内置 / siliconflow-tts / MiniMax）能力裁剪，不是所有通道都吃 SSML。 |
| 9 | 脚本自评 N 维打分、任一维 <3 必返工 | OpenMontage | **B** | 与现有 `content-calibrator` 打分环节功能重叠，需先判定是合并还是分层（脚本级自评 vs 成片级打分）。 |
| 10 | 多语言脚本 / 批量脚本 | MPT | **C** | §3.1 已判 MPT 批量机制不引入；CP 侧同理（CP 是逐条精做，不是批量撞运气）。 |

### 8.2 分镜与一致性（CP 的 AIGC 路径）

| # | 能力 | 来源 | 判定 | 理由 |
|---|------|------|------|------|
| 11 | **首帧/尾帧/运动描述三拆 + 首尾帧必须是纯快照** | ViMax | **A** | 直接对应 `aigc-video-gen` 的 i2v 入参形态，现在我们是"一段 prompt 打过去"，质量不可控。 |
| 12 | **运动描述里禁用角色名、必须用外观特征指代** | ViMax | **A** | 一句话规则，解决 i2v 模型不认名字的实际问题。 |
| 13 | **`variation_type` 三档决定传 1 张还是 2 张参考图** | ViMax | **A** | 把"什么时候用首尾帧插值"从凭感觉变成有判据，直接省钱且提质。 |
| 14 | **camera_tree + 转场视频取帧法（新机位首帧不从零生成）** | ViMax | **B** | 机制很巧但成本不低（每个新机位多一次 video 生成 + PySceneDetect 切场）。**需要先做成本/收益实测**再定是否引入；对"人物故事"类内容价值最高，对"图文解说"类几乎无用。 |
| 15 | **角色三视图 registry（front/side/back）+ 不可见角色不生成** | ViMax | **A** | 我们现在只有单张 `character_reference.jpg`，三视图是成本很低的一致性升级。 |
| 16 | **static_features / dynamic_features 拆分 + 跨场角色融合 + 同名不同龄必须拆角色** | ViMax | **A** | 数据结构级的改进，成本低。 |
| 17 | **best_image_selector 三轴择优（角色一致性 7 项 / 空间一致性 / 描述准确性）+ 排除白黑边** | ViMax | **A** | 我们现有 Gate 0 是人工看 contact sheet，加一道机器预筛能省用户的眼。 |
| 18 | **storyboard 硬规则集**（每镜有叙事目的 / 机位尽量复用且大幅运动后不可复用 / 必写位置与朝向 / 不写不可见元素 / 每镜每角色最多一句台词 / 每镜描述自包含） | ViMax | **A** | 六条全部是低成本高收益的写作纪律。 |
| 19 | **tone → 平均 hold → 每 60s slot 数表** + shape 四型 | OpenMontage | **B** | 表格本身是英文纪录片语境的经验值，中文短视频需重标定；但"先算 slot 数再写第一个 slot"这条纪律直接可用。 |

### 8.3 素材获取与匹配（CP 与 main 共享公共 skill，但 CP 用得更深）

| # | 能力 | 来源 | 判定 | 理由 |
|---|------|------|------|------|
| 20 | **slot description 模板 `<主体>,<动作>,<环境>,<光线>,<年代/质感>` + 禁情绪词/意图动词 + "想不出具体照片就是写错了"判据** | OpenMontage | **A** | 方法论，可用自己的话写。这是我们 Stock Footage 模式质量差的根因所在。 |
| 21 | **description 与 query 分职（description 喂语义排序，query ≤5 词喂图库 API）+ 每 slot 2-3 条 literal/lateral/association** | OpenMontage | **A** | 同上，立刻可改善 `pexels-footage` / `pixabay-footage` 的召回质量。 |
| 22 | **hero slot 概念（2-3 个，更长 hold / 更大候选池 / 更多 query）** | OpenMontage | **A** | 低成本，把有限的挑选精力集中到决定成败的三个镜头上。 |
| 23 | **按判断挑不按分数挑（年代/运动/相邻构图/情绪语域四维压过分数）+ exclude_ids 防一素材占两坑 + rejected_picks 落盘** | OpenMontage | **A** | 前两条纯纪律；`rejected_picks` 落盘让合成阶段能回退第二名，成本极低。 |
| 24 | **CLIP corpus + 余弦阈值 0.30/0.22 + corpus 8-12x slot + mean_motion_score<1.0 判幻灯 + diversify** | OpenMontage | **B/C** | 算法很好，但要**本地跑 CLIP 模型**（依赖 torch 系），与本仓"纯 stdlib + ffmpeg"的轻量范式冲突。**建议判 C（不引入 CLIP）**，但把它的**Fast path**（多源并发搜 → 每 query 下 2-3 条 → 看缩略图人工核对 → 手工映射）判 **A** 吸收——那条路不需要 embedding。阈值判据可退化成"人看缩略图"的检查项。 |
| 25 | **多源图库扩展（Coverr / Mixkit / Archive.org / NARA / LoC / Videvo / NASA / ESA / JAXA / NOAA / Dareful / Wikimedia / Unsplash）+ 每源强项对照表** | OpenMontage | **B** | 我们现在只有 Pexels + Pixabay 两源。这张"哪个源擅长什么"的表价值很高。但是否新增 provider 要看 §3 原则 2（不抄适配层）——**只吸收对照表，provider 接入按我们自己的方式做**，且需评估国内网络可达性。 |
| 26 | **儿童/童话内容 source lock（pixabay_video 单源 AI 奇幻库）+ 禁真实与奇幻混用 + query 改写表** | OpenMontage | **A** | 一条非常具体、可立即验证的经验，且 CP 很可能要做儿童内容。 |
| 27 | **`/media-use` 的"一个动词 resolve + 检索噪音留磁盘 + 先列可复用候选 + ledger"抽象** | HyperFrames | **A（结构性）** | 我们现在有 `pexels-footage` / `pixabay-footage` / `siliconflow-img-gen` / `siliconflow-tts` / `siliconflow-video-gen` / `aigc-video-gen` 六个各自为政的资产 skill，**agent 每次要自己想调哪个**。抽一个统一入口是结构性优化。Apache-2.0 可借。 |
| 28 | **"media opportunity pass" 四条纪律（有信号才提 / 给具体方案让人选 all-some-none / 一个项目只问一次 / 只提议不静默改）** | HyperFrames | **A** | 直接治我们 crew "要么不主动要么话痨" 的老毛病。 |
| 29 | **logo 降级链（svgl → simple-icons → GitHub avatar → favicon）+ 永不重绘** | HyperFrames | **B** | 具体实现要看这些源在国内是否可达；"永不重绘 logo"这条纪律直接吸收。 |
| 30 | **source media inspection（用户素材必先 probe，禁凭文件名臆测）** | OpenMontage | **A** | 我们 `step3-user-assets` 目前没有强制 probe。 |

### 8.4 结构与治理（CP 重构的骨架）

| # | 能力 | 来源 | 判定 | 理由 |
|---|------|------|------|------|
| 31 | **router skill + creation workflow + domain skill 三层架构** | HyperFrames | **A（★ 最高优先）** | CP 现在是 9 个 skill 平铺，agent 靠 description 猜该用哪个。三层架构 + "首个匹配行即执行"的状态表 + "匹配交付物不匹配顺口提到的词" 正是 CP 缺的编排层。CP 现有三条平行路径（collage-broll / html-video / manim-explainer）天然就是三个 creation workflow。 |
| 32 | **`BRIEF.md` 作为唯一路由产物，路由一次就走、后面不再回 router** | HyperFrames | **A** | 解决"每轮都重新纠结走哪条路"的上下文浪费。 |
| 33 | **"domain skill 永不接管端到端交付物"** | HyperFrames | **A** | 一句话规则，防止 `siliconflow-video-gen` 之类的原子能力被当成主链入口。 |
| 34 | **吸收外部 skill 时：原子能力可整体吸收，workflow 路由不可吸收（会与自家路由打架）** | OpenMontage 的 vendoring 决策 | **A（方法论）** | 直接指导我们怎么处理 CP 的 `html-video` skill——**吸收 HF 的 domain skill 层，不吸收 HF 的 10 个 creation workflow**。 |
| 35 | **pipeline manifest 的 stage 字段设计（produces / required_artifacts_in / tools_available / checkpoint_required / human_approval_default / review_focus / success_criteria）** | OpenMontage | **B** | 方法论吸收。我们不需要 YAML manifest（SKILL.md + stages 已够），但**每个 stage 都该显式写出这 7 项**——尤其 `success_criteria` 要可判定。 |
| 36 | **stage-director 固定骨架（When to Use / Prerequisites 表 / Process / Self-Evaluate / Submit / Common Pitfalls / Gate Reminder）** | OpenMontage | **B** | 我们 `stages/*.md` 目前骨架不统一。统一骨架能大幅降低 crew 误读率。 |
| 37 | **Gate Reminder 措辞：落 awaiting_human → 呈现摘要 → 结束本轮回复；批准逐闸门、早先的"你继续"不覆盖本闸门** | OpenMontage | **A（语义）** | 这是我们的 crew 最常违反的行为，值得逐字打磨成我们自己的措辞。 |
| 38 | **返工/耗时上限（max_revisions_per_stage / max_send_backs / max_wall_time_minutes）** | OpenMontage | **A** | 我们完全没有这类护栏，crew 卡在某阶段反复重试的情况真实发生过。 |
| 39 | **artifact-file-as-checkpoint（产物文件存在即 load，不存在才生成）** | ViMax | **A（★）** | §4.5 已判 main 不需要 `state.py`。CP 需要断点续跑但同样不该上状态机脚本——**用产物文件存在性当 checkpoint** 是最轻的答案，且允许用户手改 JSON 后续跑。 |
| 40 | **"只跑到文本产物为止"的函数/阶段边界（付费生成之前必停）** | ViMax `plan_text_artifacts()` | **A（★）** | 闸门的最自然定义。CP 现有 Gate 0 是在关键帧之后，**应该再往前挪一道**：文本产物（脚本+分镜+机位）全齐后先停一次。 |
| 41 | **agent 硬约束："没有 tool result 或产物文件证明，不许声称做过"** | ViMax `prompts/agent.md`（全文 4 行） | **A** | 极低成本、极高价值，建议直接写进 CP 的 AGENTS.md 或 SOUL.md。 |
| 42 | **workflow 确认闸门：模糊意图不算确认，起草脚本属对话协助不许调 tool，默认小规模（1 场 3-5 镜）不许擅自放大** | ViMax `prompts/workflow.md` | **A** | "不许把模糊想法擅自扩成多场多镜"这条能直接省钱。 |
| 43 | **两段式 storyboard 审批（agent 出分镜 → 用户浏览器逐 scene 审改 → 确认才 render）+ 四条反面清单** | html-video | **A（判据）/ B（形态）** | 四条反面清单（尤其"即使用户说你看着办也不许跳过分镜预览"）直接吸收。但"浏览器 studio 逐 scene inline 编辑"属 UI 层，按 §3 原则 1 **不吸收 UI**——在 openclaw 语境下退化为"contact sheet + 逐段确认"，这正是我们现有形态。 |
| 44 | **决策审计链（每个选择记备选 + 置信度 + 理由，跨阶段累积）** | OpenMontage | **B** | 价值明确但会显著增加 crew 的写字负担。**建议只对高成本决策强制**（路径选择、模型选择、预算变更、任何 fallback）。 |
| 45 | **预算四步 estimate → reserve → 执行 → reconcile + observe/warn/cap 三模式 + 单动作阈值 + 总额上限** | OpenMontage | **B** | CP 已有 `budget.json`（估算+实际累计），缺的是 `reserve` 与三模式。**建议只补"超阈值必须先问"这一条**，不引入完整四步。 |
| 46 | **reference-driven 创作（贴一条参考片 → 分析节奏/钩子/结构 → 给 2-3 个差异化概念 + 成本 + 一段 10-15s 试片）** | OpenMontage | **A（★）** | 与 main 的 `viral-chaser` 衔接得天衣无缝——viral-chaser 出的追爆报告就是"参考片分析"，CP 接手后正好走这条链。**"先出 10-15s 试片再全量生产"这条能极大降低返工成本。** |
| 47 | **提案期给 3 个真正不同的概念 + 逐项列明成本 + 不同价位的备选路径** | OpenMontage | **B** | CP 现在是"一个脚本给用户确认"。给 3 个概念更贵但更可能一次过。需用户拍板要不要。 |

### 8.5 成片自检与质量闸门

| # | 能力 | 来源 | 判定 | 理由 |
|---|------|------|------|------|
| 48 | **slideshow_risk 六维打分 + `≥4.0 fail 不许进 compose` + 具体扣分阈值** | OpenMontage | **A（★）** | 我们的公共 `video-review` 只查技术层（ffprobe / 黑帧 / 音频电平 / 时长分辨率一致性），**完全不查"这片子是不是会动的幻灯"**。这是 CP 质量的最大盲区。**注意：这是 pre-compose 闸门，评的是"计划"不是"成片"**，与 `video-review` 不重叠而是互补。 |
| 49 | **delivery_promise 八类 + 锁定 + "text_card/chart/kpi_grid 是动画幻灯不计入 motion" + motion_led 要求 ≥0.70** | OpenMontage | **A（★）** | 那条"给静图加转场不算动态"的判据是全部调研里最锋利的一条。CP 三条路径里 html-video 模板路径**天然是 slide grammar 重度用户**，必须有这道闸门。 |
| 50 | **lint → check → preview → render 的执行顺序纪律** | HyperFrames | **A** | CP 的 html-video 路径应照此顺序，现在是直接 render。 |
| 51 | **content-graph `validate()`：除环之外收集全部错误，一次往返给足反馈** | html-video | **A** | 校验器设计原则，成本几乎为零。 |
| 52 | **`keyframes` 诊断（对已渲染的运动做诊断）** | HyperFrames | **C（暂缓）** | 依赖 HF CLI 的具体实现，价值有但优先级低于 48/49。 |

### 8.6 CP 三条路径各自的针对性收获

| 路径 | 最该吸收的 | 来源 |
|------|-----------|------|
| **AIGC 路径**（video-product 主链 + collage-broll） | 11/12/13/15/16/17/18（首尾帧三拆、variation_type、三视图、角色特征拆分、择优三轴、storyboard 硬规则）；14 待成本实测 | ViMax |
| **模板路径**（html-video） | content-graph IR 与其四条设计理由（§6.4.3）；template manifest 的 `best_for`/`not_for` + `inputs.schema` + license 三元组（§6.4.4）；48/49 两道幻灯闸门；50 执行顺序 | html-video + HF + OM |
| **科学动画路径**（manim-explainer） | 收获最少——三个项目都不做数学动画（html-video 把 Manim 列为"researching"）。可吸收的只有 7（enhancement_cues 六型里的 `diagram`）与 36（stage 骨架统一） | — |
| **设计规范**（design-system-picker） | **`frame.md` 的"为镜头反转设计系统"这一层**——我们现在挑到的是网页设计规范，缺的正是这层翻译。12 套 frame-preset 是 Apache-2.0，可直接参考 | HyperFrames |

### 8.7 明确不吸收（附理由）

| 不吸收项 | 理由 |
|---------|------|
| 全部 WebUI / studio / TUI / backlot 看板 / Web 前端 | §3 原则 1 钦定 |
| 全部 Provider 适配层（OM 的 52 tool 适配、ViMax 的 tools/*.py、HF 的 heygen CLI、html-video 的 MiniMax provider） | §3 原则 2 钦定；模型调用统一走本仓公共模块 |
| CLIP / torch 系本地模型（corpus_builder / clip_embedder / video_understand / WhisperX） | 与本仓"stdlib + ffmpeg"轻量范式冲突；改用 Fast path 人工核对缩略图（见 #24） |
| HF 的 10 个 creation workflow skill | 会与 CP 自家路由竞争（OM 的 vendoring 决策已验证这条，见 #34） |
| html-video 的 studio HTTP server / 14 个 agent backend 检测 / ACP 协议层 | UI 与 agent 宿主层，openclaw 语境下无意义 |
| Remotion / Motion Canvas / Revideo 适配 | CP 只需一条 HTML 渲染路径（HF），多引擎抽象对我们是纯负担 |
| MPT 的 `video_count` 批量 + random shuffle | §3.1 已判；CP 同理（逐条精做而非批量撞运气） |
| 跨平台一键发布 | 归 main 的各 publish 技能 |

---

## 9. 调研中发现的现状差异（需在开发计划前确认）

### 9.1 `skills/aigc-video-gen/` 尚未落地，但已被 7 处引用（断链）

<已解决>

### 9.2 §2 现状盘点相对当前仓已有滞后

§2.1 / §2.2 / §2.7 描述的是重构前状态，当前仓已推进：

<已更改，以现状为准,在现状基础上做后续工作>

### 9.3 待用户拍板的 CP 侧决策（等这批调研确认后一次性问）

1. **CP 是否按 HF 三层架构重组**（router skill + 三条 creation workflow + 公共 domain skill）？这是 §8.4 #31 的前提，也是"完全重构"的骨架决定。
> 同意
2. **#14 camera_tree 转场取帧法**是否值得那笔额外的 video 生成成本？（建议先做一次成本实测再定，不在本轮定）
> ffmpeg是不是自带转场功能？
3. **#24 是否引入 CLIP**（本地 torch 依赖）？建议判不引入、走 Fast path，需确认。
> 不引入
4. **#25 是否扩充图库源**（Coverr / Mixkit / Archive.org / Videvo 等）？涉及新增 provider 与国内可达性评估。
> 不扩充
5. **#47 提案期是否给 3 个概念选项**（更贵但更可能一次过），还是维持现在的"一个脚本给用户确认"？
> 可以，尽量吸收上游先进的方法
6. **#44/#45 决策审计链与预算四步吸收到什么程度**（全量 vs 只对高成本决策/超阈值）？
> 可以先全量、原汁原味吸收，我们在使用中再改进
7. **`frame.md` 层是否要做**（把 `design-system-picker` 的 14 套网页规范补一层"为镜头反转"）？
> 不必 design-system-picker 完全是cp的另一个能力