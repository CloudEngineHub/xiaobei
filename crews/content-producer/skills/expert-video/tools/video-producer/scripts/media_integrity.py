"""Read-only packet and stream checks shared by muxing and locked-audio review."""
import hashlib
import json
from pathlib import Path
import subprocess


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def probe_json(path, *options):
    proc = subprocess.run(['ffprobe', '-v', 'error', *options, '-of', 'json', str(path)],
                          capture_output=True, text=True, timeout=300)
    if proc.returncode:
        raise ValueError(proc.stderr[-2000:])
    return json.loads(proc.stdout)


def packet_signature(path, kind):
    packets = probe_json(path, '-select_streams', kind+':0', '-show_packets',
                         '-show_data_hash', 'sha256', '-show_entries',
                         'packet=pts,dts,duration,size,data_hash').get('packets', [])
    if not packets or any(not p.get('data_hash') for p in packets):
        raise ValueError(f'无法校验 {kind} 逐包哈希: {path}')
    return packets


def verify_track_copy(source, output, kind):
    def track(path):
        streams = probe_json(path, '-select_streams', kind+':0', '-show_streams').get('streams', [])
        if not streams:
            raise ValueError(f'缺少 {kind} 流: {path}')
        return streams[0]
    src, dst = track(source), track(output)
    if any(src.get(k) != dst.get(k) for k in ('codec_name', 'time_base', 'start_pts', 'duration_ts')):
        raise ValueError(f'{kind} 编码/时间基/起点/时长未保持一致')
    expected, actual = packet_signature(source, kind), packet_signature(output, kind)
    if actual != expected:
        raise ValueError(f'{kind} 逐包载荷 SHA256/PTS/DTS/duration/size 不一致')
    return {'packets': len(actual), 'packet_sha256_and_timestamps_match': True,
            'duration': dst.get('duration'), 'frames': dst.get('nb_frames')}
