#!/usr/bin/env python3
"""Run one production stage and persist artifacts plus a single recovery entry."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys


def sanitise(text):
    text = re.sub(r'(https?://[^\s?]+)\?[^\s]+', r'\1?[redacted]', text)
    text = re.sub(r'(?i)Bearer\s+\S+|\bsk-[A-Za-z0-9_-]+', '[redacted]', text)
    text = re.sub(r'(?i)((?:key|token|secret|password)\s*[=:]\s*)\S+', r'\1[redacted]', text)
    return text[-2000:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project_dir', type=Path)
    parser.add_argument('--stage', required=True)
    parser.add_argument('--artifact', action='append', type=Path, default=[])
    # Split explicitly: argparse.REMAINDER would consume stage options after project_dir.
    argv = sys.argv[1:]
    if '--' not in argv:
        parser.error('用 -- 分隔阶段参数与实际 wrapper 命令')
    split = argv.index('--')
    args = parser.parse_args(argv[:split])
    command = argv[split+1:]
    if not command or Path(command[0]).name not in {'video-producer', 'video-producer.sh', 'avatar', 'avatar.sh', 'deck-render', 'deck-render.sh'}:
        parser.error('阶段命令须为 video-producer / avatar / deck-render wrapper')
    if any(re.search(r'(?i)(?:api[-_]?key|password|secret|xsec_token|Bearer|sk-[A-Za-z0-9])', value) for value in command):
        parser.error('凭据只走环境变量或工具会话，不写入阶段命令')
    project = args.project_dir.resolve()
    if not project.is_dir():
        parser.error('project_dir 必须已存在')
    state_dir = project/'.pipeline'
    state_dir.mkdir(exist_ok=True)
    checkpoint = state_dir/'checkpoint.json'
    state = json.loads(checkpoint.read_text()) if checkpoint.exists() else {'completed': [], 'artifacts': []}
    state.update(stage=args.stage, status='running', command=command,
                 updated_at=datetime.now(timezone.utc).isoformat())

    def save():
        temp = checkpoint.with_suffix('.tmp')
        temp.write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n')
        temp.replace(checkpoint)

    save()
    try:
        result = subprocess.run(command, cwd=project, stderr=subprocess.PIPE, text=True)
        code, error = result.returncode, sanitise(result.stderr)
    except OSError as exc:
        code, error = 1, sanitise(str(exc))
    if error:
        print(error, file=sys.stderr)
    artifacts = {item['path']: item for item in state.get('artifacts', [])}
    for path in args.artifact:
        path = (project/path).resolve()
        if path.is_file():
            artifacts[str(path)] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    recovery = command
    if Path(command[0]).stem == 'avatar' and len(command) > 1 and command[1] == 'generate' and '--output' in command:
        job = Path(command[command.index('--output')+1])
        job = (project/job).resolve().with_suffix('.avatar.json')
        if job.exists():
            recovery = [command[0], 'resume', '--job', str(job)]
            artifacts[str(job)] = {'path': str(job), 'sha256': hashlib.sha256(job.read_bytes()).hexdigest()}
    if code == 0:
        state['completed'].append(args.stage)
    state.update(status='complete' if code == 0 else 'failed', error_summary=error or f'exit={code}',
                 artifacts=list(artifacts.values()), recovery_command=shlex.join(recovery),
                 last_successful_stage=state['completed'][-1] if state['completed'] else None,
                 updated_at=datetime.now(timezone.utc).isoformat())
    save()
    if code:
        (state_dir/'failure.md').write_text(
            f"当前阶段：{args.stage}\n\n最后成功阶段：{state['last_successful_stage']}\n\n错误摘要：{state['error_summary']}\n\n"
            + '已完成产物：\n'+''.join(f"- {p['path']}\n" for p in state['artifacts'])
            + f"\n恢复入口：\n\n```bash\n{state['recovery_command']}\n```\n")
    else:
        (state_dir/'failure.md').unlink(missing_ok=True)
    print(json.dumps({'checkpoint': str(checkpoint), 'status': state['status'], 'recovery_command': state['recovery_command']}, ensure_ascii=False))
    raise SystemExit(code)


if __name__ == '__main__':
    main()
