"""Explicit opt-in paths for heavyweight avatar reference tests."""

from pathlib import Path
import os
import subprocess
import sys
import json

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM_ROOT = Path(
    os.environ.get("AI2APPS_AVATAR_UPSTREAM", "/nonexistent/avatar-upstream")
)
CHECKPOINT_ROOT = Path(
    os.environ.get("AI2APPS_AVATAR_CHECKPOINTS", "/nonexistent/avatar-checkpoints")
)
for name in ("flashhead", "musetalk", "avtr1", "infinitetalk", "exomni"):
    sys.path.insert(0, str(ROOT / "packages" / f"ai2apps-model-{name}-mlx" / "src"))
lock = json.loads(
    (ROOT / "packages/ai2apps-model-flashhead-mlx/upstream-lock.json").read_text()
)
for name, source in lock["sources"].items():
    checkout = UPSTREAM_ROOT / name
    if not checkout.exists():
        continue
    commit = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    if commit != source["commit"]:
        raise RuntimeError(f"Reference source revision mismatch: {name}")
if (UPSTREAM_ROOT / "mlx-audio").exists():
    sys.path.insert(0, str(UPSTREAM_ROOT / "mlx-audio"))
