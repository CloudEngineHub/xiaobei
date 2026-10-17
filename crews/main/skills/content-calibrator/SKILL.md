---
name: content-calibrator
description: DNA 表现评估引擎——消费 published-track 的发布与互动数据，按量触发 DNA 评估，产出报告与优化建议，经用户确认后回写。用户开启、调整或停用定时取数复盘时，提供参考并派 IT engineer 管理原生 Automation。发布与指标记录由 published-track 管理，平台取数由各专家包 engagement 工具负责。
metadata:
  openclaw:
    emoji: 🎯
    requires:
      bins:
      - bash
      - sqlite3
      - python3
---

# Content Calibrator — DNA 表现评估引擎

> **四条评估铁律**：
> 1. **趋势优先**：绝对值只作上下文。数据好坏看「同账号相对值 + 其走向」——新号数据天然低、老号天然高，同 DNA 跨账号不可直接比绝对值，要的是趋势
> 2. **脚本只给证据**：聚合、基线、比值、走向由 `content-calibrator eval` 计算；好坏归因由 Agent 回读 DNA 文档与作品原文完成，脚本不下结论
> 3. **先排混杂再归因**：账号成熟度、粉丝自然增长、选题热度、季节性流量都会污染信号；排除不了的混杂，结论降级写「观察」不写「结论」
> 4. **DNA 更新必须用户逐条确认**：评估只产出建议，Agent 不得自动改 DNA

---

## 职责边界（与 review / published-track 的分工）

| 角色 | 回答什么 | 产出 |
|------|---------|------|
| `published-track` | 数据在哪 | 发布记录 + 互动指标存储；各平台专家包 engagement 工具取数后回填 |
| **本技能** | **这个 DNA 好不好、该怎么改**（共性引擎） | 触发规则、基线归一化与趋势证据、评估报告结构；`<platform>/dna/<dna-id>/evals/*.eval.md` |
| 各平台专家包 `review` workflow | 该平台的数据复盘怎么做（平台特性） | 平台归因方法（指标语义、映射、混杂因素）+ 复盘编排；heartbeat 与用户临时发起的该平台复盘都走它 |

本技能只给**共性归因步骤与原则**，不含任何平台特有归因方法，平台归因方法一律由该平台专家包 review workflow 提供。本技能的结论**必须落到 DNA 动作**（保持 / 调整某维度规则 / 调整 template 某部分），经用户逐条确认后走对应平台的 style-dna workflow 更新。

---

## 核心闭环

```
📥 专家包 engagement 取数并回填 published-track → 📊 阈值检查(--check) → 🧬 DNA 评估(聚合+归因) → 📝 评估报告 → 👤 用户逐条确认 → 🔁 专家包 style-dna 更新 DNA
```

### 触发机制：数据采集每天跑，评估按量触发

- **定时取数**：用户启用后由独立 Automation 按约定频率调用各平台专家包 engagement 工具，回填 published-track；默认不创建每日任务。
- **按量**：每个（平台, DNA）的**成熟待评估记录**累积 **≥5 条**时评估一轮。成熟 = 发布 ≥3 天（数据稳定）；待评估 = `perf_evaluated=0` 且 `dna_id` 非空。一轮评估覆盖该 DNA 全部待评估记录（可多于 5 条）。
- **手动兜底**：低频 DNA 凑不满 5 条时，用户说「复盘一下这个 DNA」→ `--force` 强制评估。
- `dna_id=NULL`（历史补录/未归属）不参与 DNA 评估。

### 归因：共性步骤与原则

**原则**：

1. **归因方法平台特有，本技能不定义**：指标语义、互动路径（漏斗/完播/其他）、到 DNA 维度的映射、平台混杂因素清单，全部由该平台专家包 review workflow 提供。本技能只做平台无关的事：触发、聚合、归一化、趋势、报告结构。
2. **判定看相对值与走向**：绝对值只作上下文；`baseline_insufficient` 的记录只作绝对观察，不参与趋势结论。
3. **先排混杂再归因**：账号成熟度、粉丝自然增长、平台流量波动、选题热度、季节性等 DNA 之外能影响数据的因素，排除不了的，结论降级写「观察」不写「结论」。

**共性步骤**：

1. 读 `content-calibrator eval` 聚合 JSON：每篇绝对值 + 同账号比值 + 每指标趋势走向。
2. 对照 `<platform>/calibration/platform-state.json`、`audience.md` 了解账号阶段与受众背景。
3. 按该平台 review workflow 的归因方法，把趋势变化落到 DNA 的具体部分与维度（需回读 `{dna-id}.dna.md` / `{dna-id}.template.md` 与待评估作品原文，`source_folder` 可定位）。
4. 混杂排不掉 → 写「观察」；能归因 → 写「结论 + 建议」，每条建议注明改哪个维度 / template 部分。

---

## 评估产物

评估报告写入 Workspace：

```text
<platform>/dna/<dna-id>/evals/{YYYY-MM-DD}.eval.md
```

报告结构：

