#!/usr/bin/env python3
"""Wan S2V: original audio, bounded drive tail, resumable tasks and reviewed jobs."""
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
import wave

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[7] / 'skills/_shared'))
from avatar_job import load_avatar_job
from bailian_media import APIError, download, fingerprint, media_info, request, save_json, upload, workspace

MODEL = 'wan2.2-s2v'
DETECT_MODEL = 'wan2.2-s2v-detect'
RATE = 24000


def run(command):
    result = subprocess.run(list(map(str, command)), capture_output=True, timeout=1200)
    if result.returncode:
        raise ValueError(result.stderr.decode(errors='replace')[-2000:])
    return result.stdout


def decode_audio(path):
    return run(['ffmpeg', '-v', 'error', '-nostdin', '-i', path, '-map', '0:a:0',
                '-ac', '1', '-ar', RATE, '-f', 's16le', '-'])


def video_info(path):
    _, streams = media_info(path)
    video = next((s for s in streams if s['codec_type'] == 'video'), None)
    if not video:
        raise ValueError('数字人文件没有视频轨')
    duration = float(video.get('duration', 0))
    fps = float(Fraction(video['r_frame_rate']))
    if not math.isfinite(duration) or duration <= 0 or not 1 <= fps <= 120:
        raise ValueError('数字人视频轨时长或帧率无效')
    return duration, fps


def local_source(value, folder, kind):
    if value.startswith(('http://', 'https://')):
        suffix = Path(urlsplit(value).path).suffix.lower() or ('.png' if kind == 'image' else '.wav')
        return download(value, folder / (kind + suffix), max_bytes=15*1024*1024)
    path = Path(value).resolve()
    if not path.is_file():
        raise ValueError(f'{kind} 文件不存在')
    return path


def validate_image(image):
    with Image.open(image) as pic:
        if pic.format not in ('JPEG', 'PNG', 'BMP', 'WEBP') or not all(400 <= n <= 7000 for n in pic.size):
            raise ValueError('Wan S2V 图片须为 JPEG/PNG/BMP/WebP，宽高均为400–7000像素')
        pic.verify()


def prepare_audio(source, folder, start=0, duration=None, tail=.75):
    if source.suffix.lower() not in ('.wav', '.mp3'):
        raise ValueError('音频须为 WAV/MP3')
    if not all(math.isfinite(x) for x in (start, tail)) or start < 0 or not 0 <= tail <= 2:
        raise ValueError('start 须非负，tail 范围0–2秒，均须为有限数')
    pcm = decode_audio(source)
    begin = round(start * RATE)
    count = len(pcm)//2 - begin if duration is None else round(duration * RATE) if math.isfinite(duration) else 0
    if count <= 0 or begin + count > len(pcm)//2:
        raise ValueError('音频时间窗超出完整解码 PCM 范围')
    speech = pcm[begin*2:(begin+count)*2]
    drive = speech + bytes(round(tail*RATE)*2)
    if len(drive)/(2*RATE) >= 20:
        raise ValueError('Wan 驱动音频含尾部静音必须严格小于20秒；请按句边界分段')
    for name, data in [('speech.wav', speech), ('drive.wav', drive)]:
        path = folder / name
        if path.exists():
            with wave.open(str(path), 'rb') as existing:
                if (existing.getnchannels(), existing.getsampwidth(), existing.getframerate()) != (1, 2, RATE) or existing.readframes(existing.getnframes()) != data:
                    raise ValueError('派生输入与本次原声/时间窗不一致；请用新输出名')
        else:
            with wave.open(str(path), 'wb') as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(RATE)
                output.writeframes(data)
        if path.stat().st_size >= 15*1024*1024:
            raise ValueError('驱动 WAV 须小于15MB')
    return {'source_audio_file': str(source), 'source_audio_sha256': fingerprint(source),
            'source_start': begin/RATE, 'audio_file': str(folder/'speech.wav'),
            'audio_sha256': fingerprint(folder/'speech.wav'), 'audio_duration': count/RATE,
            'speech_pcm_sha256': hashlib.sha256(speech).hexdigest(),
            'drive_file': str(folder/'drive.wav'), 'drive_sha256': fingerprint(folder/'drive.wav'),
            'drive_duration': len(drive)/(2*RATE), 'tail_seconds': tail}


def complete_local(job_path, job):
    raw = Path(job['raw_video_file'])
    if fingerprint(raw) != job.get('raw_video_sha256'):
        raise ValueError('原始模型视频已改变')
    seconds, fps = video_info(raw)
    target = job['audio_duration']
    job['raw_video_duration'] = seconds
    save_json(job_path, job)
    if seconds < target:
        raise ValueError('模型视频未覆盖完整原声；保留原任务，不定帧、不循环、不自动重提')
    output = Path(job['video_file'])
    if output.exists():
        raise ValueError('未核验的输出已存在；另行检查，不覆盖')
    # Keep natural frames covering the full speech window; trim only excess drive tail.
    with tempfile.TemporaryDirectory(prefix='.avatar-trim-', dir=output.parent) as folder:
        temp = Path(folder)/'video.mp4'
        run(['ffmpeg', '-v', 'error', '-nostdin', '-i', raw, '-map', '0:v:0', '-an',
             '-t', str(math.ceil(target*fps-1e-8)/fps), '-c:v', 'libx264', '-crf', '18',
             '-threads', '2', '-pix_fmt', 'yuv420p', '-fps_mode', 'passthrough', temp])
        actual, _ = video_info(temp)
        if actual < target-.001 or actual-target > .12:
            raise ValueError('裁剪视频未通过0.12秒时间窗验收')
        job.update(video_sha256=fingerprint(temp), video_duration=actual,
                   duration_delta=actual-target, timing_pass=True,
                   lip_sync_review_pass=None)
        save_json(job_path, job)
        temp.replace(output)
        save_json(job_path, job)


