"""Run-scoped human checkpoint. The runner alone advances the Pipeline."""
import fcntl
import subprocess
import time
import uuid
from contextlib import contextmanager

from .state import atomic_write_json, read_json


@contextmanager
def locked(run_dir):
    with (run_dir / '.human-action.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def current(run_dir):
    path = run_dir / 'human-action.json'
    return read_json(path) if path.exists() else None


def submit(run_dir, payload):
    with locked(run_dir):
        value = current(run_dir)
        state = read_json(run_dir / 'state.json')
        if (not value or payload.get('id') != value['id'] or
                state['status'] in {'completed', 'cancelled', 'cancelling'} or
                state.get('currentCaseId') != value['caseId']):
            raise ValueError('This human step is no longer active')
        action = payload.get('action')
        if value['phase'] == 'waiting' and time.time() >= value['deadline']:
            raise ValueError('Confirmation timed out')
        if action == 'mute' and value['phase'] == 'waiting':
            value['muted'] = True
        elif action == 'start' and value['phase'] == 'waiting':
            value.update(phase='active', confirmedAt=time.time())
        elif action in {'skipped', 'passed', 'blocked', 'failed'} and value['phase'] == 'active':
            reason = payload.get('reason', '')
            if not isinstance(reason, str) or len(reason) > 4000:
                raise ValueError('Reason must be text, at most 4000 characters')
            if action in {'blocked', 'failed'} and not reason.strip():
                raise ValueError('Block and Failed require a reason')
            value.update(phase='done', result=action, reason=reason.strip(), finishedAt=time.time())
        else:
            raise ValueError('Invalid human step transition')
        atomic_write_json(run_dir / 'human-action.json', value)
        return value


def execute(run_dir, case, is_cancelled):
    arrived = time.time()
    value = {'id': uuid.uuid4().hex, 'caseId': case['id'], 'phase': 'waiting',
             'instructions': case['humanInstructions'], 'arrivedAt': arrived,
             'deadline': arrived + case['confirmTimeoutSeconds'], 'muted': False}
    with locked(run_dir):
        atomic_write_json(run_dir / 'human-action.json', value)
    sound = None
    next_beep = 0
    try:
        while True:
            cancelled = is_cancelled() or read_json(run_dir / 'state.json')['status'] in {'cancelled', 'cancelling', 'completed'}
            with locked(run_dir):
                value = current(run_dir)
                if cancelled:
                    value.update(phase='done', result='skipped', reason='Run cancelled', finishedAt=time.time())
                elif value['phase'] == 'waiting' and time.time() >= value['deadline']:
                    value.update(phase='done', result='skipped', reason='Confirm Start 超时，用户未开始', finishedAt=time.time())
                atomic_write_json(run_dir / 'human-action.json', value)
            if value['phase'] == 'done':
                break
            if value['phase'] == 'waiting' and not value['muted'] and time.monotonic() >= next_beep:
                if sound is None or sound.poll() is not None:
                    try:
                        sound = subprocess.Popen(['/usr/bin/afplay', '/System/Library/Sounds/Ping.aiff'],
                                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except OSError:
                        pass  # Visible prompt remains available when audio is unavailable.
                next_beep = time.monotonic() + 3
            elif (value['phase'] != 'waiting' or value['muted']) and sound and sound.poll() is None:
                sound.terminate()
            time.sleep(0.2)
    finally:
        if sound and sound.poll() is None:
            sound.terminate()
        if sound:
            try:
                sound.wait(timeout=2)
            except subprocess.TimeoutExpired:
                sound.kill()
                sound.wait()
    evidence = 'human-' + value['id'] + '.json'
    atomic_write_json(run_dir / evidence, value)
    return {'status': value['result'], 'summary': value.get('reason') or '用户辅助测试：' + value['result'],
            'evidence': [evidence], 'details': {'source': 'human',
            'waitingSeconds': value.get('confirmedAt', value['finishedAt']) - arrived,
            'executionSeconds': value['finishedAt'] - value.get('confirmedAt', value['finishedAt'])}}
