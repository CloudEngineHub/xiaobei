import importlib.util
import json
import io
from contextlib import redirect_stdout
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT/'crews/main/skills/expert-douyin/tools'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

note = load('note_publish', TOOLS/'douyin-note-publish/scripts/publish_douyin_note.py')
status = load('platform_status', ROOT/'crews/main/skills/published-track/scripts/platform-status.py')


class NoteTests(unittest.TestCase):
    def setUp(self):
        sleeper = patch.object(note.time, 'sleep')
        sleeper.start()
        self.addCleanup(sleeper.stop)

    def test_validate_before_browser(self):
        with patch.object(note, 'Browser') as browser:
            self.assertEqual(note.main(['run','--original-sound','--images','missing.png','--title','X']),1)
            browser.return_value.command.assert_not_called()
        with self.assertRaises(ValueError):
            note.validate(title='中'*21)
        with self.assertRaises(ValueError):
            note.validate(images=['x']*36,title='X')

    def test_link_requires_image_edit_url_and_preserves_id(self):
        b=Mock()
        def evaluate(js):
            if js == 'window.location.href':
                return 'https://creator.douyin.com/creator-micro/content/post/image?mid=7687034742688058662&enter_from=edit_item'
            if 'const result={titles:' in js:
                return {'status':'unique','titles':1,'actions':1}
            if 'return inputs.length===1 && inputs[0].value' in js:
                return {'title':'标题'}
            return True
        b.eval.side_effect=evaluate
        result=note.get_note_link(b,'标题')
        self.assertEqual(result['url'],'https://www.douyin.com/note/7687034742688058662')
        self.assertIn(unittest.mock.call('reload'),b.command.call_args_list)
        self.assertFalse(any(c.args[0] == 'fill' for c in b.command.call_args_list))
        self.assertIn(unittest.mock.call('press', 'Enter'), b.command.call_args_list)

    def test_link_rejects_editor_title_mismatch(self):
        b=Mock()
        def evaluate(js):
            if js == 'window.location.href':
                return 'https://creator.douyin.com/creator-micro/content/post/image?mid=7687034742688058662'
            if 'return inputs.length===1 && inputs[0].value' in js:
                return {'title':'标题加长版'}
            return True
        b.eval.side_effect=evaluate
        with patch.object(note,'note_link_candidate',return_value={'status':'unique'}):
            with self.assertRaisesRegex(RuntimeError,'标题不一致'):
                note.get_note_link(b,'标题')

    def test_link_ambiguity_never_clicks(self):
        b=Mock()
        b.eval.return_value=True
        with patch.object(note,'check_login'), patch.object(note,'fill_input'), \
             patch.object(note,'note_link_candidate',return_value={'status':'ambiguous','titles':2,'actions':2}) as candidate:
            with self.assertRaisesRegex(RuntimeError,'多个标题前缀候选'):
                note.get_note_link(b,'标题')
            candidate.assert_called_once_with(b,'标题',click=True)

    def test_link_research_is_bounded_and_never_publishes(self):
        b=Mock()
        b.eval.return_value=True
        def wait(browser, action, message, timeout=60):
            if not action():
                raise note.WaitTimeout(message)
            return True
        with patch.object(note,'check_login'), patch.object(note,'fill_input'), \
             patch.object(note,'wait_for',side_effect=wait), \
             patch.object(note,'note_link_candidate',return_value={'status':'missing','titles':0,'actions':0}), \
             patch.object(note,'publish') as publish:
            with self.assertRaisesRegex(RuntimeError,'重新搜索4次'):
                note.get_note_link(b,'标题')
            self.assertEqual(b.command.call_args_list.count(unittest.mock.call('press','Enter')),4)
            publish.assert_not_called()

    def test_link_recovers_after_search_refresh(self):
        b=Mock()
        def evaluate(js):
            if js == 'window.location.href':
                return 'https://creator.douyin.com/creator-micro/content/post/image?mid=7687034742688058662'
            if 'return inputs.length===1 && inputs[0].value' in js:
                return {'title':'标题'}
            return True
        b.eval.side_effect=evaluate
        def wait(browser, action, message, timeout=60):
            result=action()
            if not result:
                raise note.WaitTimeout(message)
            return result
        with patch.object(note,'wait_for',side_effect=wait), \
             patch.object(note,'note_link_candidate',side_effect=[
                 {'status':'missing'}, {'status':'unique'}]) as candidate:
            self.assertEqual(note.get_note_link(b,'标题')['mid'],'7687034742688058662')
            self.assertEqual(b.command.call_args_list.count(unittest.mock.call('press','Enter')),2)
            self.assertEqual(candidate.call_args_list[-1],unittest.mock.call(b,'标题',click=True))

    def test_candidate_missing_during_list_replacement_is_retried(self):
        b=Mock()
        with patch.object(note,'check_login'), patch.object(note,'note_link_candidate',side_effect=[
                {'status':'missing','titles':0,'actions':0},
                {'status':'missing','titles':0,'actions':0},
                {'status':'unique','titles':1,'actions':1}]) as candidate:
            note.wait_note_edit(b,'标题')
            self.assertEqual(candidate.call_count,3)
            self.assertTrue(all(call.kwargs == {'click':True} for call in candidate.call_args_list))

    def test_click_transport_error_is_not_retried(self):
        b=Mock()
        with patch.object(note,'check_login'), patch.object(note,'note_link_candidate',
                side_effect=RuntimeError('browser transport failed')) as candidate:
            with self.assertRaisesRegex(RuntimeError,'browser transport failed'):
                note.wait_note_edit(b,'标题')
            candidate.assert_called_once()

    def test_fill_uses_eval_and_stops_on_rejected_input(self):
        b = Mock()
        b.eval.side_effect = ['https://creator.douyin.com/creator-micro/content/post/image', False]
        with self.assertRaisesRegex(RuntimeError, '读回不一致'):
            note.fill(b, '标题', '描述', 'none')
        b.command.assert_not_called()

    def test_fill_stops_when_controlled_input_reverts(self):
        b = Mock()
        b.eval.side_effect = [True, False]
        with self.assertRaisesRegex(RuntimeError, '更新后读回不一致'):
            note.fill_input(b, 'input', '标题')

    def test_fill_failure_stops_before_publish_and_closes(self):
        with patch.object(note,'validate'), patch.object(note,'Browser') as browser, \
             patch.object(note,'upload'), patch.object(note,'fill',side_effect=RuntimeError('wrong music')), \
             patch.object(note,'publish') as publish:
            self.assertEqual(note.main(['run','--original-sound','--images','x.png','--title','X']),1)
            publish.assert_not_called()
            browser.return_value.close.assert_called_once()

    def test_link_failure_never_republishes(self):
        with patch.object(note,'validate'), patch.object(note,'Browser') as browser, \
             patch.object(note,'upload'), patch.object(note,'fill'), patch.object(note,'publish') as publish, \
             patch.object(note,'get_note_link',side_effect=RuntimeError('ambiguous title')):
            self.assertEqual(note.main(['run','--original-sound','--images','x.png','--title','X']),3)
            publish.assert_called_once()
            browser.return_value.close.assert_called_once()

    def test_login_required_before_fill_does_not_modify_form(self):
        b=Mock()
        b.eval.return_value='https://creator.douyin.com/login?redirect=upload'
        with self.assertRaises(note.LoginRequired):
            note.fill(b,'标题','正文')
        b.command.assert_not_called()

    def test_wait_detects_login_redirect_without_waiting_for_timeout(self):
        b=Mock()
        b.eval.side_effect=['https://creator.douyin.com/creator-micro/content/upload',
                            'https://creator.douyin.com/login']
        action=Mock(return_value=False)
        with patch.object(note.time,'sleep'):
            with self.assertRaises(note.LoginRequired):
                note.wait_for(b,action,'timeout')
        action.assert_called_once()

    def test_login_word_in_query_is_not_logout(self):
        b=Mock()
        b.eval.return_value='https://creator.douyin.com/creator-micro/content/upload?from=/login'
        note.check_login(b)

    def test_login_failure_run_stops_and_reports_publish_stage(self):
        for after_publish in (False,True):
            with self.subTest(after_publish=after_publish), patch.object(note,'validate'), \
                 patch.object(note,'Browser') as browser, patch.object(note,'upload') as upload, \
                 patch.object(note,'fill') as fill, patch.object(note,'publish') as publish, \
                 patch.object(note,'get_note_link') as link:
                if after_publish:
                    link.side_effect=note.LoginRequired('SESSION_EXPIRED')
                else:
                    upload.side_effect=note.LoginRequired('SESSION_EXPIRED')
                output=io.StringIO()
                with redirect_stdout(output):
                    code=note.main(['run','--original-sound','--images','x.png','--title','标题'])
                self.assertEqual(code,2)
                result=json.loads(output.getvalue())
                self.assertEqual(result['error'],'SESSION_EXPIRED')
                self.assertEqual(result['publish_attempted'],after_publish)
                self.assertEqual(publish.call_count,1 if after_publish else 0)
                if not after_publish:
                    fill.assert_not_called()
                browser.return_value.close.assert_called_once()

    def test_music_choice_must_come_from_current_page(self):
        b = Mock()
        b.eval.side_effect = ['https://creator.douyin.com/creator-micro/content/post/image', None]
        with self.assertRaisesRegex(RuntimeError, '候选已失效'):
            note.select_music(b, 'invented-song')
        self.assertEqual(b.eval.call_count, 2)
        b.command.assert_not_called()

    def test_publish_blocks_missing_or_mismatched_music(self):
        for selected in (None, {'name': '实际候选'}):
            with self.subTest(selected=selected):
                b = Mock()
                b.eval.side_effect = ['https://creator.douyin.com/creator-micro/content/post/image', selected]
                with patch.object(note, 'verify_music', return_value=False), patch.object(note, 'click_text') as click:
                    with self.assertRaisesRegex(RuntimeError, '尚未确认配乐'):
                        note.publish(b)
                    click.assert_not_called()

    def test_upload_waits_for_all_images_before_returning(self):
        b = Mock()
        b.eval.side_effect = [
            'https://creator.douyin.com/creator-micro/content/upload',
            'https://creator.douyin.com/creator-micro/content/upload', True,
            'https://creator.douyin.com/creator-micro/content/upload', True,
            'https://creator.douyin.com/creator-micro/content/post/image', False,
            'https://creator.douyin.com/creator-micro/content/post/image', True,
        ]
        with patch.object(note.time, 'sleep') as sleep:
            note.upload(b, ['one.png', 'two.png'])
        sleep.assert_called_once()
        self.assertIn('已添加2张图片', b.eval.call_args.args[0])

    def test_upfront_music_and_implicit_original_sound_rejected(self):
        parser = note.build_parser()
        for args in (['upload', '--images', 'x.png', '--music', 'song'],
                     ['run', '--images', 'x.png', '--title', 'X']):
            with self.subTest(args=args), self.assertRaises(SystemExit):
                parser.parse_args(args)

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
