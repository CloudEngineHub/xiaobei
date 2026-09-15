#!/usr/bin/env python3
"""Stage 3 — script-write：故事 → 分场剧本。

Usage:
  python3 scripts/script-write.py <project_dir>

入：project_dir/script/story.md（Stage 2）
出：project_dir/script/script.md（分场剧本，含 enhancement_cues 六型 + delivery_cues）

剧本硬约束：
- 同时间同地点分一场
- 可拍化描述（不写不可见物）
- 对白引号格式统一
- enhancement_cues 六型：动作/表情/环境/心理/节奏/视觉锚点
- delivery_cues：交付旁白时的语气/语速/重音指令（后续 awk-tts / 内置 TTS 用）
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 3 script-write")
    parser.add_argument("project_dir", help="项目目录（CP 自建工作区 output_videos/<topic-en-slug>/）")
    args = parser.parse_args()

    project = Path(args.project_dir).resolve()
    story_path = project / "script" / "story.md"
    if not story_path.is_file():
        die(f"前置缺失: story.md 不存在，先跑 story-develop（Stage 2）")

    script_path = project / "script" / "script.md"
    script_path.parent.mkdir(parents=True, exist_ok=True)

    # checkpoint
    if script_path.is_file():
        print(f"[checkpoint] script.md 已存在，沿用：{script_path}")
        return

    stub = f"""# 分场剧本（Stage 3）

> 据故事梗概（{story_path.name}）拆成可拍化分场剧本。每场含：场景描述、出场人物、对白、动作、enhancement_cues、delivery_cues。

## 场 1：（场名，如"主角家中—清晨")

### 场景描述
> agent 填。可拍化——只写镜头能看到的。不写"她想起了童年"（不可见），改写"她抚摸旧照片，眼神放空"。

### 出场人物
- （人物）：（本场动作）

### 对白与动作
> agent 填。对白用引号「」统一格式。动作写括号内。
主角：「（对白）」（动作：抚摸照片）

### enhancement_cues（六型，agent 据本场填）
> 六型：动作 / 表情 / 环境 / 心理外化 / 节奏 / 视觉锚点
- 动作：（agent 填，如"缓慢翻页"）
- 表情：（agent 填，如"眼神放空"）
- 环境：（agent 填，如"晨光透过窗帘"）
- 心理外化：（agent 填，如"重复抚摸同张照片"）
- 节奏：（agent 填，如"慢板，停顿多"）
- 视觉锚点：（agent 填，如"旧照片特写"）

### delivery_cues（旁白指令，后续 awk-tts / 内置 TTS 用）
> agent 填。语气 / 语速 / 重音 / 情感控制。
- 语气：（agent 填，如"怀念"）
- 语速：（agent 填，如"慢"）
- 重音：（agent 填，如"童年"）
- 情感控制：（agent 填，如"用怀念温暖的语气"，传 awk-tts --context-text）

## 场 2（如有）
（agent 同上填）
"""
    script_path.write_text(stub, encoding="utf-8")
    print(f"[done] script.md 模板已落：{script_path}")
    print(f"[next] agent 填剧本 → 跑 script-self-eval（Stage 3b）")


if __name__ == "__main__":
    main()
