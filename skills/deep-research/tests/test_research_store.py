"""Offline project storage and future-agent reuse contracts."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_research_session import brief, dossier, session


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.patcher = patch.object(session, 'collect_state', return_value={})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def prepare(self, project=None):
        return session.prepare(brief(), project or self.project)

    def fill(self, root):
        data = dossier(root / 'raw')
        data['evidence'][0]['artifact'] = 'raw/raw.md'
        session.write_json(root / 'processed/dossier.json', data)
        return data

    def index(self):
        return json.loads((self.project / 'research/index.json').read_text())

    def test_prepare_layout_and_draft_index(self):
        result = self.prepare()
        root = Path(result['run_dir'])
        self.assertEqual(Path(result['dossier']), root / 'processed/dossier.json')
        self.assertTrue(Path(result['raw_dir']).is_dir())
        self.assertTrue(Path(result['processed_dir']).is_dir())
        self.assertEqual(self.index()['runs'][0]['status'], 'draft')
        self.assertIsNone(self.index()['runs'][0]['agent_context'])

    def test_finalize_inventory_preserves_sources_and_agent_links(self):
        root = Path(self.prepare()['run_dir'])
        self.fill(root)
        source = root / 'raw/raw.md'
        before = source.read_bytes()
        session.finalize(root)
        self.assertEqual(source.read_bytes(), before)
        inventory = json.loads((root / 'artifacts.json').read_text())
        rows = {row['path']: row for row in inventory['files']}
        self.assertEqual(rows['raw/raw.md']['role'], 'raw')
        self.assertEqual(rows['raw/raw.md']['sha256'], hashlib.sha256(before).hexdigest())
        self.assertEqual(rows['processed/dossier.json']['role'], 'processed')
        self.assertEqual(rows['agent-context.json']['role'], 'final')
        item = self.index()['runs'][0]
        self.assertEqual(item['status'], 'partial')
        agent = json.loads((self.project / 'research' / item['agent_context']).read_text())
        for evidence in agent['evidence']:
            self.assertTrue((root / evidence['artifact']).is_file())
        self.assertIn('agent-context.json', (self.project / 'research/INDEX.md').read_text())

    def test_two_projects_and_repeated_runs_are_isolated(self):
        first = Path(self.prepare()['run_dir'])
        second = Path(self.prepare()['run_dir'])
        other = self.project / 'other'; other.mkdir()
        self.prepare(other)
        self.assertNotEqual(first, second)
        self.assertEqual(len(self.index()['runs']), 2)
        self.assertEqual(len(json.loads((other / 'research/index.json').read_text())['runs']), 1)
        for row in self.index()['runs']:
            self.assertEqual(Path(row['path']).parts, (Path(row['path']).name,))

    def test_user_index_conflict_does_not_allocate_or_overwrite(self):
        folder = self.project / 'research'; folder.mkdir()
        (folder / 'INDEX.md').write_text('My own research notes')
        with self.assertRaisesRegex(ValueError, 'owned|overwrite|conflict'):
            self.prepare()
        self.assertEqual((folder / 'INDEX.md').read_text(), 'My own research notes')
        self.assertEqual(len(list(folder.iterdir())), 1)

    def test_symlinked_research_root_rejected(self):
        external = self.project / 'external'; external.mkdir()
        (self.project / 'research').symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.prepare()
        self.assertEqual(list(external.iterdir()), [])

    def test_symlinked_run_not_indexed_or_followed(self):
        self.prepare()
        outside = self.project / 'outside'; outside.mkdir()
        session.write_json(outside / 'research-brief.json', brief())
        (self.project / 'research/deep-research-link').symlink_to(outside, target_is_directory=True)
        session.rebuild_index(self.project)
        self.assertEqual(len(self.index()['runs']), 1)

    def test_new_layout_rejects_flat_and_self_referential_evidence(self):
        root = Path(self.prepare()['run_dir'])
        data = dossier(root)
        with self.assertRaisesRegex(ValueError, 'raw/|processed/'):
            session.finalize(root, data)
        data['evidence'][0]['artifact'] = 'processed/dossier.json'
        session.write_json(root / 'processed/dossier.json', data)
        with self.assertRaisesRegex(ValueError, 'dossier|support'):
            session.finalize(root, data)

    def test_broken_export_and_changed_dossier_are_not_ready(self):
        root = Path(self.prepare()['run_dir'])
        data = self.fill(root)
        session.finalize(root)
        (root / 'playbook.html').write_text('Interrupted export')
        session.rebuild_index(self.project)
        self.assertEqual(self.index()['runs'][0]['status'], 'incomplete')
        self.assertIsNone(self.index()['runs'][0]['agent_context'])
        session.finalize(root)
        data['summary'] = 'Changed since export'
        session.write_json(root / 'processed/dossier.json', data)
        session.rebuild_index(self.project)
        self.assertEqual(self.index()['runs'][0]['status'], 'incomplete')

    def test_legacy_flat_run_is_finalized_without_migration(self):
        root = self.project / 'research/deep-research-legacy'; root.mkdir(parents=True)
        session.write_json(root / 'research-brief.json', brief())
        session.write_json(root / 'dossier.json', dossier(root))
        session.finalize(root)
        self.assertFalse((root / 'processed').exists())
        self.assertEqual((root / 'raw.md').read_text(), 'Original source')
        self.assertEqual(self.index()['runs'][0]['status'], 'partial')

    def test_symlinked_artifact_inside_run_is_refused(self):
        root = Path(self.prepare()['run_dir'])
        data = self.fill(root)
        (root / 'raw/alias.md').symlink_to(root / 'raw/raw.md')
        data['evidence'][0]['artifact'] = 'raw/alias.md'
        with self.assertRaisesRegex(ValueError, 'symlink'):
            session.finalize(root, data)

    def test_changed_source_invalidates_inventory_until_reviewed_export(self):
        root = Path(self.prepare()['run_dir'])
        self.fill(root)
        session.finalize(root)
        (root / 'raw/raw.md').write_text('Source changed after export')
        session.rebuild_index(self.project)
        self.assertEqual(self.index()['runs'][0]['status'], 'incomplete')
        self.assertIsNone(self.index()['runs'][0]['playbook'])

    def test_symlinked_index_cannot_touch_other_project(self):
        folder = self.project / 'research'; folder.mkdir()
        target = self.project / 'private.txt'; target.write_text('Keep me')
        (folder / 'INDEX.md').symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.prepare()
        self.assertEqual(target.read_text(), 'Keep me')

    def test_locked_index_fails_closed_and_can_be_rebuilt(self):
        self.prepare()
        folder = self.project / 'research'
        old = (folder / 'index.json').read_bytes()
        (folder / '.index.lock').write_text('12345')
        with self.assertRaisesRegex(ValueError, 'locked'):
            session.rebuild_index(self.project)
        self.assertEqual(old, (folder / 'index.json').read_bytes())
        (folder / '.index.lock').unlink()
        self.assertEqual(session.rebuild_index(self.project)['runs'], 1)

    def test_malformed_neighbor_does_not_break_valid_runs(self):
        self.prepare()
        invalid = self.project / 'research/deep-research-invalid'; invalid.mkdir()
        (invalid / 'research-brief.json').write_text('not JSON')
        session.rebuild_index(self.project)
        self.assertEqual({row['status'] for row in self.index()['runs']}, {'draft', 'incomplete'})

    def test_source_title_cannot_inject_markdown_or_html(self):
        data = brief(); data['goal'] = '[click](https://evil.example/) <script>alert(1)</script>'
        session.prepare(data, self.project)
        text = (self.project / 'research/INDEX.md').read_text()
        self.assertNotIn('<script>', text)
        self.assertNotIn('[click](https://evil.example/)', text)

    def test_finalize_index_conflict_preserves_existing_pair(self):
        root = Path(self.prepare()['run_dir'])
        data = self.fill(root)
        session.finalize(root)
        before = (root / 'agent-context.json').read_bytes()
        (self.project / 'research/INDEX.md').write_text('User notes')
        data['summary'] = 'Changed'
        with self.assertRaisesRegex(ValueError, 'conflict'):
            session.finalize(root, data)
        self.assertEqual((root / 'agent-context.json').read_bytes(), before)

    def test_index_failure_returns_committed_run_instead_of_losing_it(self):
        first = self.prepare()
        lock = self.project / 'research/.index.lock'; lock.write_text('busy')
        result = self.prepare()
        self.assertNotEqual(first['run_dir'], result['run_dir'])
        self.assertIn('locked', result['index_error'])
        self.assertIsNone(result['project_index'])
        root = Path(result['run_dir']); self.fill(root)
        exported = session.finalize(root)
        self.assertIn('locked', exported['index_error'])
        self.assertTrue(Path(exported['playbook']).is_file())
        lock.unlink()
        session.rebuild_index(self.project)
        self.assertEqual({row['status'] for row in self.index()['runs']}, {'draft', 'partial'})

    def test_active_session_not_presented_as_reusable(self):
        root = Path(self.prepare()['run_dir']); self.fill(root); session.finalize(root)
        (root / '.session.lock').write_text('busy')
        session.rebuild_index(self.project)
        self.assertEqual(self.index()['runs'][0]['status'], 'incomplete')

    def test_legacy_dossier_cannot_be_its_own_source(self):
        data = dossier(self.project)
        data['evidence'][0]['artifact'] = 'dossier.json'
        session.write_json(self.project / 'dossier.json', data)
        session.write_json(self.project / 'research-brief.json', brief())
        with self.assertRaisesRegex(ValueError, 'supporting artifact'):
            session.finalize(self.project)

    def test_cli_prepare_finalize_index_and_second_project_reuse(self):
        script = Path(session.__file__)
        def call(*args):
            completed = subprocess.run([sys.executable, str(script), *args],
                                       capture_output=True, text=True, timeout=20,
                                       cwd=self.project)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            return json.loads(completed.stdout)
        brief_file = self.project / 'brief.json'
        session.write_json(brief_file, brief())
        prepared = call('prepare', '--brief', str(brief_file), '--project-root', str(self.project))
        root = Path(prepared['run_dir']); self.fill(root)
        exported = call('finalize', '--run-dir', str(root))
        self.assertEqual(exported['status'], 'partial')
        self.assertEqual(call('index', '--project-root', str(self.project))['runs'], 1)
        self.assertEqual(self.index()['runs'][0]['agent_context'], root.name + '/agent-context.json')
        other = self.project / 'second'; other.mkdir()
        self.assertEqual(call('index', '--project-root', str(other))['runs'], 0)


if __name__ == '__main__':
    unittest.main()
