#!/usr/bin/env python3
"""audio-mix — 多轨混音：指定多条音轨 + 各自起始延时和音量，输出混合音频。

原子工具，不写死 Workflow。agent 按 SKILL.md 场景化组合调用。

Usage:
  # 混三条音轨：旁白（0s 入，1.0 音量）+ BGM（5s 入，0.15 音量）+ 口播（10s 入，0.8 音量）
  python3 scripts/audio-mix.py \
    --track narration.mp3 --delay 0 --volume 1.0 \
    --track bgm.mp3 --delay 5 --volume 0.15 \
    --track voiceover.mp3 --delay 10 --volume 0.8 \
    --output mixed.mp3

  # 混两条音轨，指定总时长（短于总时长则 pad 静音到该时长）
  python3 scripts/audio-mix.py \
    --track narration.mp3 --delay 0 --volume 1.0 \
    --track bgm.mp3 --delay 2 --volume 0.2 \
    --output mixed.mp3 --duration 30

  # BGM 首尾 fade（--fadein/--fadeout 按 --track 顺序对应，缺省补 0）
  python3 scripts/audio-mix.py \
    --track narration.mp3 --delay 0 --volume 1.0 \
    --track bgm.mp3 --delay 0 --volume 0.22 --fadein 0.8 --fadeout 2.2 \
    --output mixed.wav --duration 85.6

参数说明：
  --track   音轨（可重复多次，每次跟 --delay 和 --volume）
  --delay   该轨起始延时（秒，默认 0）
  --volume  该轨音量系数（0.0-1.0，默认 1.0；0.15 = 压到 15%）
  --fadein  该轨淡入时长（秒，默认 0；从轨自身内容起点开始淡入）
  --fadeout 该轨淡出时长（秒，默认 0；锚定在轨有效末端 = min(轨实测时长, --duration - delay)）
  --output  输出混合音频路径
  --duration 输出总时长（秒，可选；不传则取最长轨延时+时长）。
            硬上限语义：短轨 apad 补虚到该时长，超出的轨被截断（等效 atrim）

实现：ffmpeg afade（淡入淡出，轨本地时间轴）+ adelay（毫秒延时）+ volume（音量）
+ apad（补虚到 --duration）+ amix（叠加）。
afade 放在 adelay 之前：fade 作用于轨自身内容，不受延时平移影响。
延时用 adelay=<ms>；--duration 时 apad=whole_dur=<dur> 把每轨补虚到总时长；
amix inputs=N duration=longest dropout_transition=0 normalize=0——
normalize=0 禁用 amix 自动除以轨道数，每轨 volume 即最终音量（设 2.0 就是 2 倍，不被稀释）。
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def die(msg: str) -> None:
    print(f"[error] {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    print(f"[cmd] {cmd[0]} ... ({len(cmd)} args)")
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        die(f"命令失败 (rc={p.returncode}): {p.stderr[:500] or p.stdout[:500]}")
    return p


def probe_duration(path: Path) -> float:
    p = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
        capture_output=True, text=True,
    )
    if p.returncode != 0:
        return 0.0
    try:
        return float(json.loads(p.stdout).get("format", {}).get("duration", 0) or 0)
    except (ValueError, json.JSONDecodeError):
        return 0.0


def fade_chain(fadein: float, fadeout: float, track: str, delay: float,
               duration: float | None) -> list[str]:
    """构造该轨的 afade 滤镜段（轨本地时间轴，adelay 之前生效）。

    fadein：st=0 起淡入 fadein 秒。
    fadeout：锚定有效末端 eff = min(轨实测时长, duration - delay)，st = eff - fadeout。
    """
    parts: list[str] = []
    if fadein > 0:
        parts.append(f"afade=t=in:st=0:d={fadein}")
    if fadeout > 0:
        track_dur = probe_duration(Path(track))
        if track_dur <= 0:
            die(f"--fadeout 需要实测轨时长，ffprobe 失败: {track}")
        eff = track_dur
        if duration is not None:
            eff = min(eff, duration - delay)
        st = eff - fadeout
        if st < 0:
            die(f"--fadeout {fadeout}s 超过轨 {Path(track).name} 的有效时长 {eff:.3f}s")
        parts.append(f"afade=t=out:st={st:.3f}:d={fadeout}")
    return parts


def main() -> None:
    parser = argparse.ArgumentParser(description="audio-mix 多轨混音")
    parser.add_argument(
        "--track", action="append", required=True,
        help="音轨文件路径（可重复多次）",
    )
    parser.add_argument(
        "--delay", action="append", type=float, default=None,
        help="该轨起始延时（秒，默认 0；按 --track 顺序对应）",
    )
    parser.add_argument(
        "--volume", action="append", type=float, default=None,
        help="该轨音量系数（0.0-1.0，默认 1.0；按 --track 顺序对应）",
    )
    parser.add_argument(
        "--fadein", action="append", type=float, default=None,
        help="该轨淡入时长（秒，默认 0；按 --track 顺序对应）",
    )
    parser.add_argument(
        "--fadeout", action="append", type=float, default=None,
        help="该轨淡出时长（秒，默认 0；锚定轨有效末端，按 --track 顺序对应）",
    )
    parser.add_argument("--output", required=True, help="输出混合音频路径")
    parser.add_argument("--duration", type=float, default=None,
                        help="输出总时长（秒，可选；硬上限：短轨补虚、超出轨截断）")
    args = parser.parse_args()

    tracks = args.track
    n = len(tracks)

    # delay/volume/fadein/fadeout 按 track 顺序对应，缺省补默认值
    delays = args.delay if args.delay else []
    delays += [0.0] * (n - len(delays))
    volumes = args.volume if args.volume else []
    volumes += [1.0] * (n - len(volumes))
    fadeins = args.fadein if args.fadein else []
    fadeins += [0.0] * (n - len(fadeins))
    fadeouts = args.fadeout if args.fadeout else []
    fadeouts += [0.0] * (n - len(fadeouts))

    if len(delays) != n or len(volumes) != n:
        die(f"--delay / --volume 数量须等于 --track 数量（{n}）")
    if len(fadeins) != n or len(fadeouts) != n:
        die(f"--fadein / --fadeout 数量须等于 --track 数量（{n}）")
    if any(f < 0 for f in fadeins + fadeouts):
        die("--fadein / --fadeout 必须 >= 0")

    # 校验各轨文件存在
    for t in tracks:
        if not Path(t).is_file():
            die(f"音轨不存在: {t}")

    dst = Path(args.output).resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)

    # ffmpeg filter_complex 构造：
    # [i:a]afade...,adelay=<ms>,volume=<v>,apad=whole_dur=<dur>[a<i>]  各轨淡入出+延时+音量+补虚
    # [a0][a1]...[aN]amix=inputs=N:duration=longest:dropout_transition=0:normalize=0[aout]
    # normalize=0 禁用 amix 自动除以轨道数，每轨 volume 即最终音量（设 2.0 就是 2 倍，不被稀释）
    # apad=whole_dur=<dur> 把每轨补虚到 --duration 总时长，避免短轨被截、输出时长不足
    # afade 在 adelay 前：fade 作用于轨本地时间轴，不被延时平移
    inputs: list[str] = []
    filter_parts: list[str] = []
    dur_ms = int(args.duration * 1000) if args.duration is not None else None
    for i, (delay_s, vol, fi, fo) in enumerate(zip(delays, volumes, fadeins, fadeouts)):
        inputs.extend(["-i", tracks[i]])
        delay_ms = int(delay_s * 1000)
        parts = fade_chain(fi, fo, tracks[i], delay_s, args.duration)
        if delay_ms > 0:
            # all=1：所有声道统一延时（否则立体声轨只延左声道，声像错位）
            parts.append(f"adelay={delay_ms}:all=1")
        if vol != 1.0:
            parts.append(f"volume={vol}")
        if dur_ms is not None:
            # apad=whole_dur 是样本数（ms 级近似），确保该轨至少到 --duration 总时长
            parts.append(f"apad=whole_dur={args.duration}")
        if parts:
            filter_parts.append(f"[{i}:a]" + ",".join(parts) + f"[a{i}]")
        else:
            filter_parts.append(f"[{i}:a]anull[a{i}]")

    mix_inputs = "".join(f"[a{i}]" for i in range(n))
    # duration=longest + normalize=0：取最长轨时长，每轨音量不被稀释
    filter_parts.append(
        f"{mix_inputs}amix=inputs={n}:duration=longest:dropout_transition=0:normalize=0[aout]"
    )

    filter_complex = ";".join(filter_parts)

    cmd = ["ffmpeg", "-y"]
    cmd.extend(inputs)
    cmd.extend(["-filter_complex", filter_complex, "-map", "[aout]"])

    # 输出格式按扩展名推断（默认 mp3）
    ext = dst.suffix.lower().lstrip(".")
    if ext in ("wav",):
        cmd.extend(["-c:a", "pcm_s16le"])
    elif ext in ("ogg",):
        cmd.extend(["-c:a", "libvorbis"])
    else:
        cmd.extend(["-c:a", "libmp3lame", "-b:a", "192k"])

    if args.duration is not None:
        cmd.extend(["-t", str(args.duration)])

    cmd.append(str(dst))
    run(cmd)

    print(f"[done] 混合音频已落：{dst}")
    print(f"  - {n} 轨混入")
    for i, (t, d, v, fi, fo) in enumerate(zip(tracks, delays, volumes, fadeins, fadeouts)):
        fades = f"  fadein={fi}s fadeout={fo}s" if (fi > 0 or fo > 0) else ""
        print(f"  [{i}] {Path(t).name}  delay={d}s  volume={v}{fades}")
    if args.duration is not None:
        print(f"  - 总时长限制：{args.duration}s")


if __name__ == "__main__":
    main()
