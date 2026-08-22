from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_cloud_server_import_does_not_load_mlx() -> None:
    script = r"""
import builtins

real_import = builtins.__import__

def reject_mlx(name, *args, **kwargs):
    if name == "mlx" or name.startswith("mlx.") or name.startswith("mlx_"):
        raise ModuleNotFoundError("MLX import attempted by cloud Runtime", name=name)
    return real_import(name, *args, **kwargs)

builtins.__import__ = reject_mlx
import omlx.server

assert omlx.server._CLOUD_RUNTIME_PROFILE is True
assert omlx.server._server_state.engine_pool is None
"""
    environment = dict(os.environ)
    environment["AI2APPS_RUNTIME_PROFILE"] = "cloud"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=environment,
        check=True,
    )


def test_cloud_engine_pool_reports_no_in_process_models() -> None:
    from omlx.cloud_engine_pool import CloudEnginePool

    pool = CloudEnginePool()
    assert pool.model_count == 0
    assert pool.loaded_model_count == 0
    assert pool.current_model_memory == 0
    assert pool.get_model_ids() == []
    assert pool.get_status()["runtime_profile"] == "cloud"
    assert pool.get_status()["local_inference"] is False
