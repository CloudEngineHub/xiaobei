#!/usr/bin/env python3
"""Stage 3b — script-self-eval：剧本自评 N 维打分，任一维 <3 必返工。

Usage:
  python3 scripts/script-self-eval.py <project_dir>

入：project_dir/script/script.md（Stage 3）
出：project_dir/script/self-eval.json（N 维分 1–5 + 总评 + 是否必返工）

N 维（硬约束六条）：
1. 可拍化：无不可见物描写
2. 场次划分：同时间同地点一场
3. 对白格式：引号统一
4. enhancement_cues：六型齐
5. delivery_cues：语气/语速/重音齐
6. 镜头数预算：在 intent.json 的 min-max 区间

agent 据此逐维打分填 self-eval.json。脚本不做 NLP 判分——是 agent 的自检脚手架。
"""

import argparse
import json
import sys
from pathlib import Path

EVAL_DIMS = [
    ("filmable", "可拍化", "无不可见物描写（'想起了'/'觉得'改外化动作）"),
    ("scene_split", "场次划分", "同时间同地点一场"),
    ("dialog_format", "对白格式", "引号「」统一"),
    ("enhancement_cues", "enhancement_cues 六型齐", "动作/表情/环境/心理外化/节奏/视觉锚点"),
    ("delivery_cues", "delivery_cues 齐", "语气/语速/重音/情感控制"),
    ("shot_count", "镜数在预算区间", "intent.json 的 min-max"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 3b script-self-eval")
    parser.add_argument("project_dir", help="项目目录（CP 自建工作区 output_videos/<topic-en-slug>/）")
    args = parser.parse_args()

    project = Path(args.project_dir).resolve()
    script_path = project / "script" / "script.md"
    if not script_path.is_file():
        die(f"前置缺失: script.md 不存在，先跑 script-write（Stage 3）")

    eval_path = project / "script" / "self-eval.json"
    eval_path.parent.mkdir(parents=True, exist_ok=True)

    # checkpoint
    if eval_path.is_file():
        existing = json.loads(eval_path.read_text(encoding="utf-8"))
        print(f"[checkpoint] self-eval.json 已存在：")
        print(json.dumps(existing, ensure_ascii=False, indent=2))
        return

    stub = {
        "stage": "3b",
        "dims": [
            {"key": k, "name": n, "criteria": c, "score": None, "note": ""}
            for k, n, c in EVAL_DIMS
        ],
        "overall": None,
        "must_rework": None,
        "instruction": "agent 据每维 criteria 打分 1–5，note 写扣分理由。任一维 <3 必须 rework（重跑 script-write 改对应段后再跑本评估）。",
    }
    eval_path.write_text(json.dumps(stub, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] self-eval.json 模板已落：{eval_path}")
    print(f"[next] agent 逐维打分 → 任一维 <3 必返工 → 全维 ≥3 跑 storyboard-build（Stage 4）")


if __name__ == "__main__":
    main()
