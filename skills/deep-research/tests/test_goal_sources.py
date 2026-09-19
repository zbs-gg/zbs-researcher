import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('goal_source_runner', SCRIPTS / 'deep-research.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class GoalSourceTests(unittest.TestCase):
    def test_new_sources_are_explicit_and_correctly_billed(self):
        for name in ('reddit-web', 'reddit-thread', 'reddit-live', 'youtube-social'):
            self.assertFalse(runner.CONNECTORS[name].default)
        with patch.dict(runner.KEYS, {'perplexity': None, 'openrouter': 'fake'}):
            self.assertEqual(runner._fire_provider('reddit-web'), 'openrouter')
        self.assertTrue(runner._fire_is_paid('reddit-live', runner.CONNECTORS['reddit-live']))
        self.assertFalse(runner._fire_is_paid('reddit-thread', runner.CONNECTORS['reddit-thread']))

    def test_xai_ticks_cost_is_actual_and_not_double_counted(self):
        self.assertAlmostEqual(runner._usage_cost([{'cost_in_usd_ticks': 201534000, 'cost': .02}]), .0201534)

    def test_grok_keeps_tool_trace_and_bounds_requested(self):
        response = {'id': 'test', 'status': 'completed', 'output': [{'type': 'x_search_call', 'id': 'tool'},
                    {'type': 'message', 'content': [{'type': 'output_text', 'text': 'Observed'}]}],
                    'usage': {'cost_in_usd_ticks': 200000000}}
        with tempfile.TemporaryDirectory() as temp, patch.dict(runner.KEYS, {'grok': 'fake'}), patch.object(runner, 'post_json', return_value=response) as post:
            path = Path(temp) / 'grok.md'
            runner.channel_grok('https://x.com/example/status/123', path, 3, max_turns=2, max_output_tokens=1500)
            self.assertEqual(post.call_args.args[1]['max_turns'], 2)
            self.assertFalse(post.call_args.args[1]['store'])
            self.assertEqual(json.loads(path.with_suffix('.response.json').read_text())['output'][0]['type'], 'x_search_call')

    def test_bounds_never_silently_disappear_on_fallback_or_other_mode(self):
        with patch.dict(runner.KEYS, {'grok': None, 'openrouter': 'fake'}), patch.object(runner, 'post_json') as post:
            with self.assertRaisesRegex(ValueError, 'no fallback'):
                runner.channel_grok('topic', Path('output.md'), 1, max_turns=2)
            post.assert_not_called()
        result = subprocess.run([sys.executable, str(SCRIPTS / 'deep-research.py'), '--list-connectors', '--grok-max-turns', '2'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('cannot be silently ignored', result.stderr)

    def test_social_video_disables_paid_audio_and_reads_comments(self):
        with patch.object(runner, 'channel_youtube', return_value=1) as channel, patch.object(Path, 'read_text', return_value='{"evidence": [{}, {}]}'):
            self.assertEqual(runner.channel_youtube_social('topic', Path('output.md'), 3), 2)
            self.assertTrue(channel.call_args.kwargs['comments'])
            self.assertFalse(channel.call_args.kwargs['transcribe'])

    def test_prompts_have_current_date_without_technical_topic_bias(self):
        self.assertIn(runner._dt.date.today().isoformat(), runner._grok_user('topic'))
        self.assertNotIn('2025-2026', runner._gemini_prompt('topic'))
        self.assertNotIn('technical topics', runner._GROK_SYSTEM)


if __name__ == '__main__': unittest.main()
