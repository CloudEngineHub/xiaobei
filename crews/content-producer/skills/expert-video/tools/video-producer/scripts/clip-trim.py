#!/usr/bin/env python3
"""clip-trim — 精确切素材：入点/出点/倍速/归一化/调色/多窗拼接/定帧缓推，视频音频分别处理。

原子工具，不写死 Workflow。agent 按 SKILL.md 场景化组合调用。

Usage:
  # 切视频段（0.5s 入，2.3s 出，1.5x 倍速）
  python3 scripts/clip-trim.py --input shot.mp4 --output clip.mp4 --start 0.5 --end 2.3 --speed 1.5

  # 只切音频段（30s 入，35s 出，原速）
  python3 scripts/clip-trim.py --input narration.mp3 --output clip.mp3 --start 30 --end 35

  # 切片同时归一化到 1920x1080@25（scale+pad+sar+fps 一步，24fps 源混拼前必做）
  python3 scripts/clip-trim.py --input src.mkv --output clip.mp4 --start 12 --end 15.2 \
      --normalize 1920x1080@25

  # 一镜多窗：同源切两段按序 concat copy（窗口格式 start:length，逗号分隔）
  python3 scripts/clip-trim.py --input src.mkv --output clip.mp4 \
      --windows "12.0:3.2,44.5:1.4" --normalize 1920x1080@25

  # 暖色调色（预设色板，不做自由调色）
  python3 scripts/clip-trim.py --input src.mkv --output clip.mp4 --start 8 --end 12 --grade warm

  # 定帧缓推（Ken Burns）：视频源在 --start 取帧，或图片输入直接推
  python3 scripts/clip-trim.py --input src.mkv --output clip.mp4 --start 528 --zoompan 1.08 \
      --duration 4.2 --normalize 1920x1080@25
  python3 scripts/clip-trim.py --input still.png --output clip.mp4 --zoompan 1.08 --duration 4.2

参数说明：
  --input  输入素材路径（视频、音频或图片）
  --output 输出路径
  --start  入点（秒，默认 0；--zoompan 配视频源时 = 取帧时刻）
  --end    出点（秒，默认 = 输入全长；--windows/--zoompan 模式下忽略）
  --speed  倍速（默认 1.0；2.0 = 2x，0.5 = 0.5x）
  --sync-audio  视频倍速时同步音频倍速（用 atempo filter；超出 0.5-2.0 范围链式串联）
  --duration 输出时长（秒）：图片输入必填；--zoompan 配视频源必填；其余模式默认 (end-start)/speed
  --normalize WxH@FPS  切片时归一化：scale(保比缩小)+pad(黑边)+setsar=1+fps 一步
  --grade warm|neutral 预设调色（warm = colorbalance 暖调 + vignette 暗角；neutral = 不调）
  --windows "start:length,..."  一镜多窗：按序切多段再 concat copy（分段产物落 <output>.parts/，存在即跳过）
  --zoompan END_ZOOM   定帧缓推：END_ZOOM 为结束放大倍率（如 1.08 = 推到 108%），中心锚点匀速推近
  --low-load  低载编码（nice 19 + preset veryfast + crf 18 + threads 2，共享机器上的 brief 常用约束）
  --force  清 <output>.parts/ 与 <output>.zoompan/ 工作目录强制重切（源换内容但参数未变时用）

视频倍速原理：setpts=PTS/speed 改时间戳；音频 atempo=speed 改播放速率。
倍速后时长 = (end - start) / speed。切片起点走 input seek（源时间语义），倍速不改变入点位置。
checkpoint：--windows 分段与 --zoompan 定帧落工作目录（存在即跳过），带参数指纹——
windows/起点/归一/调色参数一变自动清场重切，不会静默复用陈旧内容。
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
GRADE_PRESETS = {
    # v4 已验证的暖调预设：colorbalance 暖移 + 轻暗角
    "warm": "colorbalance=rm=0.22:gm=0.07:bm=-0.18,vignette=angle=PI/5",
}
LOW_LOAD = {"preset": "veryfast", "crf": "18", "threads": "2", "nice": "19"}
NORMAL_ENCODE = {"preset": "fast", "crf": "23", "threads": None, "nice": None}
DUR_TOLERANCE = 0.12  # 输出时长 vs 期望的告警容差（秒）


def die(msg: str) -> None:
    print(f"[error] {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    print(f"[cmd] {cmd[0]} ... ({len(cmd)} args)")
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        die(f"命令失败 (rc={p.returncode}): {p.stderr[:500] or p.stdout[:500]}")
    return p


def maybe_nice(cmd: list[str], enc: dict) -> list[str]:
    return (["nice", "-n", enc["nice"]] if enc.get("nice") else []) + cmd


def encode_args(enc: dict) -> list[str]:
    out = ["-c:v", "libx264", "-preset", enc["preset"], "-crf", enc["crf"]]
    if enc.get("threads"):
        out += ["-threads", enc["threads"]]
    return out


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


def probe_size(path: Path) -> tuple[int, int] | None:
    """探测宽×高（图片或视频）。失败返回 None。"""
    p = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    out = p.stdout.strip()
    if not out:
        return None
    try:
        w, h = out.split(",")
        return (int(w), int(h))
    except (ValueError, IndexError):
        return None


def is_video(path: Path) -> bool:
    """用 ffprobe 看是否有视频流。"""
    p = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return p.stdout.strip() == "video"


def atempo_chain(speed: float) -> str:
    """atempo filter 链。atempo 单级范围 [0.5, 2.0]，超出则链式串联。
    例：4x → atempo=2.0,atempo=2.0；0.25x → atempo=0.5,atempo=0.5。"""
    if 0.5 <= speed <= 2.0:
        return f"atempo={speed}"
    parts = []
    remaining = speed
    while remaining > 2.0:
        parts.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        parts.append("atempo=0.5")
        remaining /= 0.5
    parts.append(f"atempo={remaining}")
    return ",".join(parts)


def audio_codec_args(dst: Path) -> list[str]:
    """音频编码参数按输出容器选（.mp3 不能封 aac——按扩展名分流）。"""
    ext = dst.suffix.lower()
    if ext == ".mp3":
        return ["-c:a", "libmp3lame", "-b:a", "192k"]
    if ext == ".wav":
        return ["-c:a", "pcm_s16le"]
    if ext == ".ogg":
        return ["-c:a", "libvorbis", "-b:a", "192k"]
    return ["-c:a", "aac", "-b:a", "192k"]


def parse_normalize(raw: str) -> tuple[int, int, float]:
    """'1920x1080@25' → (1920, 1080, 25.0)。"""
    m = re.fullmatch(r"(\d+)x(\d+)@(\d+(?:\.\d+)?)", raw.strip())
    if not m:
        die(f"--normalize 格式错误: {raw}（应为 WxH@FPS，如 1920x1080@25）")
    w, h, fps = int(m.group(1)), int(m.group(2)), float(m.group(3))
    if w % 2 or h % 2:
        die(f"--normalize 宽高必须为偶数（yuv420p 要求）: {raw}")
    if fps <= 0:
        die(f"--normalize fps 必须 > 0: {raw}")
    return w, h, fps


def parse_windows(raw: str) -> list[tuple[float, float]]:
    """'12.0:3.2,44.5:1.4' → [(12.0, 3.2), (44.5, 1.4)]（start:length）。"""
    windows: list[tuple[float, float]] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = re.fullmatch(r"(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)", chunk)
        if not m:
            die(f"--windows 窗口格式错误: {chunk}（应为 start:length，如 12.0:3.2）")
        start, length = float(m.group(1)), float(m.group(2))
        if length <= 0:
            die(f"--windows 窗口时长必须 > 0: {chunk}")
        windows.append((start, length))
    if not windows:
        die(f"--windows 解析不出任何窗口: {raw}")
    return windows


def build_vf(normalize: tuple[int, int, float] | None, grade: str,
             speed: float = 1.0, with_audio_pts: bool = True) -> list[str]:
    """视频滤镜链：[setpts] → [scale+pad] → [grade] → setsar → fps → format。"""
    parts: list[str] = []
    if with_audio_pts and speed != 1.0:
        parts.append(f"setpts=PTS/{speed}")
    if normalize:
        w, h, fps = normalize
        parts.append(f"scale={w}:{h}:force_original_aspect_ratio=decrease")
        parts.append(f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black")
    if grade != "neutral":
        parts.append(GRADE_PRESETS[grade])
    if normalize:
        w, h, fps = normalize
        parts += ["setsar=1", f"fps={fps}", "format=yuv420p"]
    return parts


def cut_once(src: Path, dst: Path, start: float, length: float, vf: list[str],
             af: list[str], normalize: tuple | None, enc: dict,
             keep_audio: bool) -> None:
    """单次切片编码。-ss 放 -i 前（input seek，源时间语义，视频/音频流统一生效）；
    -t 放 -i 后限输出时长。倍速链（setpts/atempo）压缩的是滤镜后时间轴，
    output seek 的 -ss 会被静默放大 speed 倍——所以起点一律走 input seek。"""
    cmd = ["ffmpeg", "-y", "-ss", str(start), "-i", str(src), "-t", str(length)]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    if af:
        cmd += ["-af", ",".join(af)]
    cmd += encode_args(enc)
    if normalize:
        cmd += ["-r", str(normalize[2])]
    if keep_audio:
        cmd += audio_codec_args(dst)
    else:
        cmd += ["-an"]
    cmd.append(str(dst))
    run(maybe_nice(cmd, enc))


def params_fingerprint(work_dir: Path, params: dict) -> bool:
    """参数指纹比对：一致返回 True（checkpoint 可用）；不一致清场返回 False。

    调窗/调起点/调归一参数是这两个模式的日常迭代方式，光靠产物存在性做
    checkpoint 会静默复用陈旧内容（改起点时长不变，连时长告警都没有）。
    """
    fp_file = work_dir / "params.json"
    current = json.dumps(params, sort_keys=True)
    if fp_file.is_file() and fp_file.read_text(encoding="utf-8") == current:
        return True
    for stale in work_dir.glob("*"):
        if stale.is_file():
            stale.unlink(missing_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    fp_file.write_text(current, encoding="utf-8")
    return False


def mode_windows(src: Path, dst: Path, windows: list[tuple[float, float]], args,
                 normalize, vf: list[str], af: list[str], enc: dict) -> float:
    """一镜多窗：逐窗切段（分段产物即 checkpoint，带参数指纹）→ concat demuxer copy。"""
    parts_dir = dst.parent / f"{dst.stem}.parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    fresh = not params_fingerprint(parts_dir, {
        "windows": args.windows, "speed": args.speed,
        "normalize": args.normalize, "grade": args.grade, "low_load": args.low_load})
    if fresh:
        print("[fingerprint] 参数变化，分段重切")
    part_files: list[Path] = []
    expected = 0.0
    for i, (start, length) in enumerate(windows):
        part = parts_dir / f"part{i:02d}.mp4"
        out_len = length / args.speed
        expected += out_len
        if part.is_file() and part.stat().st_size > 0:
            print(f"[checkpoint] 窗 {i} 已存在：{part}")
        else:
            print(f"[window {i}] start={start}s length={length}s")
            cut_once(src, part, start, out_len, vf, af, normalize, enc, keep_audio=True)
        part_files.append(part)
    list_file = parts_dir / "concat.txt"
    list_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in part_files) + "\n", encoding="utf-8")
    run(maybe_nice(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(list_file), "-c", "copy", str(dst)], enc))
    return expected


def mode_zoompan(src: Path, dst: Path, args, normalize, enc: dict,
                 is_image: bool) -> float:
    """定帧缓推：视频源先取帧（图片源直接用），再 zoompan 匀速推近。"""
    duration = args.duration
    if duration is None or duration <= 0:
        die("--zoompan 必须搭配 --duration（输出时长，秒）")
    if normalize:
        w, h, fps = normalize
    else:
        size = probe_size(src)
        if not size:
            die(f"无法探测输入尺寸: {src}（或显式传 --normalize WxH@FPS）")
        w, h = size[0] // 2 * 2, size[1] // 2 * 2
        fps = 25.0
    nfr = max(2, int(round(duration * fps)))

    work_dir = dst.parent / f"{dst.stem}.zoompan"
    work_dir.mkdir(parents=True, exist_ok=True)
    fresh = not params_fingerprint(work_dir, {
        "start": args.start, "zoompan": args.zoompan,
        "normalize": args.normalize, "grade": args.grade})
    if fresh:
        print("[fingerprint] 参数变化，重新取帧")
    still = work_dir / "still.png"
    if not still.is_file():
        if is_image:
            # 图片先归一到目标画幅（保比 + pad），zoompan 不做拉伸
            vf = build_vf(normalize, args.grade, with_audio_pts=False)
            cmd = ["ffmpeg", "-y", "-i", str(src)]
            if vf:
                cmd += ["-vf", ",".join(vf)]
            cmd += ["-frames:v", "1", str(still)]
            run(maybe_nice(cmd, enc))
        else:
            vf = build_vf(normalize, args.grade, with_audio_pts=False)
            cmd = ["ffmpeg", "-y", "-ss", str(args.start), "-i", str(src), "-frames:v", "1"]
            if vf:
                cmd += ["-vf", ",".join(vf)]
            cmd += ["-q:v", "2", str(still)]
            run(maybe_nice(cmd, enc))
        print(f"[still] 取帧落盘：{still}")
    else:
        print(f"[checkpoint] 定帧已存在：{still}")

    dz = args.zoompan - 1.0
    zp = (f"zoompan=z='1+({dz:.4f}*on/{nfr})':d={nfr}"
          f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
          f":s={w}x{h}:fps={fps}")
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(still), "-t", f"{duration:.3f}",
           "-vf", f"{zp},format=yuv420p", "-an"]
    cmd += encode_args(enc)
    cmd.append(str(dst))
    run(maybe_nice(cmd, enc))
    return duration


def mode_static(src: Path, dst: Path, args, normalize, vf: list[str], enc: dict) -> float:
    """图片输入 + --duration：静图定格成视频段（无缓推）。"""
    duration = args.duration
    if duration is None or duration <= 0:
        die("图片输入必须给 --duration（或 --zoompan 搭配 --duration 做缓推）")
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(src), "-t", f"{duration:.3f}"]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    cmd += encode_args(enc)
    if normalize:
        cmd += ["-r", str(normalize[2])]
    cmd += ["-an", str(dst)]
    run(maybe_nice(cmd, enc))
    return duration


def main() -> None:
    parser = argparse.ArgumentParser(description="clip-trim 精确切素材")
    parser.add_argument("--input", required=True, help="输入素材路径（视频、音频或图片）")
    parser.add_argument("--output", required=True, help="输出路径")
    parser.add_argument("--start", type=float, default=0.0, help="入点（秒，默认 0）")
    parser.add_argument("--end", type=float, default=None, help="出点（秒，默认=输入全长）")
    parser.add_argument("--speed", type=float, default=1.0, help="倍速（默认 1.0）")
    parser.add_argument("--sync-audio", action="store_true", help="视频倍速时同步音频倍速")
    parser.add_argument("--pre-buffer", type=float, default=0.0,
                        help="切段前置缓冲（秒，默认 0）：实际入点提前该值，避免 -ss 切 MP3 吞首字；逻辑入点仍是原 start")
    parser.add_argument("--duration", type=float, default=None,
                        help="输出时长（秒）：图片输入与 --zoompan 配视频源时必填")
    parser.add_argument("--normalize", default=None,
                        help="归一化目标 WxH@FPS（如 1920x1080@25）：scale+pad+sar+fps 一步")
    parser.add_argument("--grade", default="neutral", choices=["neutral", "warm"],
                        help="预设调色（warm=暖调+暗角；默认 neutral 不调）")
    parser.add_argument("--windows", default=None,
                        help='一镜多窗 "start:length,start:length"（切多段按序 concat copy）')
    parser.add_argument("--zoompan", type=float, default=None,
                        help="定帧缓推结束倍率（如 1.08）；视频源在 --start 取帧，图片源直接推")
    parser.add_argument("--low-load", action="store_true",
                        help="低载编码：nice 19 + veryfast + crf 18 + threads 2")
    parser.add_argument("--force", action="store_true",
                        help="清多窗/zoompan 工作目录强制重切重取帧（源文件换内容但参数未变时用；参数变了有指纹自动重切）")
    args = parser.parse_args()

    src = Path(args.input).resolve()
    dst = Path(args.output).resolve()
    if not src.is_file():
        die(f"输入不存在: {src}")
    if args.speed <= 0:
        die(f"倍速必须 > 0，收到 {args.speed}")
    if args.pre_buffer < 0:
        die(f"--pre-buffer 必须 >= 0，收到 {args.pre_buffer}")
    if args.zoompan is not None and args.zoompan <= 1.0:
        die(f"--zoompan 结束倍率必须 > 1.0（推近），收到 {args.zoompan}")
    if args.windows and args.zoompan is not None:
        die("--windows 与 --zoompan 不能同时用（多窗是实拍切片，缓推是定帧动画）")

    normalize = parse_normalize(args.normalize) if args.normalize else None
    # 图片按扩展名判定（ffprobe 对单张图片也报 video 流，不能用 is_video 区分）
    is_image = src.suffix.lower() in IMAGE_EXTS
    has_video = is_image or is_video(src)
    if (args.windows or args.zoompan is not None or normalize) and not has_video:
        die(f"--windows/--zoompan/--normalize 只支持视频或图片输入: {src}")

    enc = dict(LOW_LOAD) if args.low_load else dict(NORMAL_ENCODE)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if args.force:
        for suffix in (".parts", ".zoompan"):
            work = dst.parent / f"{dst.stem}{suffix}"
            if work.is_dir():
                shutil.rmtree(work, ignore_errors=True)
                print(f"[force] 已清工作目录：{work}")

    # ===== 三个特化模式 =====
    if args.windows:
        if is_image or not has_video:
            die(f"--windows 只支持视频输入: {src}")
        windows = parse_windows(args.windows)
        vf = build_vf(normalize, args.grade, speed=args.speed)
        af = [atempo_chain(args.speed)] if (args.sync_audio and args.speed != 1.0) else []
        expected = mode_windows(src, dst, windows, args, normalize, vf, af, enc)
    elif args.zoompan is not None:
        expected = mode_zoompan(src, dst, args, normalize, enc, is_image)
    elif is_image:
        vf = build_vf(normalize, args.grade, with_audio_pts=False)
        expected = mode_static(src, dst, args, normalize, vf, enc)
    else:
        # ===== 经典单窗切片（视频/音频）=====
        src_dur = probe_duration(src)
        end = args.end if args.end is not None else src_dur
        if end <= args.start:
            die(f"出点({end})必须大于入点({args.start})")
        # pre-buffer：实际入点提前 N 秒（不越过 0），保留段头音频避免吞首字
        real_start = max(0.0, args.start - args.pre_buffer)
        trim_dur = end - real_start
        out_dur = trim_dur / args.speed
        if args.duration is not None:
            out_dur = args.duration  # 显式时长优先（-t 卡输出）

        # -ss 走 input seek（源时间语义）：倍速链压缩滤镜后时间轴，output seek 会错位
        cmd = ["ffmpeg", "-y", "-ss", str(real_start), "-i", str(src), "-t", str(out_dur)]
        vf = []
        af = []
        if has_video:
            vf = build_vf(normalize, args.grade, speed=args.speed)
            if args.speed != 1.0 and args.sync_audio:
                af.append(atempo_chain(args.speed))
        if vf:
            cmd.extend(["-vf", ",".join(vf)])
        if af:
            cmd.extend(["-af", ",".join(af)])
        if has_video and not is_image:
            cmd.extend(encode_args(enc))
            if normalize:
                cmd.extend(["-r", str(normalize[2])])
        cmd.extend(audio_codec_args(dst))
        cmd.append(str(dst))
        run(maybe_nice(cmd, enc))
        expected = out_dur

    actual_dur = probe_duration(dst)
    print(f"[done] {src.name} → {dst.name}")
    print(f"  - 期望时长 {expected:.3f}s，实际 {actual_dur:.3f}s")
    if abs(actual_dur - expected) > DUR_TOLERANCE:
        print(f"[warn] 时长偏差 {actual_dur - expected:+.3f}s 超过容差 {DUR_TOLERANCE}s，检查源与参数",
              file=sys.stderr)
    if args.normalize:
        w, h, fps = normalize
        print(f"  - 归一化：{w}x{h}@{fps}fps")
    if args.grade != "neutral":
        print(f"  - 调色预设：{args.grade}")
    if args.windows:
        print(f"  - 多窗：{args.windows}")
    if args.zoompan is not None:
        print(f"  - 定帧缓推：zoom 1.0 → {args.zoompan}")
    if args.low_load:
        print(f"  - 低载编码：nice {LOW_LOAD['nice']} / {LOW_LOAD['preset']} / crf {LOW_LOAD['crf']} / threads {LOW_LOAD['threads']}")


if __name__ == "__main__":
    main()