1. **整体判定**：这个 DNA 近期表现（趋势语言：改善 / 平稳 / 下滑），置信度与样本量。
2. **趋势表**：每指标的比值走势（引 `content-calibrator eval` 输出，不重算）。
3. **template 归因**：哪个 template 部分在起作用 / 拖后腿，证据是哪几篇（归因口径按平台 review workflow 的方法）。
4. **逐条优化建议**：每条 = 建议内容 + 目标维度/template 部分 + 证据篇目。供用户逐条确认。
5. **观察区**：归因不了但值得记录的信号（含混杂说明）。

写完报告后必须调 `--mark-evaluated` 标记覆盖的记录，防止下轮重复评估。

---

## 脚本

统一走顶层 wrapper `content-calibrator`（在 PATH 中，零路径拼接）。

### eval — DNA 表现评估聚合引擎（唯一数据入口）

```bash
# 廉价阈值检查（已启用的定时复盘调用，无触发时跳过后续评估）
content-calibrator eval --platform <platform> --check

# 聚合触发 DNA 的证据（绝对值 + 账号基线比值 + 趋势走向）
content-calibrator eval --platform <platform>

# 手动触发低频 DNA（不达阈值也评估）
content-calibrator eval --platform <platform> --dna-id <dna-id> --force

# 评估报告写完后标记（防重复评估）
content-calibrator eval --platform <platform> --mark-evaluated --ids 3,4,5
```

参数：`--min-samples 5`（触发阈值）、`--mature-days 3`（成熟窗口）、`--baseline-window 10`（账号基线取此前最多 N 篇均值）。须从 Workspace 根调用。

基线语义：同账号**此前**（发布日更早）最多 N 篇的指标均值，避免后视；此前 <3 篇 → `baseline_insufficient`。`account` 为空的记录归入未知账号组，不与其他账号混算。

### query-metrics — 单篇指标查询

```bash
content-calibrator query-metrics --platform <platform> --source-folder <work 目录>
```

### init — 平台初始化

```bash
content-calibrator init --platform <platform_id>
```

幂等。创建 `<platform>/calibration/`，默认只含 `platform-state.json`（baseline 兜底参考）+ `audience.md`；存量旧点号文件 `.platform-state.json` 自动改名。对标记录（如 `benchmark.md`）不在默认初始化内，由 `account-benchmark` workflow 按需生成。

---

## 定时取数与复盘（用户启用后执行）

参考文件：[定时取数与 DNA 复盘](references/scheduled-review.md)。它是执行说明，文件存在不会开启调度；OpenClaw 2026.10.4 不再读取 workspace 的 HEARTBEAT.md。

### main 启用、调整和停用

1. 复用用户已明确的选择，补齐平台/账号、频率或时间与 IANA 时区、是否连带 DNA 评估、报告渠道/account/收件人。只开启用户要求的部分；不因为安装技能就自动启用取数。
2. 读取参考，核对实际可用技能和目标 workspace。将参考的真实绝对路径、用户选定范围、已有任务 ID、时间/时区、结果去向和维护授权交给 IT engineer；由 IT 把执行说明写入独立 Automation 的 payload 或 main workspace 的任务说明文件，并在 payload 中显式引用。
3. 执行 agent 必须是 main，通常使用 isolated 会话。参考目前覆盖 douyin、xhs、wx_channel、wx_mp；其他平台按对应专家包另行核实，不从此模板推断已支持定时取数。
4. IT 回报 jobId、执行 agent、schedule/时区、enabled、nextRunAt 和 delivery 后，main 记录已确认的任务事实及 ID。MEMORY 中的登记方便维护，实际启停以原生任务为准；登记内容不能代替任务的执行上下文。
5. 调整或停用时把既有 jobId 交给 IT，更新/暂停原任务；先核对旧心跳 scratch 或 Doctor 已转换的任务，避免新旧两套重复取数，不为改一项业务停掉整个 main 心跳。

### 每次任务运行

按参考顺序完成平台取数、阈值检查、对应专家包 review 和汇总。只取数的任务跳过 DNA 评估；复盘不重复取数，缺项/过期数据如实标注。评估只产出报告与建议，DNA 更新须用户逐条确认。

定时任务由 main 在本次运行中顺序执行，不把整轮再次委托为子任务，不在运行中修改自身调度。技术故障记录后继续其他平台，汇总交 main 后续派 IT；认证失效不自动登录。报告由 Automation delivery 统一投递，任务正文不重复发送。

---

## Status — 状态看板

向用户报告校准状态时展示：

```
🧬 Content Calibrator 状态（DNA 表现评估）

【平台】<platform>：baseline 未定 / 已定
【待评估】<dna-id>：3/5 条成熟记录（未触发）
【最近评估】<platform>/dna/<dna-id>/evals/<date>.eval.md — 判定：改善
【待确认建议】2 条
```

数据来源：`content-calibrator eval --check` + `<platform>/dna/*/evals/` 目录。

---

## 历史说明

本技能前身为「内容校准预测循环」（统一 rubric 打分 + 盲预测 + 阈值门 + bump 升级）。2026-08-20 起 rubric 体系废除：发布前不再打分，判断准则不再是独立进化对象，发布数据直接关联 DNA（`pub_*` 表 `dna_id` 列）做表现评估。DB 中 `cal_*` 列为历史兼容保留。
