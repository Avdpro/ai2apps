"""Development-only Studio integrations loaded from the fixed App Dev checkout."""

import os
from pathlib import Path


def comfyui_prototype_enabled():
    source = os.environ.get("AI2APPS_DEVELOPMENT_SOURCE_ROOT")
    checkout = Path(__file__).resolve().parents[2]
    return (
        os.environ.get("AI2APPS_INSTANCE_ID") == "app-dev"
        and os.environ.get("AI2APPS_ALLOW_DEVELOPMENT_RUNTIME") == "1"
        and bool(source)
        and Path(source).resolve() == checkout
        and (checkout / "ai2apps/experiments/comfyui_studio/__init__.py").is_file()
    )
