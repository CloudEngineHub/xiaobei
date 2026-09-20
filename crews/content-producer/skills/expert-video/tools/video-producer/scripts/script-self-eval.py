#!/usr/bin/env python3
"""Stage 2 — script-self-eval：按 workflow 的自检标准给 script 打分。

Usage:
  python3 scripts/script-self-eval.py <project_dir>

入：project_dir/script/script.md（Stage 1）+ project_dir/brief.md（读 workflow）
出：project_dir/script/self-eval.json（N 维分 1–5 + 总评 + 是否必返工）

自检维度按 Brief 的 workflow 变体（脚手架据此落对应模板）：
- 未指定 workflow → 通用五维（可拍化 / 场次 / 对白格式 / cues 齐）
- reversal-ad     → GATE A 四问 + 叙事闭环 + 合规
- narration-video → 口播稿落稿锁定模式（只检查不改写）或旁白稿规范
- collage-broll   → 隐喻自检五条

agent 据此逐维打分填 self-eval.json。脚本不做 NLP 判分——是 agent 的自检脚手架。
任一维 <3 必返工；落稿锁定模式只检查不改写，问题报甲方。
"""

import argparse
import json
import sys
from pathlib import Path

import _brief


def die(msg: str) -> None:
    print(f"[error] {msg}", file=sys.stderr)
    sys.exit(1)


GENERIC_DIMS = [
    ("filmable", "可拍化", "无不可见物描写（'想起了'/'觉得'改外化动作）"),
    ("scene_split", "场次划分", "同时间同地点一场"),
    ("dialog_format", "对白格式", "引号「」统一"),
    ("enhancement_cues", "enhancement_cues 六型齐", "动作/表情/环境/心理外化/节奏/视觉锚点"),
    ("delivery_cues", "delivery_cues 齐", "语气/语速/重音/情感控制"),
]

REVERSAL_DIMS = [
    ("setup_credible", "铺垫可信", "反转点之前观众会认真相信这是纯内容视频（零广告感）"),
    ("twist_magnitude", "反转幅度", "反转瞬间能让观众脱口而出「万万没想到」（题材/身份/场景/情绪跳得够远）"),
    ("twist_smoothing", "接入丝滑", "接入句因果一句话可复述（自问自答/因果链/意象复用，非硬切）"),
    ("cta_story", "CTA 剧情化", "设二次反转时 CTA 动机由剧情给出（未设则记 5 并注明未设）"),
    ("narrative_loop", "叙事单线闭环", "节拍 ≤6、句间因果可追、无断头线；意象桥成立（产品段第一镜复用正文核心意象）"),
    ("compliance", "合规", "正片零 URL/域名/联系方式，无收益承诺，产品能力不越 Brief"),
]

NARRATION_LOCK_DIMS = [
    ("verbatim", "逐字一致", "与甲方 voiceover.md 逐字一致（落稿锁定只检查不改写，问题报甲方）"),
    ("duration_fit", "时长适配", "文案长度适配 Brief 时长带（语速 6–8 字/秒；超带报甲方定夺）"),
    ("compliance", "合规", "无越 Brief 的品牌事实、承诺与红线内容"),
]

NARRATION_TEXT_DIMS = [
    ("filmable", "可配画面", "每句可独立配画面（抽象概念落到具体视觉）"),
    ("core_alignment", "核心传达一致", "旁白与 Brief 核心传达 / CTA 要求一致"),
    ("duration_fit", "时长适配", "语速 6–8 字/秒下适配 Brief 时长带"),
    ("delivery_cues", "delivery_cues 齐", "语气/语速/重音/情感控制"),
]

RECORDING_DIMS = [
    ("timeline_complete", "时间轴完整", "句 → 时间段 → 画面对应齐全（时间戳 Stage 11 场景 D ASR 后回填）"),
    ("duration_fit", "时长适配", "录音总长与 Brief 时长带匹配"),
]

