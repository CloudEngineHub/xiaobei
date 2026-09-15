#!/usr/bin/env python3
"""Stage 11 — mix-audio：配音配乐三场景分流。

Usage:
  python3 scripts/mix-audio.py <project_dir>

入：project_dir/script/script.md（含 delivery_cues / 对白 / 旁白标记）
出：project_dir/audio/ 目录 + subtitles.srt 模板
    （实际音频产物由 agent 按下方三场景路径生成）

三场景分流（agent 按 script.md 实际内容判断走哪条）：

  A. 人物对话 → 声画同出
     aigc-video-gen i2v 渲染时人物对白自带语音，不单独做 TTS。
     本场景无需 mix-audio 处理，直接进 assemble。

  B. 旁白 → 一次性 TTS + ASR 对齐
     1. agent 把整片旁白词写好，一次性 TTS 生成 audio/narration.mp3
        （保证语音一致性，不要分段生成）
     2. 跑 narration-align（Stage 11b）：
        python3 scripts/narration-align.py <project_dir>
        → 调火山 ASR 极速版对 narration.mp3 转写，输出
        audio/narration-segments.json（utterance 级真实时间戳，秒）
     3. agent 拿 segments 按 shot 时长切片对应，assemble 时混入

  C. 背景音乐 → 成片合成后一次性生成/下载
     1. 成片 video.mp4 合好后，按成片时长统一生成或下载 BGM
     2. 落 audio/bgm.mp3，assemble 时混入
     BGM 可选路径：
       - pexels-footage / pixabay-footage 搜 background music
       - 静音占位（无 BGM 需求时）

混合场景：A+B+C、B+C、A+C 均可能，agent 按 script.md 判断。
"""

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 11 mix-audio")
    parser.add_argument("project_dir", help="项目目录（CP 自建工作区 output_videos/<topic-en-slug>/）")
    args = parser.parse_args()

    project = Path(args.project_dir).resolve()
    script_path = project / "script" / "script.md"
    if not script_path.is_file():
        die(f"前置缺失: script.md 不存在")

    audio_dir = project / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    # srt 占位模板
    srt = audio_dir / "subtitles.srt"
    if not srt.is_file():
        srt.write_text(
            "1\n00:00:00,000 --> 00:00:03,000\n（agent 据对白+旁白填字幕）\n",
            encoding="utf-8",
        )

    print(f"[done] audio/ 目录已建 + subtitles.srt 模板已落")
    print()
    print("=== 配音配乐三场景分流（agent 按 script.md 判断走哪条）===")
    print()
    print("A. 人物对话 → 声画同出")
    print("   aigc-video-gen i2v 渲染时人物对白自带语音，不单独做 TTS。")
    print("   本场景无需 mix-audio，直接进 assemble。")
    print()
    print("B. 旁白 → 一次性 TTS 带字级时间戳 + 对齐")
    print("   1. agent 把整片旁白词写好，一次性 TTS 生成 audio/narration.mp3")
    print("      （保证语音一致性，不要分段生成）")
    print("      调 awk-tts 时加 --enable-subtitle，火山单向流式 HTTP 原生返回")
    print("      字级时间戳（sentence.words 带 startTime/endTime，秒），")
    print("      awk-tts 自动落盘 audio/narration.subtitle.json")
    print("   2. 跑 narration-align（Stage 11b）：")
    print("        python3 scripts/narration-align.py <project_dir>")
    print("      → 优先复用 narration.subtitle.json（TTS 原生字级时间戳，零额外调用）")
    print("      → 缺失时回退火山 ASR 极速版转写 narration.mp3")
    print("      → 输出 audio/narration-segments.json（统一 segments 格式）")
    print("   3. agent 拿 segments 按 shot 时长切片对应，assemble 时混入")
    print()
    print("C. 背景音乐 → 成片合成后一次性生成/下载")
    print("   1. 成片 video.mp4 合好后，按成片时长统一生成或下载 BGM")
    print("   2. 落 audio/bgm.mp3，assemble 时混入")
    print("   BGM 可选路径：")
    print("     - pexels-footage / pixabay-footage 搜 background music")
    print("     - 静音占位（无 BGM 需求时）")
    print()
    print("混合场景：A+B+C、B+C、A+C 均可能，agent 按 script.md 判断。")
    print()
    print("D. 用户口播录音 → ASR 时间戳 → 按时间戳补素材")
    print("   1. agent 把用户给的口播录音落 audio/voiceover.<ext>")
    print("   2. 调火山 ASR 极速版转写口播录音，拿 utterance 级真实时间戳")
    print("      （凭据复用 viral-chaser 同池 VOLC_ASR_*，与 narration-align 回退路径同一接口）")
    print("   3. agent 按时间戳把口播内容切成段，每段对应一个 shot 时长区间")
    print("   4. 按 shot 段内容补素材（pexels-footage / pixabay-footage / aigc-video-gen）")
    print("      ——口播内容直接当旁白用，无需另做 TTS；声画对齐靠 ASR 时间戳")
    print("   5. assemble 时把口播录音混入成片音轨")


def die(message: str) -> None:
    print(f"[error] {message}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
