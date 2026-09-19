#!/usr/bin/env python3
"""Publish image notes through the persistent douyin browser session."""
import argparse
import json
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '_shared'))
from publish_browser import Browser, SESSION, UPLOAD_URL, MANAGE_URL, publish_lock

VISIBLE = 'e.getClientRects().length > 0'

class LoginRequired(RuntimeError):
    pass


def check_login(b):
    url = b.eval('window.location.href') or ''
    if '/login' in url:
        raise LoginRequired('SESSION_EXPIRED: 创作者中心跳转登录页')



def wait_for(action, message, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = action()
        if value:
            return value
        time.sleep(1)
    raise RuntimeError(message)


def click_text(b, text, selector='button,div,span,a,li,label'):
    return b.eval(f'''(() => {{const nodes=[...document.querySelectorAll({json.dumps(selector)})]
      .filter(e=>{VISIBLE} && (e.children.length===0 || e.tagName==='BUTTON') && e.textContent.trim()==={json.dumps(text)});
      if(nodes.length!==1) return false; (nodes[0].closest('button')||nodes[0]).click(); return true;}})()''')


def validate(images=None, title='', caption=''):
    if not title.strip() or len(title) > 20:
        raise ValueError('图文标题必须为 1–20 字')
    if len(caption) > 1000:
        raise ValueError('图文描述不能超过 1000 字')
    if images is not None:
        if not 1 <= len(images) <= 35:
            raise ValueError('图文需要 1–35 张图片')
        for name in images:
            path = Path(name)
            if not path.is_file() or path.suffix.lower() not in {'.jpg','.jpeg','.png','.webp','.bmp','.tif'}:
                raise ValueError(f'图片不存在或格式不支持: {name}')
            if not 0 < path.stat().st_size <= 50 * 1024 * 1024:
                raise ValueError(f'图片必须非空且不超过 50MB: {name}')


def upload(b, images):
    b.command('open', UPLOAD_URL)
    check_login(b)
    wait_for(lambda: click_text(b, '发布图文'), '找不到发布图文标签')
    b.command('upload', 'input[type=file][accept*="image"]',
              *[str(Path(p).resolve()) for p in images], timeout=300)
    wait_for(lambda: b.eval('!!document.querySelector(\'input[placeholder="添加作品标题"]\')'),
             '图片上传超时，标题表单未出现', timeout=300)


def select_music(b, name, category=None):
    if not click_text(b, '选择音乐'):
        raise RuntimeError('找不到选择音乐入口')
    if category:
        wait_for(lambda: click_text(b, category), '找不到音乐分类')
    else:
        b.command('fill', 'input[placeholder*="搜索音乐"]', name)
        b.command('press', 'Enter')
    # Exact title and exactly one card; never choose a list-wide 使用 button.
    js = f'''(() => {{const matches=[...document.querySelectorAll('div,span')]
      .filter(e=>{VISIBLE} && !e.children.length && e.textContent.trim()==={json.dumps(name)});
      const cards=[...new Set(matches.map(e=>e.closest('[class*="card-wrapper"]')).filter(Boolean))];
      if(cards.length!==1) return false; cards[0].click(); return true;}})()'''
    wait_for(lambda: b.eval(js), '目标歌曲不存在或重名，未选择配乐')
    use = f'''(() => {{const cards=[...document.querySelectorAll('[class*="card-container-act"]')]
      .filter(e=>{VISIBLE} && [...e.querySelectorAll('*')].some(n=>!n.children.length && n.textContent.trim()==={json.dumps(name)}));
      if(cards.length!==1) return false;
      const buttons=[...cards[0].querySelectorAll('button,span,div')].filter(e=>!e.children.length && e.textContent.trim()==='使用');
      if(buttons.length!==1) return false; (buttons[0].closest('button')||buttons[0]).click(); return true;}})()'''
    wait_for(lambda: b.eval(use), '目标歌曲激活卡片内未找到唯一使用按钮')
    # The selector panel must close; an exact song label must remain beside 修改音乐.
    verify = f'''(() => {{const labels=[...document.querySelectorAll('div,span')]
      .filter(e=>{VISIBLE} && !e.children.length && e.textContent.trim()==={json.dumps(name)});
      return labels.some(e=>{{let p=e; for(let i=0;i<5 && p && p!==document.body;i++,p=p.parentElement)
      {{if(p.innerText.includes('修改音乐') && !p.querySelector('[class*="card-container-act"]')) return true;}} return false;}});}})()'''
    wait_for(lambda: b.eval(verify), '配乐断言失败，禁止发布')


def fill(b, title, caption, music=None, category=None, declaration='ai'):
    b.command('fill', 'input[placeholder="添加作品标题"]', title)
    wait_for(lambda: b.eval(f'document.querySelector(\'input[placeholder="添加作品标题"]\')?.value === {json.dumps(title)}'), '标题读回不一致')
    js = f'''(() => {{const editors=[...document.querySelectorAll('div[contenteditable=true]')].filter(e=>{VISIBLE});
      if(editors.length!==1) return false; const e=editors[0]; e.focus();
      const r=document.createRange(); r.selectNodeContents(e); const s=window.getSelection(); s.removeAllRanges(); s.addRange(r);
      document.execCommand('insertText',false,{json.dumps(caption)});
      return e.innerText.trim()==={json.dumps(caption.strip())};}})()'''
    if not b.eval(js):
        raise RuntimeError('描述框缺失、不唯一或读回不一致')
    if music:
        select_music(b, music, category)
    if declaration == 'ai':
        opened = click_text(b, '请选择自主声明') or click_text(b, '自主声明')
        if opened:
            wait_for(lambda: click_text(b, '内容由AI生成'), 'AI 声明选项未找到')
            if not click_text(b, '确定', 'button'):
                raise RuntimeError('AI 声明确认失败')


def get_note_link(b, title):
    b.command('open', MANAGE_URL)
    b.command('reload')
    check_login(b)
    wait_for(lambda: b.eval('!!document.querySelector(\'input[placeholder*="搜索作品"]\')'), '管理页搜索框未出现')
    b.command('fill', 'input[placeholder*="搜索作品"]', title)
    b.command('press', 'Enter')
    # Locate the smallest title-bearing card with one edit action; ambiguity fails closed.
    js = f'''(() => {{const titles=[...document.querySelectorAll('*')].filter(e=>{VISIBLE} &&
      (e.textContent||'').trim()==={json.dumps(title)} && !e.children.length);
      const actions=new Set(); for(const t of titles) {{let p=t.parentElement;
      for(let i=0;i<7 && p && p!==document.body;i++,p=p.parentElement) {{
        const edits=[...p.querySelectorAll('button,a,span,div')].filter(e=>{VISIBLE} && !e.children.length && e.textContent.trim()==='编辑作品');
        if(edits.length) {{if(edits.length===1) actions.add(edits[0]); break;}}
      }}}} if(actions.size!==1) return false; [...actions][0].click(); return true;}})()'''
    wait_for(lambda: b.eval(js), '未找到唯一同标题作品，需人工核实，不能重发')
    def read_id():
        url = b.eval('window.location.href') or ''
        parsed = urlparse(url)
        mid = parse_qs(parsed.query).get('mid', [''])[0]
        return mid if parsed.hostname == 'creator.douyin.com' and parsed.path.endswith('/content/post/image') and re.fullmatch(r'\d{19}', mid) else None
    mid = wait_for(read_id, '未捕获图文编辑页 mid')
    return {'ok': True, 'session': SESSION, 'content_id': mid, 'mid': mid,
            'url': f'https://www.douyin.com/note/{mid}'}


def publish(b):
    if not click_text(b, '发布', 'button'):
        raise RuntimeError('未找到唯一可见发布按钮')
    wait_for(lambda: '/content/manage' in (b.eval('window.location.href') or ''), '发布后未跳转管理页，请核实后再操作')


def build_parser():
    p = argparse.ArgumentParser(prog='douyin-note-publish')
    sub = p.add_subparsers(dest='cmd', required=True)
    for cmd in ('open-page','upload','fill','publish','get-note-link','run'):
        s = sub.add_parser(cmd)
        s.add_argument('--headed', action='store_true')
        if cmd in ('run','upload'):
            s.add_argument('--images', nargs='+', required=True)
        if cmd in ('run','fill','get-note-link'):
            s.add_argument('--title', required=True)
        if cmd in ('run','fill'):
            s.add_argument('--caption', default='')
            s.add_argument('--music')
            s.add_argument('--music-category')
            s.add_argument('--declaration', choices=('ai','none'), default='ai')
    return p


def main(argv=None):
    a = build_parser().parse_args(argv)
    b = Browser(a.headed)
    try:
        if a.cmd in ('run','fill','upload'):
            validate(getattr(a,'images',None), getattr(a,'title','上传'), getattr(a,'caption',''))
        with publish_lock():
            try:
                if a.cmd == 'open-page':
                    b.command('open', UPLOAD_URL)
                    result = {'ok':True,'session':SESSION,'url':b.eval('window.location.href'),
                              'hint':'用页面元素判定登录态，未登录交 login-manager'}
                else:
                    result = {'ok':True,'session':SESSION}
                    if a.cmd in ('upload','run'):
                        upload(b,a.images)
                    if a.cmd in ('fill','run'):
                        fill(b,a.title,a.caption,a.music,a.music_category,a.declaration)
                    if a.cmd in ('publish','run'):
                        publish(b)
                    if a.cmd in ('get-note-link','run'):
                        try:
                            result = get_note_link(b,a.title)
                        except LoginRequired:
                            raise
                        except Exception as exc:
                            with tempfile.NamedTemporaryFile(mode='w',prefix='dy-note-debug-',suffix='.json',delete=False) as f:
                                json.dump({'error':str(exc),'title':a.title},f,ensure_ascii=False)
                            print(json.dumps({'ok':False,'error':'LINK_UNCONFIRMED','debug':f.name,'hint':'人工核实，禁止自动重发'},ensure_ascii=False))
                            return 3
                print(json.dumps(result,ensure_ascii=False))
            finally:
                if a.cmd in ('run','get-note-link'):
                    try:
                        b.close()
                    except Exception as exc:
                        print(f'close: {exc}',file=sys.stderr)
        return 0
    except LoginRequired as exc:
        print(f'error: {exc}',file=sys.stderr)
        return 2
    except Exception as exc:
        print(f'error: {exc}',file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
