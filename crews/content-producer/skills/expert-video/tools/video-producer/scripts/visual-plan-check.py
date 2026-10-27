#!/usr/bin/env python3
"""Validate project visual requirements and record actual human preview review."""
import argparse
import json
from pathlib import Path
import sys

from _visual_plan import check, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project_dir', type=Path)
    parser.add_argument('--preview', action='append', type=Path, default=[])
    parser.add_argument('--verdict', choices=['pass', 'fail'])
    parser.add_argument('--reviewer')
    parser.add_argument('--notes')
    args = parser.parse_args()
    project = args.project_dir.resolve()
    result = check(project)
    if args.verdict:
        if not args.preview or not args.reviewer or not args.notes or result['verdict'] != 'pass':
            parser.error('登记预览须配置视觉承诺、通过统计，并提供 preview/reviewer/notes')
        artifacts = []
        for path in args.preview:
            path = (project/path).resolve()
            artifacts.append({'path': str(path), 'sha256': sha(path)})
        review = project/'review/visual-preview.json'
        review.parent.mkdir(parents=True, exist_ok=True)
        review.write_text(json.dumps({**result, 'verdict': args.verdict, 'reviewer': args.reviewer,
                                      'notes': args.notes, 'artifacts': artifacts}, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as exc:
        print(f'[error] {exc}', file=sys.stderr)
        raise SystemExit(1)
