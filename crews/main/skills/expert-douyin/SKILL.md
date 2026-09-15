---
name: expert-douyin
description: 抖音账号运营专家。承接定位起号、内容 DNA（视频 / 图文两套框架）、选题与包装、图文生产、已有素材轻加工、视频全案 Brief 与口播文案、发布与数据复盘；全片制作委托 content-producer。
metadata:
  openclaw:
    emoji: 🎵
---

# 抖音账号运营专家

## 预设 Workflow

整活直接走对应 workflow：

| 场景 | Workflow | 什么时候触发 |
|------|----------|-------------|
| 内容 DNA 管理 | Style DNA | 建 / 更新内容 DNA（样本、偏好、局部借鉴、对标融合）：先判作品类型，再决定样本落到哪个 DNA |
| 内容生产 | Content Production | 做一条 / 做几条抖音内容；main 直接做已有素材轻加工，视频全案只产出Brief并委托content-producer |
| 起号与定位 | Account Setup | 新号起号、定位梳理、内容支柱搭建、老号接手与诊断 |
| 账号对标 | Account Benchmark | 对标账号 / 对标视频分析，并与默认或指定 DNA 逐项比较 |
| 改片与调整 | Editing | 改文案、重剪、换封面、调结构、换风格 |
| 数据复盘 | Review | douyin 全部数据复盘：DNA 评估、用户临时看数据 / 复盘 / 评估 DNA |

## 资源命名约定

- Tools、Workflows、DNA 模板等名称是 `expert-douyin` 技能包内的逻辑资源名，不是 Agent Workspace 路径，也不要拼成相对路径执行。
- 技能部署后整个包通过软链进入运行环境；Agent 不要假设这些资源被展开到 Workspace 下。
- 嵌套工具说明中的 `references/` 仅指该工具说明随附的技能包资源，不是 Workspace 路径，不要从 Workspace 根拼接。
- 其他文档中出现的 `douyin/dna/`、`douyin/ref/`、`douyin/outputs/`、`douyin/calibration/` 才是 Workspace 相对路径，统一从 Workspace 根目录解析。
- 只有命令清单中明确列出的 wrapper 名称可以直接作为 shell 命令调用；其余 Tool 名称仅用于定位对应说明。

零散操作（只想发条视频、只想拆解一条参考视频、只想建个 DNA）直接用下面的工具。

## 工具清单

零散活儿直接调用，不走完整 workflow。按工具名称查找对应说明，不要把工具名拼成路径。

| 工具 | 用途 | 命令 |
|------|------|------|
| `douyin-style-profiler` | 生成单篇作品（视频 / 图文，`--kind`）的 DNA report，并聚合 DNA 文档与 template（视频 = Brief + 口播文案模板；图文 = 写作模板） | `douyin-style-profiler` |
| `douyin-comments` | 抓取抖音视频评论（对标分析 / 标签反推用，纯 HTTP 不起浏览器） | `douyin-comments` |
| `douyin-publish` | 成片 → 抖音创作者中心发布（浏览器自动化） | `douyin-publish` |

跨领域通用技能：`viral-chaser`（抖音 / B站 / 小红书视频下载拆解，DNA 采样与仿写参考的取数主力）、`smart-search`（跨平台搜索，选题调研优先走社交平台，不用通用搜索引擎）、`content-calibrator`（DNA 表现评估）、`published-track`（发布记录与指标库）、`login-manager`（抖音登录态维护）。

素材加工相关技能：`video-edit`（素材加工拼接）、`talking-head-cut`（口播轻剪辑）、`ui-demo`（产品操作录屏）、`video-review`（成片质检闸门）、`siliconflow-img-gen`（封面图）、`pexels-footage` / `pixabay-footage`（免版权素材）。

**视频全案分工硬边界**：main 负责选题策划、按 DNA 出 **Brief**、拟定标题与简介、准备素材（用户素材预处理 / `ui-demo` 录屏 / 从 `campaign_assets/` 挑选，绝对路径写进 Brief）、监督推动 CP、成片后的发布与运营，也直接做图文内容与已有素材轻加工；视频全案的成片制作委托 `content-producer`。口播类视频的口播文案由 main 按 `narration-script` 子模块写好并随 Brief 交付（真人口播时，指导用户录音并取得录音文件），CP 不重写策略文案。Brief 指定 `workflow` 时 CP 必须采用；未指定时 CP 按其通用制作流程做（那是 CP 的基准准则，不是备选 workflow），档位由 Stage 1 定。Brief **不含 DNA 信息**，main 也不替 CP 建工作区（双方 T3 权限可互访取文件）。

## 风格与 DNA

DNA 存储目录是 `douyin/dna/`。未指定 DNA 时默认使用并更新 `dna-0`（视频）；图文另建 dna-id（如 `dna-0-note`）。生产前同时读取 DNA 文档与 DNA template；对标分析先建立独立对标 DNA，不默认写入 `dna-0`。

DNA 是**从一批作品样本提取并聚合出的内容生产规则集**：视频 10 维——选题与观看理由、标题与封面、内容创意、**业务植入套路**、**互动引导与 CTA 套路**、视频内容形态与制作指向、制作规格与视听倾向，加可选的口播文案子模块与账号运营子模块（简介写法、内容形式比例、发布习惯）；图文 9 维——选题、标题与封面图组、内容创意、正文表达与语气、图组视觉、**业务植入套路**、**互动引导与 CTA 套路**，加账号运营子模块。它指导 main agent 出图文内容或视频 Brief（+ 口播文案），不规定创作细节与成片制作。维度框架 v2 位于 `douyin-style-profiler` 的 `references/video-dna-framework.md` 与 `references/note-dna-framework.md`。

## 数据与记录

- 发布记录统一走 `published-track`（入库时传 `--account`；`dna_id` 经作品目录 `dna-meta.json` 自动关联）
- DNA 表现评估的引擎是 `content-calibrator`（触发、基线归一化、趋势、报告结构），数据在 `published-track`；**douyin 的全部复盘工作（heartbeat 按量触发 + 用户临时发起）统一走 Review Workflow**，由它调用上述技能并用抖音归因方法分析。评估报告落 `douyin/dna/<dna-id>/evals/`，建议经用户逐条确认后走 Style DNA Workflow 回写 DNA
- 平台级数据（受众画像、对标记录、平台状态）存平台运营文件夹 `douyin/calibration/`
- 平台运营文件夹 `douyin/` 统一存放运营产出物、知识、经验和记录表格（如 `douyin/ref/` 参考材料、`douyin/outputs/` 成片与素材）；与 `douyin/dna/`、`douyin/calibration/` 等结构化数据目录分开，不混放
- 数据是用来指导下一轮改进的，不是为了凑数字——每次复盘必须有明确的下一步动作

## 平台速查与硬性红线

- **发布限频**：单抖音号每 24h ≤ 5 条；触发风控立即降级，30 分钟内不重试。
- **串行发布**：`douyin-publish` 同一时间只能有一个发布任务在跑（浏览器 session 竞态）。
- **AIGC 标注**：AI 生成的内容按平台规则标注，`douyin-publish fill` 已内置自主声明"内容由AI生成"。
- **简介引流**：视频简介可提及产品与业务，但不放明显引流信息；禁止二维码、联系方式；可引导主动搜索或看主页。
- **登录态**：浏览器操作一律走 `login-manager` 真实登录后的持久化 session，严禁 `cookies import` 造会话。
- **数据诚实**：互动数据只来自平台接口、`viral-chaser` 返回或用户提供的线索，不编造；估算值必须标注估算方法，不可得的数据写明"数据不可得"。
