import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import research_session as session


def brief():
    return dict(goal='Find sustainable audience acquisition', decision='Choose a first experiment',
                audience='Operator', success_criteria=['Traceable actions'], languages=['ru', 'en'],
                output_language='ru', as_of='2026-09-05', sources=['reddit'], seeds=[], budget_usd=1)


def dossier(root):
    (root / 'raw.md').write_text('Original source', encoding='utf-8')
    return dict(schema_version=1, brief=brief(), summary='An evidence-backed experiment', status='partial',
                evidence=[dict(id='E1', source='reddit', kind='post', url='https://www.reddit.com/r/test/comments/abc/example/',
                               author='author', published_at='2026-08-20', retrieved_at='2026-09-05', language='en',
                               text='Original source', artifact='raw.md', verification='direct', limitations=[])],
                claims=[dict(id='C1', text='A bounded observation', evidence_ids=['E1'], confidence='supported',
                             fact_date='2026-08-20', caveat='One source')],
                actions=[dict(id='A1', title='Run an experiment', steps=['Measure a baseline'], why='Test transferability',
                              claim_ids=['C1'], measure='Qualified visits', stop_when='No useful result')],
                coverage=[dict(source='reddit', language='en', status='covered', evidence_ids=['E1'], note='One post'),
                          dict(source='reddit', language='ru', status='unavailable', evidence_ids=[], note='No Russian post read')],
                seeds=[], open_questions=['Does this generalize?'])


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def test_brief_required_goal_and_finite_budget(self):
        for field, value in [('goal', ''), ('budget_usd', float('nan')), ('languages', []), ('as_of', 'yesterday')]:
            data = brief(); data[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                session.validate_brief(data)

    def test_unsafe_seed_rejected(self):
        for url in ['file:///etc/passwd', 'http://localhost/a', 'https://127.0.0.1/a', 'https://user:password@example.com', 'javascript:alert(1)']:
            data = brief(); data['seeds'] = [url]
            with self.subTest(url=url), self.assertRaises(ValueError):
                session.validate_brief(data)

    def test_prepare_is_offline_and_status_does_not_claim_connection(self):
        with patch.object(session, 'collect_state', return_value={'providers': {'openrouter': True}, 'local_media': {}}):
            result = session.prepare(brief(), self.root)
        root = Path(result['run_dir'])
        self.assertTrue((root / 'research-brief.json').is_file())
        self.assertTrue((root / 'research-plan.md').is_file())
        self.assertEqual(result['readiness']['reddit']['status'], 'configured_unverified')

    def test_valid_partial_pair(self):
        data = dossier(self.root)
        session.write_json(self.root / 'research-brief.json', brief())
        result = session.finalize(self.root, data)
        agent = json.loads((self.root / 'agent-context.json').read_text())
        html = (self.root / 'playbook.html').read_text()
        self.assertEqual(agent['status'], 'partial')
        self.assertIn(agent['dossier_sha256'], html)
        self.assertEqual(result['status'], 'partial')

    def test_false_complete_rejected(self):
        data = dossier(self.root); data['status'] = 'complete'
        with self.assertRaisesRegex(ValueError, 'partial'):
            session.validate_dossier(data, brief(), self.root)

    def test_model_summary_cannot_support_fact(self):
        data = dossier(self.root); data['evidence'][0]['verification'] = 'model_reported'
        with self.assertRaisesRegex(ValueError, 'direct'):
            session.validate_dossier(data, brief(), self.root)

    def test_missing_reference_and_missing_language_fail(self):
        data = dossier(self.root); data['claims'][0]['evidence_ids'] = ['E404']
        with self.assertRaises(ValueError): session.validate_dossier(data, brief(), self.root)
        data = dossier(self.root); data['coverage'].pop()
        with self.assertRaises(ValueError): session.validate_dossier(data, brief(), self.root)

    def test_artifact_escape_and_symlink_fail(self):
        data = dossier(self.root); data['evidence'][0]['artifact'] = '../outside.md'
        with self.assertRaises(ValueError): session.validate_dossier(data, brief(), self.root)
        (self.root / 'escape').symlink_to('/etc/hosts')
        data['evidence'][0]['artifact'] = 'escape'
        with self.assertRaises(ValueError): session.validate_dossier(data, brief(), self.root)

    def test_seed_must_be_accounted_for(self):
        data = dossier(self.root); b = brief(); b['seeds'] = ['https://youtube.com/watch?v=123']
        data['brief'] = b
        with self.assertRaises(ValueError): session.validate_dossier(data, b, self.root)

    def test_platform_seed_aliases_preserve_comment_identity(self):
        self.assertEqual(session.source_identity('https://youtu.be/O6zYPRSycJU?t=12'), session.source_identity('https://www.youtube.com/watch?v=O6zYPRSycJU'))
        self.assertNotEqual(session.source_identity('https://www.youtube.com/watch?v=O6zYPRSycJU&lc=comment1'), session.source_identity('https://youtu.be/O6zYPRSycJU'))
        self.assertNotEqual(session.source_identity('https://www.reddit.com/r/test/comments/abc/topic/comment1/'), session.source_identity('https://www.reddit.com/comments/abc/'))
        data = dossier(self.root); data['evidence'][0]['url'] += 'comment1/'
        with self.assertRaisesRegex(ValueError, 'comment permalink'):
            session.validate_dossier(data, brief(), self.root)

    def test_unsupported_cannot_drive_action_and_inference_needs_experiment(self):
        for confidence in ['unsupported', 'inference']:
            data = dossier(self.root); data['claims'][0]['confidence'] = confidence
            with self.subTest(confidence=confidence), self.assertRaises(ValueError):
                session.validate_dossier(data, brief(), self.root)
        data['actions'][0]['experimental'] = True
        session.validate_dossier(data, brief(), self.root)

    def test_invalid_export_does_not_replace_previous_pair(self):
        session.write_json(self.root / 'research-brief.json', brief())
        data = dossier(self.root); session.finalize(self.root, data)
        before = (self.root / 'playbook.html').read_bytes()
        data['claims'][0]['evidence_ids'] = ['missing']
        with self.assertRaises(ValueError): session.finalize(self.root, data)
        self.assertEqual(before, (self.root / 'playbook.html').read_bytes())

    def test_final_targets_cannot_be_raw_evidence(self):
        data = dossier(self.root)
        (self.root / 'playbook.html').write_text('Original source')
        (self.root / 'alias').symlink_to(self.root / 'playbook.html')
        for artifact in ('playbook.html', 'alias'):
            data['evidence'][0]['artifact'] = artifact
            with self.subTest(artifact=artifact), self.assertRaisesRegex(ValueError, 'final export target'):
                session.validate_dossier(data, brief(), self.root)
        self.assertEqual((self.root / 'playbook.html').read_text(), 'Original source')

    def test_budget_reserves_before_call_and_unknown_cost_stays_reserved(self):
        session.write_json(self.root / 'research-brief.json', brief())
        session.reserve(self.root, 'call1', 'grok', .7, 'bounded single request')
        with self.assertRaises(ValueError): session.reserve(self.root, 'call2', 'perplexity', .4, 'request')
        session.settle(self.root, 'call1', None)
        with self.assertRaises(ValueError): session.reserve(self.root, 'call2', 'perplexity', .4, 'request')
        session.settle(self.root, 'call1', .02)
        saved = json.loads((self.root / 'spending.json').read_text())
        self.assertAlmostEqual(saved['committed_usd'], .02)
        self.assertAlmostEqual(session.reserve(self.root, 'call2', 'perplexity', .4, 'request')['committed_usd'], .42)


if __name__ == '__main__': unittest.main()
