"""Explicit, local-only GitHub sync via the user's authenticated gh CLI.

Only an allowlisted metadata snapshot is persisted; credentials and raw CLI
output never reach the browser. Repositories are source projects, not launches.
"""
import json
import re
import shutil
import subprocess
import threading
from urllib.parse import urlparse
from registry import DATA, atomic, now

CACHE = DATA / 'github-cache.json'
LOCK = threading.RLock()
MAX_PAGES = 10


def safe_url(value, github=False):
    if not isinstance(value, str):
        return ''
    try:
        parsed = urlparse(value)
        if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password:
            return ''
        if github and (parsed.scheme != 'https' or parsed.hostname != 'github.com'):
            return ''
        return value[:2048]
    except ValueError:
        return ''


def normalize_repo(repo):
    """Discard arbitrary API/cache fields, including tokens or credentials."""
    if not isinstance(repo, dict):
        raise ValueError('Invalid repository metadata')
    full_name = repo.get('full_name', repo.get('fullName', ''))
    if not isinstance(full_name, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', full_name):
        raise ValueError('Invalid repository name')
    def string(key, limit=4000):
        value = repo.get(key)
        return value[:limit] if isinstance(value, str) else ''
    owner = repo.get('owner', {})
    return {
        'id': str(repo.get('id', ''))[:40], 'fullName': full_name,
        'name': full_name.split('/', 1)[1], 'description': string('description'),
        'htmlUrl': safe_url(repo.get('html_url', repo.get('htmlUrl')), github=True),
        'homepage': safe_url(repo.get('homepage')),
        'language': string('language', 80),
        'stars': max(0, repo.get('stargazers_count', repo.get('stars', 0))) if isinstance(repo.get('stargazers_count', repo.get('stars', 0)), int) else 0,
        'private': bool(repo.get('private')), 'archived': bool(repo.get('archived')),
        'fork': bool(repo.get('fork')),
        'updatedAt': string('updated_at', 80) or string('updatedAt', 80),
        'avatarUrl': safe_url(owner.get('avatar_url', '') if isinstance(owner, dict) and owner else repo.get('avatarUrl', '')),
    }


def _load():
    try:
        data = json.loads(CACHE.read_text())
        login = data.get('login', '')
        if not isinstance(login, str) or not re.fullmatch(r'[A-Za-z0-9-]{1,39}', login):
            return {}
        return {'login': login, 'repos': [normalize_repo(r) for r in data.get('repos', [])[:MAX_PAGES * 100]],
                'syncedAt': str(data.get('syncedAt', ''))[:80], 'truncated': bool(data.get('truncated'))}
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


class SyncError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message


def _api(binary, endpoint):
    try:
        result = subprocess.run([binary, 'api', '--hostname', 'github.com', endpoint], capture_output=True, text=True, timeout=20)
    except subprocess.TimeoutExpired:
        raise SyncError('network', 'GitHub timed out. Check your connection and try Sync again.')
    except OSError:
        raise SyncError('unavailable', 'GitHub CLI is unavailable. Install gh, then run gh auth login.')
    if result.returncode:
        # Inspect errors for classification, but never echo raw stderr or stdout.
        diagnostic = result.stderr.lower()
        if any(marker in diagnostic for marker in ('http 401', 'http 403', 'authentication', 'gh auth login', 'bad credentials', 'not logged')):
            raise SyncError('auth', 'GitHub sign-in needs attention. Run gh auth login in Terminal, then Sync again.')
        raise SyncError('network', 'GitHub could not be reached. Check your connection and try Sync again.')
    try:
        return json.loads(result.stdout)
    except ValueError:
        raise SyncError('response', 'GitHub returned an unexpected response. Try Sync again.')


_LAST_ERROR = None


def status():
    """Read cached metadata only; this never triggers network or login."""
    with LOCK:
        cached = _load()
        result = {'available': bool(shutil.which('gh')), 'connected': bool(cached) and _LAST_ERROR is None,
                  'login': cached.get('login', ''), 'repos': cached.get('repos', []),
                  'syncedAt': cached.get('syncedAt'), 'cached': bool(cached),
                  'truncated': cached.get('truncated', False)}
        if _LAST_ERROR:
            result.update(error=_LAST_ERROR.message, errorCode=_LAST_ERROR.code)
        return result


def sync():
    """Fetch owned repositories only after an explicit browser sync request."""
    global _LAST_ERROR
    with LOCK:
        binary = shutil.which('gh')
        try:
            if not binary:
                raise SyncError('unavailable', 'Install GitHub CLI (gh), run gh auth login in Terminal, then Sync again.')
            user = _api(binary, 'user')
            login = user.get('login', '') if isinstance(user, dict) else ''
            if not isinstance(login, str) or not re.fullmatch(r'[A-Za-z0-9-]{1,39}', login):
                raise SyncError('response', 'GitHub returned an unexpected account. Try Sync again.')
            repos = {}
            truncated = False
            for page in range(1, MAX_PAGES + 1):
                batch = _api(binary, f'user/repos?affiliation=owner&sort=updated&per_page=100&page={page}')
                if not isinstance(batch, list):
                    raise SyncError('response', 'GitHub returned unexpected repositories. Try Sync again.')
                for raw in batch[:100]:
                    try:
                        repo = normalize_repo(raw)
                    except ValueError:
                        continue
                    repos[repo['fullName']] = repo
                if len(batch) < 100:
                    break
                if page == MAX_PAGES:
                    truncated = True
            snapshot = {'login': login, 'repos': list(repos.values()), 'syncedAt': now(), 'truncated': truncated}
            atomic(CACHE, snapshot)
            CACHE.chmod(0o600)
            _LAST_ERROR = None
        except SyncError as error:
            _LAST_ERROR = error
        return status()
