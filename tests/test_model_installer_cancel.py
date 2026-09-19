import asyncio

import pytest

from ai2apps.model_installer import AI2AppsInstaller, InstallTask


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
