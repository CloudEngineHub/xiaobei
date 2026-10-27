"""Check explicit per-project visual promises and bind preview review to current files."""
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def visual_timeline(spec):
    """Normalize scenes and optional nested beats without a second timeline."""
    sources = [key for key in ('scenes', 'segments', 'slides', 'pages') if key in spec]
    if len(sources) != 1:
        raise ValueError('计划须使用唯一时间轴 scenes（或单一旧 segments/slides/pages）；禁止并列双写')
    items = spec[sources[0]]
    if not isinstance(items, list) or not items:
        raise ValueError('视觉计划时间轴必须为非空数组')
    timeline, mappings, elapsed, ids = [], [], 0.0, set()

    def number(value, label):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f'{label} 须为非负有限数')
        return float(value)

    def interval(item, start, duration, label):
        for key, expected in (('start', start), ('end', start + duration)):
            if key in item and abs(number(item[key], f'{label}.{key}') - expected) > .001:
                raise ValueError(f'{label}.{key} 与连续时长不一致，存在空隙/重复计时')

    def cues(items, duration, label):
        if not isinstance(items, list):
            raise ValueError(f'{label}.cues 须为数组')
        end = 0.0
        for cue in items:
            if not isinstance(cue, dict):
                raise ValueError(f'{label}.cue 须为对象')
            start = number(cue.get('start'), f'{label}.cue.start')
            stop = number(cue.get('end'), f'{label}.cue.end')
            if start < end - .001 or stop <= start or stop > duration + .001:
                raise ValueError(f'{label} 字幕 cue 重叠或超出所属时间范围')
            end = stop

    for i, scene in enumerate(items):
        if not isinstance(scene, dict):
            raise ValueError('scene/segment 须为对象')
        duration = number(scene.get('duration'), 'scene.duration')
        if duration <= 0:
            raise ValueError('scene.duration 须大于0')
        sid = scene.get('id', f'scene-{i+1:02d}')
        if not isinstance(sid, str) or not sid or sid in ids:
            raise ValueError('scene.id 必须唯一且非空')
        ids.add(sid)
        interval(scene, elapsed, duration, sid)
        cues(scene.get('cues', []), duration, sid)
        beats = scene.get('beats')
        if beats is not None and (not isinstance(beats, list) or not beats):
            raise ValueError(f'{sid}.beats 须为非空数组')
        offset = 0.0
        for j, beat in enumerate(beats if beats is not None else [scene]):
            if not isinstance(beat, dict):
                raise ValueError('beat 须为对象')
            length = number(beat.get('duration'), 'beat.duration')
            if length <= 0:
                raise ValueError('beat.duration 须大于0')
            if beats is not None:
                interval(beat, offset, length, f'{sid}.beat-{j+1}')
                cues(beat.get('cues', []), length, f'{sid}.beat-{j+1}')
            bid = f'{sid}/beat-{j+1:02d}'
            timeline.append({**scene, **beat, 'duration': length, 'start': elapsed+offset,
                             'end': elapsed+offset+length, 'scene_id': sid, 'beat_id': bid})
            mappings.append({'scene_id': sid, 'beat_id': bid, 'start': elapsed+offset,
                             'end': elapsed+offset+length})
            offset += length
        if abs(offset-duration) > .001:
            raise ValueError(f'{sid} 的 beat 时长之和须等于 scene.duration；字幕不另计时')
        elapsed += duration
    if 'duration' in spec and abs(number(spec['duration'], 'spec.duration')-elapsed) > .001:
        raise ValueError('计划总时长与 scenes/segments 时长之和不一致')
    return timeline, mappings, elapsed


def check(project, *, require_preview=False):
    spec_path = project/'script/deck-spec.json'
    promise_path = project/'slots/delivery-promise.json'
    promise = json.loads(promise_path.read_text())
    requirements = promise.get('visual_requirements') or (promise.get('promises') or {}).get('visual_requirements')
    if not requirements:
        return {'verdict': 'not-configured', 'instruction': '按既有 GATE B 人工审片，不默认加入数值阈值'}
    spec = json.loads(spec_path.read_text())
    segments, mappings, duration = visual_timeline(spec)
    text_seconds, diagrams, problems = 0, 0, []
    allowed = {'text', 'diagram', 'screencast', 'footage', 'illustration'}
    for i, segment in enumerate(segments):
        kind, action = segment.get('visual_kind'), segment.get('visual_action')
        duration = float(segment.get('duration', 0))
        if kind not in allowed or not math.isfinite(duration) or duration <= 0:
            problems.append(f'第{i+1}段缺少有效 visual_kind 或 duration')
        if kind == 'text':
            text_seconds += duration
        elif not isinstance(action, str) or not action.strip():
            problems.append(f'第{i+1}段须描述画面中实际会动什么')
        if kind == 'diagram' and isinstance(action, str) and action.strip():
            diagrams += 1
    for field in ('max_text_seconds', 'min_dynamic_diagrams'):
        if field in requirements and (isinstance(requirements[field], bool)
                or not isinstance(requirements[field], (int, float))
                or not math.isfinite(requirements[field]) or requirements[field] < 0):
            raise ValueError(f'{field} 须为非负有限数')
    if text_seconds > requirements.get('max_text_seconds', math.inf):
        problems.append('纯文字累计时长超过 Brief/承诺上限')
    if diagrams < requirements.get('min_dynamic_diagrams', 0):
        problems.append('动态结构图数量未达到 Brief/承诺下限')
    result = {'verdict': 'fail' if problems else 'pass', 'problems': problems,
              'text_seconds': text_seconds, 'dynamic_diagrams': diagrams,
              'scene_beat_mapping': mappings, 'duration': duration,
              'spec_sha256': sha(spec_path), 'promise_sha256': sha(promise_path),
              'basis': '声明的分镜类型与动作；实际语义与观感须人工预览核验'}
    if problems:
        raise ValueError('；'.join(problems))
    if require_preview:
        preview = json.loads((project/'review/visual-preview.json').read_text())
        if any(preview.get(key) != result[key] for key in ('spec_sha256', 'promise_sha256')) or preview.get('verdict') != 'pass':
            raise ValueError('当前分镜/承诺尚未通过视觉预览')
        artifacts = preview.get('artifacts') or []
        if not artifacts or any(not Path(p['path']).is_file() or sha(p['path']) != p['sha256'] for p in artifacts):
            raise ValueError('预览产物缺失或已改变，需重新审片')
    return result
