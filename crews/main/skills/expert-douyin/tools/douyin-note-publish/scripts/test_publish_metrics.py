import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[7]
TOOLS = ROOT/'crews/main/skills/expert-douyin/tools'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

note = load('note_publish', TOOLS/'douyin-note-publish/scripts/publish_douyin_note.py')
status = load('platform_status', ROOT/'crews/main/skills/published-track/scripts/platform-status.py')


class NoteTests(unittest.TestCase):
    def test_validate_before_browser(self):
        with patch.object(note, 'Browser') as browser:
            self.assertEqual(note.main(['run','--images','missing.png','--title','X']),1)
            browser.return_value.command.assert_not_called()
        with self.assertRaises(ValueError):
            note.validate(title='中'*21)
        with self.assertRaises(ValueError):
            note.validate(images=['x']*36,title='X')

    def test_link_requires_image_edit_url_and_preserves_id(self):
        b=Mock()
        b.eval.side_effect=['https://creator.douyin.com/creator-micro/content/manage',True,True,
                           'https://creator.douyin.com/creator-micro/content/post/image?mid=7687034742688058662&enter_from=edit_item']
        result=note.get_note_link(b,'标题')
        self.assertEqual(result['url'],'https://www.douyin.com/note/7687034742688058662')
        self.assertIn(unittest.mock.call('reload'),b.command.call_args_list)

    def test_music_failure_stops_before_publish_and_closes(self):
        with patch.object(note,'validate'), patch.object(note,'Browser') as browser, \
             patch.object(note,'upload'), patch.object(note,'fill',side_effect=RuntimeError('wrong music')), \
             patch.object(note,'publish') as publish:
            self.assertEqual(note.main(['run','--images','x.png','--title','X','--music','song']),1)
            publish.assert_not_called()
            browser.return_value.close.assert_called_once()

    def test_link_failure_never_republishes(self):
        with patch.object(note,'validate'), patch.object(note,'Browser') as browser, \
             patch.object(note,'upload'), patch.object(note,'fill'), patch.object(note,'publish') as publish, \
             patch.object(note,'get_note_link',side_effect=RuntimeError('ambiguous title')):
            self.assertEqual(note.main(['run','--images','x.png','--title','X']),3)
            publish.assert_called_once()
            browser.return_value.close.assert_called_once()

    def test_shared_lock_fail_first(self):
        with note.publish_lock():
            with self.assertRaisesRegex(RuntimeError,'正忙'):
                with note.publish_lock():
                    pass


class MetricsTests(unittest.TestCase):
    def test_platform_status(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace=Path(folder)
            self.assertFalse(status.platform_status(workspace,'douyin')['enabled'])
            directory=workspace/'douyin/calibration'
            directory.mkdir(parents=True)
            legacy=directory/'.platform-state.json'
            legacy.write_text('{"enabled":true}')
            self.assertTrue(status.platform_status(workspace,'douyin')['enabled'])
            current=directory/'platform-state.json'
            current.write_text('{"enabled":false}')
            self.assertFalse(status.platform_status(workspace,'douyin')['enabled'])
            current.write_text('{"enabled":"true"}')
            self.assertFalse(status.platform_status(workspace,'douyin')['ok'])
            current.write_text('invalid')
            self.assertFalse(status.platform_status(workspace,'douyin')['ok'])

    def test_note_and_video_extraction(self):
        script=ROOT/'crews/main/skills/published-track/scripts/fetch-and-update-metrics.sh'
        text=script.read_text()
        func=text[text.index('extract_content_id()'):text.index('# ─── 平台配置')]
        for kind in ('note','video'):
            proc=subprocess.run(['bash','-c',func+'\nextract_content_id douyin "$1"','test',
                                 f'https://www.douyin.com/{kind}/7687034742688058662?x=1'],capture_output=True,text=True)
            self.assertEqual(proc.stdout.strip(),'7687034742688058662')

if __name__=='__main__':
    unittest.main()
