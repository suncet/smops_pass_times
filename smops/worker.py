"""Local queue processor; retries failed pushes without discarding the email."""
import fcntl
import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .parser import ScheduleError, parse_message
from .render import render

LOG = logging.getLogger('smops')


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True,
                          text=True, capture_output=True, timeout=90,
                          env=dict(os.environ, GIT_TERMINAL_PROMPT='0'))


def newer(candidate, current):
    if current is None:
        return True
    return candidate['message_at'] > current['message_at']


def write_status(state, **values):
    values['checked_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    temporary = state / 'status.json.tmp'
    temporary.write_text(json.dumps(values, indent=2) + '\n', encoding='utf-8')
    temporary.replace(state / 'status.json')


def process_queue(repo, state):
    repo, state = Path(repo).resolve(), Path(state).resolve()
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ('queue', 'processed', 'rejected'):
        (state / name).mkdir(exist_ok=True, mode=0o700)
    with (state / 'worker.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        try:
            _process(repo, state)
        except Exception as error:
            # Avoid logging email contents or Git's potentially sensitive stderr.
            LOG.error('Update failed (%s); queued messages retained for retry.', type(error).__name__)
            write_status(state, ok=False, error_type=type(error).__name__,
                         action='Check network, Git credentials, and publisher checkout; queued messages will retry.')
            raise


def _process(repo, state):
    files = sorted((state / 'queue').glob('*.eml'))
    if not files:
        return
    # Recover any commit whose previous push failed before reading new data.
    git(repo, 'push', 'origin', 'HEAD:main')
    git(repo, 'pull', '--ff-only', 'origin', 'main')
    if git(repo, 'status', '--porcelain').stdout.strip():
        # Only generated docs may remain dirty following an interrupted run.
        changed = git(repo, 'diff', '--name-only', 'HEAD').stdout.splitlines()
        if any(not path.startswith('docs/') for path in changed):
            raise RuntimeError('Publisher has unexpected local changes.')
    current_path = repo / 'docs/schedule.json'
    current = json.loads(current_path.read_text()) if current_path.exists() else None
    selected, accepted, rejected = current, [], []
    for path in files:
        try:
            candidate = parse_message(path.read_bytes())
        except (ScheduleError, UnicodeError, ValueError) as error:
            LOG.error('Rejected %s: %s', path.name, str(error))
            path.replace(state / 'rejected' / path.name)
            rejected.append(path.name)
            continue
        accepted.append(path)
        if newer(candidate, selected):
            selected = candidate
    if selected is not current:
        render(selected, repo / 'docs')
    # Explicit path list keeps raw mail and local state out of Git commits.
    public = ['docs/index.html', 'docs/schedule.json', 'docs/passes.csv',
              'docs/style.css', 'docs/app.js', 'docs/.nojekyll']
    git(repo, 'add', '--', *public)
    if git(repo, 'diff', '--cached', '--name-only').stdout.strip():
        git(repo, 'commit', '-m', 'Update public SMOPS pass schedule')
    git(repo, 'push', 'origin', 'HEAD:main')
    for path in accepted:
        path.replace(state / 'processed' / path.name)
    write_status(state, ok=not rejected, published_message_at=selected['message_at'] if selected else None,
                 processed=len(accepted), rejected=rejected)
    LOG.info('Processed %d messages; rejected %d.', len(accepted), len(rejected))
