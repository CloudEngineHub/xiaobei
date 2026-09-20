"""Local DOM regression via camoufox-cli; never opens Douyin or publishes."""
import sys
from pathlib import Path
import json
import shutil
import subprocess
import unittest
import uuid
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[2] /
    'crews/main/skills/expert-douyin/tools/douyin-note-publish/scripts'))
import publish_douyin_note as note


class LocalBrowser(note.Browser):
    def __init__(self):
        self.session = 'note-link-test-' + uuid.uuid4().hex[:10]

    def command(self, *args, timeout=60):
        result = subprocess.run(
            ['camoufox-cli', '--session', self.session, '--json', *args],
            capture_output=True, text=True, timeout=timeout, check=True)
        envelope = json.loads(result.stdout)
        if envelope.get('success') is False or envelope.get('ok') is False:
            raise RuntimeError(str(envelope))
        data = envelope.get('data')
        return data.get('result') if isinstance(data, dict) and 'result' in data else data


@unittest.skipUnless(shutil.which('camoufox-cli'), 'camoufox-cli required')
class LinkDOMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = LocalBrowser()

    @classmethod
    def tearDownClass(cls):
        cls.b.close()

    def card(self, text, style=''):
        return f'''<div class="info-title-operation-test" style="{style}">
          <div class="info-title-text-test">{text}</div>
          <div onclick="document.body.dataset.clicked=String(Number(document.body.dataset.clicked||0)+1)"><svg></svg><span>编辑作品</span></div>
        </div>'''

    def open(self, html):
        self.b.command('open', 'data:text/html;charset=utf-8,' + quote(html))

    def test_combined_title_caption_with_nested_markup(self):
        self.open(self.card('发完笔记,<em>前30分钟</em>决定生死。这里是正文 #话题'))
        result = note.note_link_candidate(self.b, '发完笔记,前30分钟决定生死')
        self.assertEqual(result, {'titles':1,'actions':1,'status':'unique'})
        self.assertFalse(self.b.eval('!!document.body.dataset.clicked'))
        note.note_link_candidate(self.b, '发完笔记,前30分钟决定生死', click=True)
        self.assertEqual(self.b.eval('document.body.dataset.clicked'), '1')

    def test_hidden_duplicate_and_unrelated_card(self):
        self.open(self.card('目标标题。正文') + self.card('目标标题。隐藏副本','display:none')
                  + self.card('另一篇作品正文包含目标标题'))
        self.assertEqual(note.note_link_candidate(self.b,'目标标题')['status'],'unique')

    def test_multiple_prefix_candidates_do_not_click(self):
        self.open(self.card('目标标题。正文') + self.card('目标标题加长版。正文'))
        self.assertEqual(note.note_link_candidate(self.b,'目标标题',click=True)['status'],'ambiguous')
        self.assertFalse(self.b.eval('!!document.body.dataset.clicked'))

    def test_visible_candidate_disappears_then_returns_during_search(self):
        card = self.card('目标标题。正文')
        self.open(card)
        # 复现旧代码第一次检查成功、随后搜索结果替换使第二次检查为空。
        self.assertEqual(note.note_link_candidate(self.b,'目标标题')['status'],'unique')
        self.b.eval(f'''(() => {{
          document.body.innerHTML='';
          setTimeout(() => {{document.body.innerHTML={json.dumps(card)};}}, 2000);
          return true;
        }})()''')
        self.assertEqual(note.note_link_candidate(self.b,'目标标题')['status'],'missing')
        note.wait_note_edit(self.b,'目标标题',timeout=10)
        self.assertEqual(self.b.eval('document.body.dataset.clicked'),'1')

    def test_missing_edit_or_title_does_not_click(self):
        for html in ('<div class="info-title-text-test">目标标题。正文</div>',
                     self.card('其他标题'), '<div>目标标题</div><span>编辑作品</span>'):
            with self.subTest(html=html):
                self.open(html)
                self.assertEqual(note.note_link_candidate(self.b,'目标标题',click=True)['status'],'missing')
                self.assertFalse(self.b.eval('!!document.body.dataset.clicked'))


if __name__ == '__main__':
    unittest.main()
