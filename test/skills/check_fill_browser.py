"""Local-browser regression: python3 test/skills/check_fill_browser.py (no account required)."""
import importlib.util
import json
import subprocess
import uuid
from pathlib import Path
from urllib.parse import quote

path = Path(__file__).resolve().parents[2] / 'crews/main/skills/expert-douyin/tools/douyin-note-publish/scripts/publish_douyin_note.py'
spec = importlib.util.spec_from_file_location('note', path)
note = importlib.util.module_from_spec(spec)
spec.loader.exec_module(note)

class LocalBrowser(note.Browser):
    def command(self, *args, timeout=60):
        p = subprocess.run(['camoufox-cli', '--session', session, '--json', *args],
                           capture_output=True, text=True, timeout=timeout)
        if p.returncode:
            raise RuntimeError(p.stderr or p.stdout)
        result = json.loads(p.stdout)
        if result.get('ok') is False:
            raise RuntimeError(str(result))
        data = result.get('data')
        return data['result'] if isinstance(data, dict) and 'result' in data else data

session = 'note-regression-' + uuid.uuid4().hex[:10]
b = LocalBrowser()
html = '''<input placeholder="添加作品标题"><input placeholder="搜索作品"><div contenteditable="true"></div>
<script>
window.events=[]; window.state={};
for(const e of document.querySelectorAll('input')) {
  let tracked='';
  Object.defineProperty(e,'value',{get(){return Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').get.call(this)},set(v){tracked=v;Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(this,v)}});
  for(const type of ['input','change']) e.addEventListener(type,()=>{
    events.push(type); document.body.dataset.events=JSON.stringify(events); if(e.value!==tracked) {state[e.placeholder]=e.value; tracked=e.value; e.dataset.state=e.value;}
  });
  e.addEventListener('keydown',event=>{if(event.key==='Enter') document.body.dataset.searched=state[e.placeholder]});
}
</script>'''
try:
    b.command('open', 'data:text/html;charset=utf-8,' + quote(html))
    title = '中文"反斜杠\\与emoji😀'
    note.fill(b, title, '第一行\n第二行 #话题', 'none')
    observed = b.eval('document.querySelector("input").dataset.state')
    assert observed == title, repr(observed)
    note.fill_input(b, 'input[placeholder*="搜索作品"]', title)
    b.command('press', 'Enter')
    assert b.eval('document.body.dataset.searched') == title
    assert b.eval('JSON.parse(document.body.dataset.events)') == ['input', 'change', 'input', 'change']
    note.fill_input(b, 'input[placeholder*="搜索作品"]', '')
    assert b.eval('document.querySelectorAll("input")[1].dataset.state') == ''
    for setup in [
        'document.querySelector("input").disabled=true',
        'document.querySelector("input").disabled=false; document.querySelector("input").readOnly=true',
        'document.querySelector("input").readOnly=false; document.body.append(document.querySelector("input").cloneNode())',
    ]:
        b.eval(setup)
        try:
            note.fill_input(b, 'input[placeholder="添加作品标题"]', '不应写入')
        except RuntimeError:
            pass
        else:
            raise AssertionError('non-editable or ambiguous input accepted')
    print('PASS: real camoufox CLI: title/caption, controlled input events, search Enter, escaping, clear, disabled/read-only/ambiguous guards')
finally:
    b.close()
