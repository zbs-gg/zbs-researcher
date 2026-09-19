"""Offline release/documentation integrity; never reads private benchmark inputs."""
import hashlib
import json
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless((ROOT / '.claude-plugin/plugin.json').exists(), 'repository-level documentation check')
class ReleaseDocsTests(unittest.TestCase):
    def test_candidate_versions_and_history(self):
        plugin = json.loads((ROOT / '.claude-plugin/plugin.json').read_text())
        market = json.loads((ROOT / '.claude-plugin/marketplace.json').read_text())
        installer = json.loads((ROOT / 'installer/package.json').read_text())
        selected = next(row for row in market['plugins'] if row['name'] == 'deep-research')
        self.assertEqual([plugin['version'], selected['version'], installer['version']], ['0.7.0'] * 3)
        changelog = (ROOT / 'CHANGELOG.md').read_text()
        self.assertRegex(changelog, r'(?m)^## 0\.7\.0\b')
        self.assertRegex(changelog, r'(?m)^## 0\.6\.0\b')
        self.assertRegex(changelog, r'(?m)^## 0\.5\.0\b')

    def test_historical_case_cannot_pose_as_new_version_victory(self):
        data = json.loads((ROOT / 'docs/comparison/case.json').read_text())
        self.assertTrue(data['historical'])
        self.assertFalse(data['current_version_tested'])
        self.assertFalse(data['owner_judgment_complete'])
        self.assertIsNone(data['winner'])
        self.assertEqual(data['captured_on'], '2026-08-14')
        self.assertEqual({x['id'] for x in data['methods']}, {'researcher', 'parallel'})
        self.assertGreaterEqual(len(data['limitations']), 4)

    def test_answer_excerpts_have_valid_hashes_and_no_private_paths(self):
        folder = ROOT / 'docs/comparison'
        data = json.loads((folder / 'case.json').read_text())
        for method in data['methods']:
            path = folder / method['answer_file']
            self.assertTrue(path.resolve().is_relative_to(folder.resolve()))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), method['excerpt_sha256'])
            self.assertRegex(method['source_sha256'], r'^[a-f0-9]{64}$')
            self.assertGreater(len(path.read_text()), 1000)
            self.assertTrue(method['extraction'])
        for path in folder.iterdir():
            if path.is_file():
                text = path.read_text()
                self.assertNotRegex(text, r'/Users/|/home/|trun_[a-z0-9]+|sk-[A-Za-z0-9]{20,}')

    def test_comparison_links_work_without_private_runtime_files(self):
        paths = [ROOT / 'README.md', ROOT / 'docs/comparison/README.md']
        for path in paths:
            links = re.findall(r'\]\(([^\s)]+)\)', path.read_text())
            for link in links:
                parsed = urlsplit(link)
                if parsed.scheme or not parsed.path:
                    continue
                target = (path.parent / unquote(parsed.path)).resolve()
                self.assertTrue(target.is_relative_to(ROOT), (path, link))
                self.assertTrue(target.exists(), (path, link))
                self.assertNotIn('research', target.relative_to(ROOT).parts, (path, link))


if __name__ == '__main__':
    unittest.main()
