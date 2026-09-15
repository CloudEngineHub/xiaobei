#!/usr/bin/env python3
"""Stage 2 — story-develop：idea → 故事（分场）。

Usage:
  python3 scripts/story-develop.py <project_dir>

入：project_dir/script/intent.json（Stage 0）
出：project_dir/script/story.md（100–200 词梗概 + 人物 + 分场）

场次划分原则：同时间同地点分一场。agent 按 SKILL.md 工作流填 story.md 模板。
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 2 story-develop")
    parser.add_argument("project_dir", help="项目目录（CP 自建工作区 output_videos/<topic-en-slug>/）")
    args = parser.parse_args()

    project = Path(args.project_dir).resolve()
    intent_path = project / "script" / "intent.json"
    if not intent_path.is_file():
        die(f"前置缺失: intent.json 不存在，先跑 intent-router（Stage 0）")

    story_path = project / "script" / "story.md"
    story_path.parent.mkdir(parents=True, exist_ok=True)

    # checkpoint
    if story_path.is_file():
        print(f"[checkpoint] story.md 已存在，沿用：{story_path}")
        return

    intent = json.loads(intent_path.read_text(encoding="utf-8"))
    stub = f"""# 故事梗概（Stage 2）

## 档位
{intent['genre']}（时长目标 {intent['duration_target']}s，{intent['shot_count']['min']}-{intent['shot_count']['max']} 镜）

## 受众
{intent['audience']}

## 梗概（100–200 词）
> agent 填。包含：开场钩子、主角、冲突、转折、结局。显式复述受众与类型（如"本片面向科技爱好者，类型为叙事短片"）。

## 人物
> agent 填。每个主要人物：姓名/称呼、年龄、身份、一句话性格、视觉锚点（外观特征，后续 character-register Stage 6 用）。

| 人物 | 年龄 | 身份 | 性格 | 视觉锚点 |
|------|------|------|------|---------|
| （agent 填） | | | | |

## 分场（同时间同地点分一场）
> agent 填。每场：地点、时间、出场人物、核心动作、叙事目的。

### 场 1
- 地点：（agent 填）
- 时间：（agent 填）
- 出场人物：（agent 填）
- 核心动作：（agent 填）
- 叙事目的：（agent 填，如"建立主角日常"）

### 场 2（如有）
（agent 填）
"""
    story_path.write_text(stub, encoding="utf-8")

    print(f"[done] story.md 模板已落：{story_path}")
    print(f"[next] agent 填梗概/人物/分场 → 跑 script-write（Stage 3）")


if __name__ == "__main__":
    main()
