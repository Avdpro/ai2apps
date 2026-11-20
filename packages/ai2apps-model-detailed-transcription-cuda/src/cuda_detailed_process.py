"""Cancellation-aware isolated stage launcher for incompatible official dependencies.

Interpreter and checkpoint paths are trusted Host configuration, never payload values.
No inference libraries are imported in the coordinating process.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import threading


class DetailedCancelled(RuntimeError):
    pass


class DetailedStageProcess:
    def __init__(self, qwen_python: Path, nemo_python: Path, *, script: Path | None = None):
        self.interpreters = {'qwen': Path(qwen_python), 'sortformer': Path(nemo_python)}
        self.script = script or Path(__file__).with_name('cuda_detailed_stage.py')
        self.runtime_commands = None

    @classmethod
    def from_runtime(cls, runtime_root: Path, python: Path, service_id: str):
        from ai2apps.model_worker.runtime_profiles import (
            framework_profile_for_stage, framework_stage_entrypoint,
        )
        root = runtime_root.resolve(strict=True)
        executable = python.resolve(strict=True)
        launcher = (root/'app/ai2apps/model_worker/stage_launcher.py').resolve(strict=True)
        if not executable.is_relative_to(root) or not launcher.is_relative_to(root):
            raise RuntimeError('Detailed stage executable must belong to Runtime')
        instance = cls(executable, executable)
        instance.runtime_commands = {}
        for stage in ('qwen', 'sortformer'):
            framework_profile_for_stage(root, service_id, stage)
            framework_stage_entrypoint(root, service_id, stage)
            instance.runtime_commands[stage] = [str(executable), '-I', str(launcher),
                '--service-id', service_id, '--stage', stage]
        return instance

    @staticmethod
    def _terminate(process):
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()

    def run(self, job: dict, cancelled: threading.Event) -> dict:
        if cancelled.is_set():
            raise DetailedCancelled('Detailed transcription cancelled')
        interpreter = self.interpreters[job['stage']]
        with tempfile.TemporaryDirectory(prefix='cuda-detailed-') as directory:
            root = Path(directory)
            request, result = root/'job.json', root/'result.json'
            request.write_text(json.dumps(job, allow_nan=False))
            environment = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
            # Prevent an inherited import path from mixing the two profiles.
            environment.pop('PYTHONPATH', None)
            with (root/'stage.log').open('w+b') as log:
                command = (self.runtime_commands[job['stage']] if self.runtime_commands
                           else [str(interpreter), str(self.script)])
                process = subprocess.Popen([*command, '--job',
                    str(request), '--result', str(result)], env=environment,
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    while process.poll() is None:
                        if cancelled.wait(.05):
                            raise DetailedCancelled('Detailed transcription cancelled')
                    if cancelled.is_set():
                        raise DetailedCancelled('Detailed transcription cancelled')
                    if process.returncode:
                        log.seek(0, 2); log.seek(max(0, log.tell()-8000))
                        raise RuntimeError('Detailed stage failed: '+log.read().decode(errors='replace'))
                    output = json.loads(result.read_text())
                    if not isinstance(output, dict):
                        raise ValueError('Invalid detailed stage result')
                    return output
                finally:
                    self._terminate(process)
