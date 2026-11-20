"""Fetch pinned AVTR-1 assets using the user's existing Hugging Face authorization."""

import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from huggingface_hub import hf_hub_download

    manifest = json.loads(
        (Path(__file__).resolve().parents[1] / "checkpoint-assets.json").read_text()
    )
    for entry in manifest["assets"]:
        path = Path(
            hf_hub_download(
                entry["repo"],
                entry["path"],
                revision=entry["revision"],
                local_dir=args.output,
            )
        )
        with path.open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        if checksum != entry["sha256"]:
            raise ValueError("Asset checksum mismatch: " + entry["path"])
        print("Verified " + entry["path"])


if __name__ == "__main__":
    main()
