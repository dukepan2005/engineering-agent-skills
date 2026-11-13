#!/usr/bin/env python3
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'cleanup-build-artifacts.sh'

class CleanupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='matpace-cleanup-test-', dir='/private/tmp')
        self.root = Path(self.temp.name).resolve()
        self.workspace = self.root / 'workspace'
        self.target = self.workspace / 'matpace-api/bin/matpace-api'
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(b'test')
        (self.workspace / 'matpace-api/go.mod').write_text('module example\n')
        (self.workspace / 'matpace-ios/.derived_data/Build').mkdir(parents=True)
        bins = self.root / 'bin'; bins.mkdir()
        for name, contents in {
            'go': '''#!/bin/sh
case "$1 $2" in
 'env GOCACHE') printf '%s\\n' "$HOME/Library/Caches/go-build" ;;
 'env GOMODCACHE') printf '%s\\n' "$HOME/go/pkg/mod" ;;
 'env GOTMPDIR') printf '\\n' ;;
 *) exit 1 ;;
esac
''',
            'ps': '#!/bin/sh\nprintf "42 /usr/bin/idle idle\\n"\n',
            'lsof': '#!/bin/sh\nexit 1\n',
        }.items():
            path = bins / name; path.write_text(contents); path.chmod(0o755)
        self.env = os.environ.copy(); self.env['PATH'] = str(bins) + os.pathsep + self.env['PATH']

    def tearDown(self):
        self.temp.cleanup()

    def run_cleanup(self, *args):
        return subprocess.run(['bash', str(SCRIPT), '--root', str(self.workspace), *args], env=self.env, text=True, capture_output=True)

    def preview_token(self):
        result = self.run_cleanup('--target', 'matpace-api/bin/matpace-api')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(self.target), result.stdout)
        return self.approval_token(result)

    @staticmethod
    def approval_token(result):
        return re.search(r'^Approval token: (\S+)$', result.stdout, re.MULTILINE).group(1)

    def test_mixed_targets_refresh_only_changed_path(self):
        scratch = self.root / 'scratch result'
        scratch.mkdir()
        (scratch / 'log').write_bytes(b'old')
        changed = self.workspace / 'build output'
        changed.mkdir()
        (changed / 'log').write_bytes(b'old')
        unrelated = self.root / 'unrelated'
        unrelated.touch()
        args = ('--target', 'build output', '--temp-target', str(scratch))
        preview = self.run_cleanup(*args)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn(str(changed), preview.stdout)
        self.assertIn(str(scratch), preview.stdout)
        token = self.approval_token(preview)
        (changed / 'log').write_bytes(b'new')

        result = self.run_cleanup(*args, '--apply', '--approval-token', token)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(scratch.exists())
        self.assertTrue(changed.exists())
        self.assertTrue(unrelated.exists())
        refresh = result.stdout.split('Cleanup inventory (', 1)[1]
        self.assertIn(str(changed), refresh)
        self.assertNotIn(str(scratch), refresh)
        retry = self.run_cleanup('--target', 'build output', '--apply',
                                 '--approval-token', self.approval_token(result))
        self.assertEqual(retry.returncode, 0, retry.stderr)
        self.assertFalse(changed.exists())

    def test_temp_target_rejects_roots_traversal_and_symlink_parents(self):
        link = self.root / 'redirect'
        link.symlink_to(self.target.parent, target_is_directory=True)
        for target in ('/private/tmp', '/Users', str(self.root / '..' / 'elsewhere'), str(link / self.target.name)):
            with self.subTest(target=target):
                result = self.run_cleanup('--temp-target', target)
                self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.target.exists())

    def test_same_size_replacement_is_held(self):
        token = self.preview_token()
        original = self.target.with_name('original')
        self.target.rename(original)
        self.target.write_bytes(b'test')
        result = self.run_cleanup('--target', 'matpace-api/bin/matpace-api', '--apply', '--approval-token', token)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.target.exists())
        self.assertTrue(original.exists())

    def test_original_approval_cannot_add_a_target(self):
        token = self.preview_token()
        scratch = self.root / 'unapproved'
        scratch.touch()
        result = self.run_cleanup('--target', 'matpace-api/bin/matpace-api',
                                  '--temp-target', str(scratch), '--apply', '--approval-token', token)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(scratch.exists())
        self.assertTrue(self.target.exists())

    def test_matpace_default_preview_preserves_global_go_cache(self):
        result = self.run_cleanup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(self.target), result.stdout)
        self.assertIn(str(self.workspace / 'matpace-ios/.derived_data/Build'), result.stdout)
        self.assertIn('preserved global Go build/test cache:', result.stdout)
        self.assertTrue(self.target.exists())

    def test_explicit_global_cache_option_changes_preview_token(self):
        default = self.run_cleanup()
        opted_in = self.run_cleanup('--include-go-cache')
        self.assertEqual(default.returncode, 0, default.stderr)
        self.assertEqual(opted_in.returncode, 0, opted_in.stderr)
        self.assertIn('preserved global Go build/test cache:', default.stdout)
        self.assertNotIn('preserved global Go build/test cache:', opted_in.stdout)
        token = lambda result: re.search(r'Approval token: ([a-f0-9]{64})', result.stdout).group(1)
        self.assertNotEqual(token(default), token(opted_in))
        self.assertTrue(self.target.exists())

    def test_missing_explicit_target_has_empty_inventory(self):
        result = self.run_cleanup('--target', 'matpace-api/bin/missing')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('none', result.stdout)
        self.assertNotIn('unknown', result.stdout)

    def test_explicit_target_without_preserve_can_apply(self):
        token = self.preview_token()
        result = self.run_cleanup('--target', 'matpace-api/bin/matpace-api', '--apply', '--approval-token', token)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.target.exists())
        self.assertTrue((self.workspace / 'matpace-api/go.mod').exists())

    def test_changed_inventory_is_not_deleted(self):
        token = self.preview_token(); self.target.write_bytes(b'x' * 8192)
        result = self.run_cleanup('--target', 'matpace-api/bin/matpace-api', '--apply', '--approval-token', token)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.target.exists())

    def test_failed_process_inspection_leaves_target_intact(self):
        token = self.preview_token()
        lsof = self.root / 'bin/lsof'; lsof.write_text('#!/bin/sh\nexit 2\n'); lsof.chmod(0o755)
        result = self.run_cleanup('--target', 'matpace-api/bin/matpace-api', '--apply', '--approval-token', token)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('cannot inspect', result.stderr)
        self.assertTrue(self.target.exists())

    def test_preserved_path_overlap_is_rejected(self):
        result = self.run_cleanup('--target', 'matpace-api/bin', '--preserve', 'matpace-api/bin/matpace-api')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('overlaps preserved path', result.stderr)
        self.assertTrue(self.target.exists())

if __name__ == '__main__':
    unittest.main()
