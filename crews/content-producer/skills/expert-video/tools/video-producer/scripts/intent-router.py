#!/usr/bin/env python3
"""Stage 1 — intent-router：把 Brief 意图路由成三档脚本模板。

三档（内部 key 保留英文，user-facing 表述用中文名）：
- narrative（故事讲述型）——重情节、有人物弧光、含旁白 → 默认 3–5 镜/场
- motion（纯画面动效型）——重节奏感/视觉冲击/少对白 → 默认 5–8 镜快切
- montage（蒙太奇剪接型）——重氛围/抽象/纯视觉 → 默认 4–7 镜无叙事

Usage:
  video-producer intent-router <project_dir> [--user-text "..."] [--report-file path]

入：project_dir（CP 自建工作区 output_videos/<topic-en-slug>/），可选甲方原文或参考拆解报告路径
出：project_dir/script/intent.json（档位 + 主题 + 受众 + 时长目标 + 备选 + 决策理由）

产物文件存在性即 checkpoint：intent.json 已存在则打印现状退出，不重生成（用户手改后续跑）。
"""

import argparse
import json
import sys
from pathlib import Path

VALID_GENRES = {"narrative", "motion", "montage"}
DURATION_DEFAULTS = {"narrative": 30, "motion": 25, "montage": 20}
SHOT_DEFAULTS = {"narrative": (3, 5), "motion": (5, 8), "montage": (4, 7)}


def die(msg: str) -> None:
    print(f"[error] {msg}", file=sys.stderr)
    sys.exit(1)


def detect_genre(text: str) -> tuple[str, str]:
    """从用户文本特征粗判档位。返 (genre, reason)。"""
    lower = text.lower()
    if any(k in lower for k in ["故事", "情节", "人物", "弧光", "narrative", "story", "plot", "character"]):
        return "narrative", "用户提及故事/情节/人物"
    if any(k in lower for k in ["节奏", "冲击", "快切", "motion", "beat", "impact", "rhythm"]):
        return "motion", "用户提及节奏/冲击/快切"
    if any(k in lower for k in ["氛围", "抽象", "纯视觉", "montage", "vibe", "abstract", "atmosphere"]):
        return "montage", "用户提及氛围/抽象/纯视觉"
    return "narrative", "无明确信号，退默认 narrative（最通用）"


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 1 intent-router")
    parser.add_argument("project_dir", help="项目目录（CP 自建工作区 output_videos/<topic-en-slug>/）")
    parser.add_argument("--user-text", default=None, help="甲方原文（Brief 主题句或用户描述）")
    parser.add_argument("--report-file", default=None, help="甲方给的参考拆解报告路径（可选）")
    parser.add_argument("--genre", default=None, choices=sorted(VALID_GENRES), help="强制档位，跳过自动判定")
    parser.add_argument("--duration", type=int, default=None, help="时长目标（秒），不传走档位默认")
    parser.add_argument("--audience", default=None, help="受众描述")
    args = parser.parse_args()

    project = Path(args.project_dir).resolve()
    if not project.is_dir():
        die(f"project_dir 不存在或非目录: {args.project_dir}")
    intent_path = project / "script" / "intent.json"
    intent_path.parent.mkdir(parents=True, exist_ok=True)

    # checkpoint：产物已存在则不重生成
    if intent_path.is_file():
        existing = json.loads(intent_path.read_text(encoding="utf-8"))
        print(f"[checkpoint] intent.json 已存在，沿用：")
        print(json.dumps(existing, ensure_ascii=False, indent=2))
        return

    text = args.user_text or ""
    if not text and args.report_file:
        report = Path(args.report_file)
        if report.is_file():
            text = report.read_text(encoding="utf-8")[:2000]

    if not text:
        die("需 --user-text 或 --report-file 之一作为意图来源")

    genre, reason = (args.genre, "用户强制档位") if args.genre else detect_genre(text)
    duration = args.duration or DURATION_DEFAULTS[genre]
    shot_min, shot_max = SHOT_DEFAULTS[genre]

    intent = {
        "stage": 0,
        "genre": genre,
        "topic": text[:200],
        "audience": args.audience or "未指定",
        "duration_target": duration,
        "shot_count": {"min": shot_min, "max": shot_max},
        "decisions": [
            {
                "choice": f"genre={genre}",
                "alternatives": sorted(VALID_GENRES - {genre}),
                "confidence": 0.7 if not args.genre else 1.0,
                "reason": reason,
            }
        ],
    }
    intent_path.write_text(json.dumps(intent, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] 路由完成：genre={genre} duration={duration}s shots={shot_min}-{shot_max}")
    print(f"[done] 产物：{intent_path}")
    print(f"[next] 跑 story-develop（Stage 2）")


if __name__ == "__main__":
    main()
