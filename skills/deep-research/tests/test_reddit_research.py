import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

scripts_path = str(Path(__file__).resolve().parents[1] / 'scripts')
path_added = scripts_path not in sys.path
if path_added:
    sys.path.insert(0, scripts_path)
try:
    import connectors
    from connectors import attach_runner
    from connectors import reddit_research as reddit
finally:
    if path_added:
        sys.path.remove(scripts_path)


class RedditResearchTests(unittest.TestCase):
    def setUp(self):
        previous = connectors._RUNNER_GLOBALS
        self.addCleanup(attach_runner, previous)

    def test_thread_preserves_text_authorship_parent_and_missing_dates(self):
        fetch = Mock(side_effect=[{'data': [{'id': 'abc123', 'title': 'Discussion', 'selftext': 'Post body', 'author': 'owner', 'created_utc': 1700000000, 'subreddit': 'test'}]}, {'data': [{'id': 'xyz123', 'body': 'Комментарий', 'author': 'reader', 'parent_id': 't3_abc123', 'link_id': 't3_abc123'}]}])
        attach_runner({'_arctic_shift_json': fetch})
        with tempfile.TemporaryDirectory() as folder:
            result = reddit.channel_reddit_thread('https://www.reddit.com/r/test/comments/abc123/topic/', folder)
            self.assertEqual(len(result['evidence']), 2)
            comment = result['evidence'][1]
            self.assertEqual(comment['text'], 'Комментарий')
            self.assertEqual(comment['parent_id'], 't3_abc123')
            self.assertIsNone(comment['published_at'])
            self.assertEqual(comment['verification'], 'direct')
            self.assertTrue(Path(folder, result['evidence'][0]['artifact']).exists())
            self.assertIn('link_id=abc123', fetch.call_args_list[1].args[0])

    def test_comment_failure_keeps_post(self):
        attach_runner({'_arctic_shift_json': Mock(side_effect=[{'data': [{'id': 'abc123', 'selftext': 'readable'}]}, RuntimeError('down')])})
        with tempfile.TemporaryDirectory() as folder:
            result = reddit.channel_reddit_thread('https://reddit.com/comments/abc123', folder)
            self.assertEqual(result['status'], 'partial')
            self.assertEqual(result['comments_status'], 'unavailable')
            self.assertEqual(len(result['evidence']), 1)

    def test_rejects_nonpost_private_and_lookalike_urls_without_fetch(self):
        fetch = Mock()
        attach_runner({'_arctic_shift_json': fetch})
        for url in ['https://reddit.com/r/test/', 'https://reddit.com.evil.test/comments/abc', 'http://reddit.com/comments/abc', 'https://u:p@reddit.com/comments/abc', 'https://127.0.0.1/comments/abc', 'https://reddit.com:444/comments/abc']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                reddit.channel_reddit_thread(url, '.')
        fetch.assert_not_called()

    def test_removed_and_wrong_thread_comments_are_not_evidence(self):
        attach_runner({'_arctic_shift_json': Mock(side_effect=[{'data': []}, {'data': [{'id': 'one', 'body': '[deleted]'}, {'id': 'two', 'body': 'wrong', 'link_id': 't3_other'}]}])})
        with tempfile.TemporaryDirectory() as folder:
            result = reddit.channel_reddit_thread('https://reddit.com/comments/abc123', folder)
            self.assertEqual(result['evidence'], [])
            self.assertNotEqual(result['status'], 'complete')

    def test_web_uses_existing_billing_route_and_labels_model_report(self):
        sink = []
        def lens(query, out_path, max_items, usage_sink=None):
            self.assertIn('site:reddit.com', query)
            self.assertIs(usage_sink, sink)
            out_path.write_text('A summary https://www.reddit.com/r/test/comments/abc123/topic/')
        attach_runner({'channel_perplexity': lens})
        with tempfile.TemporaryDirectory() as folder:
            result = reddit.channel_reddit_web('research', folder, usage_sink=sink)
            self.assertEqual(result['evidence'][0]['verification'], 'model_reported')
            self.assertEqual(len(result['discovered_urls']), 1)
            self.assertEqual(result['status'], 'partial')

    def test_comment_limit_is_clamped_and_duplicate_ids_are_deduplicated(self):
        fetch = Mock(side_effect=[{'data': []}, {'data': [{'id': 'abc', 'body': 'hello'}, {'id': 'abc', 'body': 'hello'}]}])
        attach_runner({'_arctic_shift_json': fetch})
        with tempfile.TemporaryDirectory() as folder:
            result = reddit.channel_reddit_thread('https://reddit.com/comments/abc123', folder, max_comments=10000)
            self.assertEqual(len(result['evidence']), 1)
            self.assertIn('limit=100', fetch.call_args_list[1].args[0])

    def test_future_dates_are_unknown_and_failures_never_reveal_exception_payload(self):
        fetch = Mock(side_effect=[{'data': [{'id': 'abc123', 'selftext': 'hello', 'created_utc': 99999999999}]}, RuntimeError('pretend-secret-token')])
        attach_runner({'_arctic_shift_json': fetch})
        with tempfile.TemporaryDirectory() as folder:
            result = reddit.channel_reddit_thread('https://reddit.com/comments/abc123', folder)
            self.assertIsNone(result['evidence'][0]['published_at'])
            self.assertNotIn('pretend-secret-token', json.dumps(result))

    def test_live_single_request_flattens_replies_and_tracks_credits(self):
        fetch = Mock(return_value={'success': True, 'credits_charged': 1,
            'post': {'id': 'abc123', 'title': 'Title', 'selftext': 'Body', 'author': 'owner'},
            'comments': [{'id': 'c1', 'body': 'Parent', 'author': 'one', 'replies': {'items': [
                {'id': 'c2', 'body': 'Ответ', 'author': 'two', 'parent_id': 't1_c1'}]}}],
            'more': {'has_more': True, 'cursor': 'must-not-follow'}})
        attach_runner({'KEYS': {'scrapecreators': 'secret-fixture'}, 'get_json': fetch})
        usage = []
        url = 'https://www.reddit.com/r/test/comments/abc123/topic/'
        with tempfile.TemporaryDirectory() as folder:
            result = reddit.channel_reddit_live(url, folder, usage_sink=usage)
            self.assertEqual(len(result['evidence']), 3)
            self.assertEqual(result['evidence'][2]['parent_id'], 't1_c1')
            self.assertEqual(result['seed_url'], url)
            self.assertEqual(result['evidence'][0]['url'], url)
            self.assertEqual(usage, [{'provider': 'scrapecreators', 'credits_charged': 1}])
            self.assertEqual(result['comments_status'], 'partial')
            self.assertTrue(result['has_more'])
            self.assertNotIn('secret-fixture', json.dumps(result))
            for path in Path(folder).iterdir():
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        fetch.assert_called_once()
        self.assertEqual(fetch.call_args.kwargs['timeout'], 60)

    def test_live_missing_key_does_not_fetch_and_failure_does_not_fallback(self):
        fetch = Mock(side_effect=RuntimeError('private-response-key'))
        attach_runner({'KEYS': {}, 'get_json': fetch})
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(RuntimeError):
                reddit.channel_reddit_live('https://reddit.com/comments/abc123', folder)
            fetch.assert_not_called()
            attach_runner({'KEYS': {'scrapecreators': 'fixture'}, 'get_json': fetch})
            with self.assertRaisesRegex(RuntimeError, 'ScrapeCreators request failed') as exc:
                reddit.channel_reddit_live('https://reddit.com/comments/abc123', folder)
            self.assertNotIn('private-response-key', str(exc.exception))
            fetch.assert_called_once()

    def test_live_honors_comment_bound_and_does_not_trust_remote_links(self):
        fetch = Mock(return_value={'success': True, 'comments': [
            {'id': 'bad', 'body': 'wrong post', 'link_id': 't3_wrong'},
            {'id': 'gone', 'body': '[deleted]'},
            {'id': 'c1', 'body': 'one', 'url': 'http://127.0.0.1/private'},
            {'id': 'c2', 'body': 'two'}]})
        attach_runner({'KEYS': {'scrapecreators': 'fixture'}, 'get_json': fetch})
        with tempfile.TemporaryDirectory() as folder:
            result = reddit.channel_reddit_live('https://reddit.com/comments/abc123', folder, max_comments=1)
            self.assertEqual(len(result['evidence']), 1)
            self.assertEqual(result['evidence'][0]['source_id'], 'c1')
            self.assertNotIn('127.0.0.1', result['evidence'][0]['url'])
            self.assertIn('truncated', ' '.join(result['limitations']))
        fetch.assert_called_once()

    def test_comment_seed_fetches_target_by_id_and_parent_keeps_post_url(self):
        seed = 'https://www.reddit.com/r/test/comments/abc123/topic/target123/'
        fetch = Mock(side_effect=[{'data': [{'id': 'abc123', 'title': 'Parent'}]},
            {'data': []}, {'data': [{'id': 'target123', 'body': 'Target body', 'link_id': 't3_abc123'}]}])
        attach_runner({'_arctic_shift_json': fetch})
        with tempfile.TemporaryDirectory() as folder:
            result = reddit.channel_reddit_thread(seed, folder)
            post, comment = result['evidence']
            self.assertNotEqual(post['url'], seed)
            self.assertEqual(post['url'], 'https://www.reddit.com/r/test/comments/abc123/topic/')
            self.assertEqual(comment['url'], seed)
            self.assertEqual(result['seed_status'], 'read')
        self.assertIn('/comments/ids?ids=target123', fetch.call_args.args[0])
        self.assertEqual(fetch.call_count, 3)

    def test_missing_comment_seed_never_aliases_parent_body(self):
        seed = 'https://reddit.com/user/author/comments/abc123/topic/target123/'
        fetch = Mock(side_effect=[{'data': [{'id': 'abc123', 'title': 'Parent'}]}, {'data': []}, {'data': []}])
        attach_runner({'_arctic_shift_json': fetch})
        with tempfile.TemporaryDirectory() as folder:
            result = reddit.channel_reddit_thread(seed, folder)
            self.assertEqual(result['seed_status'], 'unavailable')
            self.assertFalse(any(e['url'] == seed for e in result['evidence']))

    def test_user_post_urls_and_live_comment_seed_missing_target(self):
        seed = 'https://www.reddit.com/user/author/comments/abc123/topic/target123/'
        fetch = Mock(return_value={'success': True, 'post': {'id': 'abc123', 'title': 'Parent'}, 'comments': []})
        attach_runner({'KEYS': {'scrapecreators': 'fixture'}, 'get_json': fetch})
        with tempfile.TemporaryDirectory() as folder:
            result = reddit.channel_reddit_live(seed, folder)
            self.assertEqual(result['seed_status'], 'unavailable')
            self.assertNotEqual(result['evidence'][0]['url'], seed)
        fetch.assert_called_once()

    def test_existing_target_comment_does_not_trigger_extra_request(self):
        seed = 'https://reddit.com/comments/abc123/topic/target123/'
        fetch = Mock(side_effect=[{'data': []}, {'data': [{'id': 'target123', 'body': 'Found', 'link_id': 't3_abc123'}]}])
        attach_runner({'_arctic_shift_json': fetch})
        with tempfile.TemporaryDirectory() as folder:
            result = reddit.channel_reddit_thread(seed, folder)
            self.assertEqual(result['seed_status'], 'read')
            self.assertEqual(result['evidence'][0]['url'], seed)
        self.assertEqual(fetch.call_count, 2)


if __name__ == '__main__':
    unittest.main()
