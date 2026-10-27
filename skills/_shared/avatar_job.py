"""Read-only validation of avatar provenance and separate delivery gates."""
import json
import math
from pathlib import Path

from bailian_media import fingerprint, media_info


def load_avatar_job(path, *, require_review=True):
    job = json.loads(Path(path).read_text())
    if job.get('status') != 'SUCCEEDED' or job.get('timing_pass') is not True:
        raise ValueError('数字人任务未完成或时长核验未通过')
    durations = {}
    for kind in ('audio', 'video'):
        file = Path(job[f'{kind}_file'])
        if not file.is_file() or fingerprint(file) != job.get(f'{kind}_sha256'):
            raise ValueError(f'数字人 {kind} 文件缺失或 SHA-256 不匹配，勿手改 job')
        seconds, streams = media_info(file)
        durations[kind] = seconds
        if not any(s['codec_type'] == kind for s in streams):
            raise ValueError(f'数字人 {kind} 文件缺少对应媒体轨')
        expected = float(job.get(f'{kind}_duration', seconds))
        if not math.isfinite(expected) or abs(seconds - expected) > .12:
            raise ValueError(f'数字人 {kind} 时长与 job 不符')
    if abs(durations['audio'] - durations['video']) > .12:
        raise ValueError('数字人音视频实际时长偏差超过0.12秒')
    if job.get('schema_version', 1) >= 2:
        if job.get('api_succeeded') is not True:
            raise ValueError('数字人 API 成功状态未确认')
        if require_review:
            review = job.get('lip_sync_review') or {}
            if (job.get('lip_sync_review_pass') is not True
                    or review.get('video_sha256') != job['video_sha256']
                    or review.get('audio_sha256') != job['audio_sha256']):
                raise ValueError('数字人尚未通过当前音视频的人工口型审查；使用 avatar review 记录实际审片结果')
    return job
