"""Bounded Test-only system audio capture; no global mix fallback."""
from __future__ import annotations

import json
import fcntl
import re
import subprocess
import time
import uuid
from pathlib import Path

from .shell_target import test_shell_path
from .state import read_json


def native_binary() -> Path:
    source = Path(__file__).with_name('native_audio.swift')
    build = source.parents[2] / '.build' / 'audio-capture'
    binary = build / 'test-audio-capture'
    if not binary.exists() or binary.stat().st_mtime_ns < source.stat().st_mtime_ns:
        build.mkdir(parents=True, exist_ok=True)
        temporary = build / ('capture-' + uuid.uuid4().hex)
        subprocess.run(['xcrun', 'swiftc', '-parse-as-library', '-module-cache-path',
                        str(build / 'module-cache'), str(source), '-o', str(temporary)],
                       check=True, capture_output=True, timeout=90)
        temporary.replace(binary)
    return binary


def permission() -> dict:
    result = subprocess.run([str(native_binary()), 'permission'], capture_output=True,
                            text=True, timeout=30)
    return {'status': 'ready' if result.returncode == 0 else 'blocked',
            'permission': result.stdout.strip(),
            'guidance': 'macOS 系统设置 → 隐私与安全性 → 屏幕与系统音频录制；授权实际启动应用后重试。不会录制麦克风。'}


def capture_dir(run_dir: Path, capture_id: str) -> Path:
    if not re.fullmatch(r'[0-9a-f]{32}', capture_id):
        raise ValueError('Invalid capture ID')
    directory = run_dir / 'evidence' / 'audio' / capture_id
    if not directory.resolve().is_relative_to(run_dir.resolve()):
        raise ValueError('Audio evidence path escapes Run')
    return directory


def status(run_dir: Path, capture_id: str) -> dict:
    directory = capture_dir(run_dir, capture_id)
    value = read_json(directory / 'capture.json')
    evidence = [str((directory / 'capture.json').relative_to(run_dir))]
    if (directory / 'output.wav').is_file():
        evidence.append(str((directory / 'output.wav').relative_to(run_dir)))
    return {**value, 'captureId': capture_id, 'evidence': evidence}


def start(repo_root: Path, run_dir: Path, case_id: str, seconds: int = 120) -> dict:
    with (run_dir / '.audio-capture.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _start(repo_root, run_dir, case_id, seconds)


def _start(repo_root: Path, run_dir: Path, case_id: str, seconds: int) -> dict:
    if not 1 <= seconds <= 180:
        raise ValueError('Capture duration must be 1–180 seconds')
    state = read_json(run_dir / 'state.json')
    if state['status'] in {'completed', 'cancelled', 'cancelling'}:
        raise ValueError('Cannot capture for an ended Run')
    from .runner import next_agent_job
    job = next_agent_job(state)
    if not job or job['case']['id'] != case_id:
        raise ValueError('Capture requires the current pending UI Case')
    # Exclude concurrent captures within a Run; expired manifests require explicit inspection.
    for manifest in (run_dir / 'evidence' / 'audio').glob('*/capture.json'):
        if read_json(manifest).get('status') in {'starting', 'recording'}:
            raise ValueError('An audio capture is already active in this Run')
    target = test_shell_path(repo_root)
    binary = native_binary()
    capture_id = uuid.uuid4().hex
    directory = capture_dir(run_dir, capture_id)
    directory.mkdir(parents=True, exist_ok=False)
    # The native helper owns this directory and writes readiness only after startCapture succeeds.
    process = subprocess.Popen([str(binary), target, str(directory), str(run_dir / 'state.json'),
                                case_id, str(seconds)], stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               start_new_session=True)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if (directory / 'capture.json').exists():
            result = status(run_dir, capture_id)
            if result['status'] != 'starting':
                return result
        if process.poll() is not None:
            break
        time.sleep(0.1)
    (directory / 'stop').touch(exist_ok=False)
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    raise RuntimeError('Audio capture did not become ready; no playback should be started')


def stop(run_dir: Path, capture_id: str) -> dict:
    directory = capture_dir(run_dir, capture_id)
    result = status(run_dir, capture_id)
    if result['status'] not in {'recording', 'starting'}:
        return result
    (directory / 'stop').touch(exist_ok=True)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        result = status(run_dir, capture_id)
        if result['status'] not in {'recording', 'starting'}:
            return result
        time.sleep(0.1)
    raise RuntimeError('Capture stop not yet confirmed; do not transcribe an open file')
