import asyncio

import pytest

from ai2apps.model_installer import (
    AI2AppsInstaller,
    InstallTask,
    _set_checkpoint_install_stage,
)


def test_checkpoint_post_transfer_stage_clears_stale_byte_progress() -> None:
    task = InstallTask(
        "task", "model", "huggingface", "owner/model", "a" * 40
    )
    task.progress_stage = "verifying_checkpoint"
    task.current_file = "vocab.json"
    task.bytes_completed = 10
    task.bytes_total = 10
    task.total_bytes_completed = 100
    task.total_bytes_total = 100

    _set_checkpoint_install_stage(
        task,
        stage="activating_checkpoint",
        phase="Starting local model service",
        progress=97.0,
    )

    assert task.progress_stage == "activating_checkpoint"
    assert task.phase == "Starting local model service"
    assert task.progress == 97.0
    assert task.current_file == ""
    assert task.bytes_completed == task.bytes_total == 0
    assert task.total_bytes_completed == task.total_bytes_total == 0


@pytest.mark.asyncio
async def test_cancel_stops_active_distribution_runner(tmp_path):
    class FakeDownloader:
        model_dir = tmp_path / "models"

    installer = AI2AppsInstaller(FakeDownloader())
    task = InstallTask(
        "task",
        "provider/model",
        "huggingface",
        "owner/model",
        "a" * 40,
    )
    installer.tasks[task.task_id] = task
    started = asyncio.Event()

    async def active_distribution():
        started.set()
        await asyncio.Event().wait()

    runner = asyncio.create_task(active_distribution())
    installer._runners[task.task_id] = runner
    await started.wait()

    assert await installer.cancel(task.task_id) is True
    assert runner.cancelled()
    assert task.status.value == "cancelled"
