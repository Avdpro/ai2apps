"""Where checkpoints come from: a local directory or the Hugging Face Hub."""

from __future__ import annotations

from pathlib import Path

DEFAULT_REPO = "higurashi-ai/Haru-4B"
_FILES = ("config.json", "model.safetensors", "tokenizer.json")


def resolve_checkpoint(path_or_repo: str = DEFAULT_REPO, revision: str | None = None) -> Path:
    """Directory holding ``config.json``, ``model.safetensors`` and ``tokenizer.json``."""
    path = Path(path_or_repo).expanduser()
    if path.is_dir():
        return path
    from huggingface_hub import snapshot_download

    return Path(snapshot_download(path_or_repo, revision=revision, allow_patterns=list(_FILES)))