def finish(job_path, *, timeout=900, interval=15):
    job_path = Path(job_path).resolve()
    job = json.loads(job_path.read_text())
    if job.get('schema_version', 1) < 2:
        legacy = Path(__file__).resolve().parents[2]/'liveportrait/scripts/liveportrait.py'
        spec = importlib.util.spec_from_file_location('legacy_avatar', legacy)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.finish(job_path, timeout=timeout)
    if job.get('timing_pass') is True and Path(job['video_file']).is_file():
        load_avatar_job(job_path, require_review=False)
        print(json.dumps({'job': str(job_path), 'video': job['video_file'], 'review_required': job.get('lip_sync_review_pass') is not True}))
        return
    base, key = workspace()
    if base != job.get('base_url'):
        raise ValueError('任务不属于当前业务空间')
    for kind in ('audio', 'source_audio', 'drive', 'image'):
        if fingerprint(job[f'{kind}_file']) != job[f'{kind}_sha256']:
            raise ValueError(f'{kind} 输入已改变，不得混用任务')
    if not job.get('task_id'):
        raise ValueError('提交结果不确定：先查控制台，禁止重复生成')
    raw = Path(job['raw_video_file'])
    if raw.exists():
        complete_local(job_path, job)
        return
    deadline = time.monotonic() + timeout
    while True:
        output = request(base, key, '/tasks/'+job['task_id']).get('output') or {}
        job.update(status=output.get('task_status', 'UNKNOWN'),
                   api_succeeded=output.get('task_status') == 'SUCCEEDED')
        save_json(job_path, job)
        print(f'[info] {job["model"]} status={job["status"]}', flush=True)
        if job['api_succeeded']:
            url = (output.get('results') or {}).get('video_url') or output.get('video_url')
            if not url:
                raise ValueError('成功响应缺少video_url')
            download(url, raw, max_bytes=512*1024*1024)
            job['raw_video_sha256'] = fingerprint(raw)
            save_json(job_path, job)
            complete_local(job_path, job)
            print(json.dumps({'job': str(job_path), 'video': job['video_file'], 'review_required': True}))
            return
        if job['status'] not in ('PENDING', 'RUNNING'):
            raise APIError(f'{MODEL} {job["status"]} code={output.get("code", "unknown")}')
        if time.monotonic() >= deadline:
            raise TimeoutError(f'任务仍在运行；avatar resume --job {job_path}')
        time.sleep(min(interval, max(0, deadline-time.monotonic())))


def generate(args):
    target = args.output.resolve()
    job_path = target.with_suffix('.avatar.json')
    if target.suffix.lower() != '.mp4' or target.exists() or job_path.exists():
        raise ValueError('需要新MP4输出；既有任务用 avatar resume，不重复生成')
    base, key = workspace()
    folder = target.parent / ('.'+target.stem+'-avatar-inputs')
    folder.mkdir(parents=True, exist_ok=True)
    image = local_source(args.image, folder, 'image')
    audio = local_source(args.audio, folder, 'audio')
    validate_image(image)
    job = {'schema_version': 2, 'provider': 'bailian-workspace', 'model': MODEL,
           'base_url': base, 'status': 'PREPARED', 'api_succeeded': False,
           'timing_pass': False, 'lip_sync_review_pass': None,
           'image_file': str(image), 'image_sha256': fingerprint(image),
           'video_file': str(target), 'raw_video_file': str(target.with_name(target.stem+'.wan-raw.mp4')),
           'parameters': {'resolution': args.resolution},
           **prepare_audio(audio, folder, args.start, args.duration, args.tail)}
    if Path(job['raw_video_file']).exists():
        raise ValueError('原始视频输出已存在，拒绝覆盖')
    check = request(base, key, '/services/aigc/image2video/face-detect', {
        'model': DETECT_MODEL, 'input': {'image_url': upload(base, key, image, DETECT_MODEL)}})
    if (check.get('output') or {}).get('check_pass') is not True:
        raise ValueError('Wan S2V 人像检测未通过')
    job['detect_request_id'] = check.get('request_id')
    body = {'model': MODEL, 'input': {'image_url': upload(base, key, image, MODEL),
            'audio_url': upload(base, key, Path(job['drive_file']), MODEL)}, 'parameters': job['parameters']}
    job['status'] = 'SUBMITTING'
    save_json(job_path, job)
    result = request(base, key, '/services/aigc/image2video/video-synthesis', body, async_task=True)
    job['task_id'] = (result.get('output') or {}).get('task_id')
    if not job['task_id']:
        raise ValueError('提交未返回task_id；先查控制台，禁止重复提交')
    job['status'] = 'PENDING'
    save_json(job_path, job)
    finish(job_path, timeout=args.timeout)