COLLAGE_DIMS = [
    ("single_metaphor", "单一隐喻", "一条文稿只表达一个清晰隐喻，不逐字进画面"),
    ("object_count", "物件 3–6", "关键物件 3–6 个，不是满屏碎片"),
    ("color_semantics", "色彩语义", "底色与点色按语义色场表选，有理由"),
    ("batch_narrative", "批量叙事", "批量时前后叙事成立，或每条独立成立"),
    ("translatability", "可转译", "隐喻一眼可懂、可拆 3–6 个可分离纸片组供静帧生成"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 2 script-self-eval（按 workflow 自检标准）")
    parser.add_argument("project_dir", help="项目目录（CP 自建工作区 output_videos/<topic-en-slug>/）")
    args = parser.parse_args()

    project = Path(args.project_dir).resolve()
    script_path = project / "script" / "script.md"
    if not script_path.is_file():
        die(f"前置缺失: script.md 不存在，先跑 script-write（Stage 1）")

    brief_text = _brief.read_brief(project)
    workflow = _brief.parse_workflow(brief_text)
    vo_mode, _ = _brief.detect_voiceover(project, brief_text)

    # 维度按 workflow + 口播交付形态选择
    if workflow == "reversal-ad":
        dims, mode_note = REVERSAL_DIMS, "reversal-ad：GATE A 四问质检标准"
    elif workflow == "collage-broll":
        dims, mode_note = COLLAGE_DIMS, "collage-broll：隐喻自检（GATE A 质检标准）"
    elif workflow == "narration-video" and vo_mode in ("voiceover", "recording"):
        dims, mode_note = (NARRATION_LOCK_DIMS if vo_mode == "voiceover" else RECORDING_DIMS), \
            f"narration-video · {'口播稿落稿锁定——只检查不改写，问题报甲方' if vo_mode == 'voiceover' else '真人录音定稿——只检查排布计划'}"
    elif workflow == "narration-video":
        dims, mode_note = NARRATION_TEXT_DIMS, "narration-video · TTS 旁白稿规范"
    else:
        dims, mode_note = GENERIC_DIMS, "通用五维（未指定 workflow）"

    eval_path = project / "script" / "self-eval.json"
    eval_path.parent.mkdir(parents=True, exist_ok=True)

    # checkpoint
    if eval_path.is_file():
        existing = json.loads(eval_path.read_text(encoding="utf-8"))
        print(f"[checkpoint] self-eval.json 已存在：")
        print(json.dumps(existing, ensure_ascii=False, indent=2))
        return

    stub = {
        "stage": "2",
        "workflow": workflow,
        "mode": mode_note,
        "dims": [
            {"key": k, "name": n, "criteria": c, "score": None, "note": ""}
            for k, n, c in dims
        ],
        "overall": None,
        "must_rework": None,
        "instruction": (
            f"agent 据每维 criteria 打分 1–5，note 写扣分理由。任一维 <3 必须 rework（重跑 script-write 改对应段后再跑本评估）。"
            + ("落稿锁定模式：只检查不改写——发现问题报甲方，不自行改稿。" if workflow == "narration-video" and vo_mode == "voiceover" else "")
        ),
    }
    eval_path.write_text(json.dumps(stub, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] self-eval.json 模板已落（{mode_note}）：{eval_path}")
    if workflow == "collage-broll":
        print("[next] agent 逐维打分 → 全维 ≥3 后 GATE A 呈交隐喻清单 → 批准后进 Phase 2 静帧生成（不走 storyboard-build）")
    elif workflow == "reversal-ad":
        print("[next] agent 逐维打分（四问答案随 GATE A 呈交）→ 全维 ≥3 跑 storyboard-build（Stage 3）")
    else:
        print("[next] agent 逐维打分 → 任一维 <3 必返工 → 全维 ≥3 跑 storyboard-build（Stage 3）")


if __name__ == "__main__":
    main()
