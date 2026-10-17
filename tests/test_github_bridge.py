import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import github_bridge as gh


class GitHubBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache_patch = patch.object(gh, 'CACHE', Path(self.tmp.name) / 'github-cache.json')
        self.cache_patch.start()
        gh._LAST_ERROR = None

    def tearDown(self):
        self.cache_patch.stop()
        self.tmp.cleanup()

    def test_sanitizes_urls_and_allowlists_metadata(self):
        repo = gh.normalize_repo({'id': 42, 'full_name': 'tester/demo', 'html_url': 'https://github.com/tester/demo',
                                  'homepage': 'javascript:alert(1)', 'token': 'secret', 'password': 'secret',
                                  'owner': {'avatar_url': 'https://user:secret@example.com/icon', 'token': 'secret'}})
        self.assertEqual(repo['homepage'], '')
        self.assertEqual(repo['avatarUrl'], '')
        self.assertEqual(repo['htmlUrl'], 'https://github.com/tester/demo')
        self.assertNotIn('secret', json.dumps(repo))
        self.assertEqual(gh.safe_url('https://demo.example.com'), 'https://demo.example.com')
        self.assertEqual(gh.safe_url('file:///etc/passwd'), '')
        self.assertEqual(gh.safe_url('https://evil.example.com/repo', github=True), '')

    def test_fixed_cli_argv_paginated_sync_and_cache(self):
        results = [SimpleNamespace(returncode=0, stdout=json.dumps({'login': 'tester', 'token': 'secret'}), stderr=''),
                   SimpleNamespace(returncode=0, stdout=json.dumps([{'id': 42, 'full_name': 'tester/demo', 'private': True,
                       'html_url': 'https://github.com/tester/demo', 'homepage': 'https://demo.example.com', 'token': 'secret'}]), stderr='')]
        with patch.object(gh.shutil, 'which', return_value='/usr/bin/gh'), patch.object(gh.subprocess, 'run', side_effect=results) as run:
            result = gh.sync()
            self.assertTrue(result['connected'])
            self.assertTrue(result['repos'][0]['private'])
            self.assertEqual(run.call_args_list[0].args[0], ['/usr/bin/gh', 'api', '--hostname', 'github.com', 'user'])
            self.assertEqual(run.call_args_list[1].args[0], ['/usr/bin/gh', 'api', '--hostname', 'github.com', 'user/repos?affiliation=owner&sort=updated&per_page=100&page=1'])
            self.assertNotIn('secret', gh.CACHE.read_text())
            self.assertEqual(gh.CACHE.stat().st_mode & 0o777, 0o600)
        with patch.object(gh.subprocess, 'run') as run:
            self.assertEqual(gh.status()['login'], 'tester')
            run.assert_not_called()

    def test_error_preserves_cache_without_echoing_cli_secrets(self):
        gh.atomic(gh.CACHE, {'login': 'tester', 'repos': [{'fullName': 'tester/demo'}], 'syncedAt': 'previous'})
        for diagnostic, code in [('HTTP 401 bad credentials secret-token', 'auth'), ('connection refused secret-token', 'network')]:
            with patch.object(gh.shutil, 'which', return_value='/usr/bin/gh'), patch.object(gh.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stdout='secret-token', stderr=diagnostic)):
                result = gh.sync()
            self.assertFalse(result['connected'])
            self.assertTrue(result['cached'])
            self.assertEqual(len(result['repos']), 1)
            self.assertEqual(result['errorCode'], code)
            self.assertNotIn('secret-token', json.dumps(result))
        self.assertEqual(json.loads(gh.CACHE.read_text())['syncedAt'], 'previous')

    def test_repository_page_cap(self):
        page = [{'full_name': f'tester/demo-{i}'} for i in range(100)]
        with patch.object(gh, 'MAX_PAGES', 2), patch.object(gh.shutil, 'which', return_value='/usr/bin/gh'), patch.object(gh, '_api', side_effect=[{'login': 'tester'}, page, page]) as api:
            result = gh.sync()
        self.assertTrue(result['truncated'])
        self.assertEqual(api.call_count, 3)
        self.assertEqual(len(result['repos']), 100)

    def test_missing_cli_actionable(self):
        with patch.object(gh.shutil, 'which', return_value=None):
            result = gh.sync()
        self.assertFalse(result['available'])
        self.assertEqual(result['errorCode'], 'unavailable')
        self.assertIn('gh auth login', result['error'])


if __name__ == '__main__':
    unittest.main()
