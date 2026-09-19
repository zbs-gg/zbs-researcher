import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from playbook import render_playbook


class PlaybookTests(unittest.TestCase):
    def test_untrusted_text_is_escaped_and_no_remote_assets(self):
        data = dict(brief=dict(goal='<script>alert(1)</script>', decision='Choose', audience='You', output_language='ru', as_of='2026-09-05'),
                    summary='A & B', status='partial', dossier_sha256='abc123', claims=[], actions=[], evidence=[], coverage=[], seeds=[], open_questions=[])
        html = render_playbook(data)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>alert', html)
        self.assertIn('abc123', html)
        self.assertIn('width=device-width', html)
        self.assertNotIn('fonts.googleapis', html)
        self.assertIn('agent-context.json', html)


if __name__ == '__main__': unittest.main()
