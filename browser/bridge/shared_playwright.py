"""Read the instance runtime or render through its single Node Playwright driver."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

BROWSER = Path(__file__).resolve().parents[1]


def _run(script, body=None):
    root = BROWSER.parent
    portable = root / ('tools/node/node.exe' if os.name == 'nt' else 'tools/node/bin/node')
    node = os.environ.get('XIAOBEI_BROWSER_NODE') or (str(portable) if portable.is_file() else shutil.which('node'))
    if not node:
        raise RuntimeError('缺少 Node；请修复 xiaobei 统一安装')
    result = subprocess.run([node, str(BROWSER / 'scripts' / script)],
                            input=json.dumps(body, ensure_ascii=False) if body is not None else None,
                            capture_output=True, text=True, encoding='utf-8', timeout=180)
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[-4000:])
    return json.loads(result.stdout)


def runtime_info():
    return _run('shared-playwright.mjs')


def render_slides(html, width, height, scale):
    with tempfile.TemporaryDirectory(prefix='xiaobei-slides-') as directory:
        result = _run('render-local.mjs', dict(action='slides', html=str(html), width=width,
                                             height=height, scale=scale, output=directory))
        return [Path(file).read_bytes() for file in result['files']]


def render_card(html, output=None):
    return _run('render-local.mjs', dict(action='card', html=str(html), width=1080,
                                        height=1440, scale=2, output=str(output) if output else None))['check']
