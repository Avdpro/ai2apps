"""Fixed prompt selection without importing the GPU runtime."""

import hashlib
import json
from pathlib import Path

DEFAULT_PROMPT = "A high quality video with natural details and consistent motion."


def fixed_context(root, prompt):
    root = Path(root)
    metadata = root / "context-metadata.json"
    if not metadata.is_file():
        return None  # Original upstream snapshots remain usable for regression tests.
    info = json.loads(metadata.read_text())
    if prompt != info.get("prompt"):
        if (root / "text_encoder/config.json").is_file() and (
            root / "connectors/config.json"
        ).is_file():
            return None
        raise ValueError(
            "Custom prompts need the Custom Prompt option in Discover. "
            "Install its additional text components, or clear the prompt "
            "to use Standard Upscaling."
        )
    path = root / "default-prompt-context.safetensors"
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != info.get(
        "sha256"
    ):
        raise ValueError(
            "The default upscaling data is missing or damaged. "
            "Repair this model in Discover."
        )
    return path