def review(args):
    job = load_avatar_job(args.job, require_review=False)
    job['lip_sync_review_pass'] = args.verdict == 'pass'
    job['lip_sync_review'] = {'reviewer': args.reviewer, 'notes': args.notes,
                             'at': datetime.now(timezone.utc).isoformat(),
                             'video_sha256': job['video_sha256'], 'audio_sha256': job['audio_sha256']}
    save_json(args.job, job)


def assemble(args):
    manifest = args.manifest.resolve()
    entries = json.loads(manifest.read_text())
    if not isinstance(entries, list) or not entries:
        raise ValueError('manifest 须为非空 job 路径数组，按原声时间窗排序')
    target = args.output.resolve()
    output_job = target.with_suffix('.avatar.json')
    if target.exists() or output_job.exists() or target.suffix.lower() != '.mp4':
        raise ValueError('合并输出须为新MP4')
    source = args.audio.resolve()
    source_hash = fingerprint(source)
    full_pcm = decode_audio(source)
    jobs, cursor = [], 0
    for entry in entries:
        path = (manifest.parent/entry).resolve()
        job = load_avatar_job(path)
        start = round(job.get('source_start', -1)*RATE)
        count = round(job['audio_duration']*RATE)
        if (job.get('schema_version') != 2 or job.get('model') != MODEL
                or job.get('provider') != 'bailian-workspace' or job.get('source_audio_sha256') != source_hash
                or start != cursor or hashlib.sha256(full_pcm[start*2:(start+count)*2]).hexdigest() != job.get('speech_pcm_sha256')):
            raise ValueError('分段任务未按顺序覆盖同一原声，或PCM来源不一致')
        jobs.append((path, job))
        cursor += count
    if cursor*2 != len(full_pcm):
        raise ValueError('分段没有覆盖完整原声')
    seconds = cursor/RATE
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.avatar-assemble-', dir=target.parent) as folder:
        listing, output = Path(folder)/'concat.txt', Path(folder)/'video.mp4'
        lines = []
        for _, job in jobs:
            escaped = job['video_file'].replace("'", "'\\''")
            lines.extend([f"file '{escaped}'", f"duration {job['audio_duration']:.9f}"])
        listing.write_text('\n'.join(lines)+'\n')
        run(['ffmpeg', '-v', 'error', '-nostdin', '-f', 'concat', '-safe', '0', '-i', listing,
             '-an', '-vf', 'fps=30,format=yuv420p', '-t', str(seconds), '-c:v', 'libx264', '-crf', '18', '-threads', '2', output])
        actual, _ = video_info(output)
        if abs(actual-seconds) > .12:
            raise ValueError('合并视频时长不匹配')
        aggregate = {'schema_version': 2, 'provider': 'bailian-workspace', 'model': MODEL,
                     'status': 'SUCCEEDED', 'api_succeeded': True, 'timing_pass': True,
                     'lip_sync_review_pass': None, 'audio_file': str(source), 'audio_sha256': source_hash,
                     'audio_duration': seconds, 'video_file': str(target), 'video_duration': actual,
                     'video_sha256': fingerprint(output), 'segments': [
                         {'job': str(path), 'job_sha256': fingerprint(path)} for path, _ in jobs]}
        output.replace(target)
        save_json(output_job, aggregate)
    print(json.dumps({'video': str(target), 'job': str(output_job), 'review_required': True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    gen = sub.add_parser('generate')
    gen.add_argument('--image', required=True)
    gen.add_argument('--audio', required=True)
    gen.add_argument('--output', required=True, type=Path)
    gen.add_argument('--resolution', choices=['480P', '720P'], default='480P')
    gen.add_argument('--start', type=float, default=0)
    gen.add_argument('--duration', type=float)
    gen.add_argument('--tail', type=float, default=.75)
    gen.add_argument('--timeout', type=int, default=900)
    resume = sub.add_parser('resume')
    resume.add_argument('--job', type=Path, required=True)
    resume.add_argument('--timeout', type=int, default=900)
    rev = sub.add_parser('review')
    rev.add_argument('--job', type=Path, required=True)
    rev.add_argument('--verdict', choices=['pass', 'fail'], required=True)
    rev.add_argument('--reviewer', required=True)
    rev.add_argument('--notes', required=True)
    join = sub.add_parser('assemble')
    join.add_argument('--manifest', type=Path, required=True)
    join.add_argument('--audio', type=Path, required=True)
    join.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= getattr(args, 'timeout', 900) <= 3600:
        parser.error('timeout 范围1–3600秒')
    if args.command == 'resume':
        finish(args.job, timeout=args.timeout)
    else:
        {'generate': generate, 'review': review, 'assemble': assemble}[args.command](args)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, APIError, TimeoutError) as exc:
        print(f'[error] {exc}', file=sys.stderr)
        raise SystemExit(1)
