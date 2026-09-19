#!/usr/bin/env python3
"""Convert fixed upstream RVC training weights to safe MLX artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .checkpoint import export_training_checkpoint


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("generator", type=Path)
    parser.add_argument("discriminator", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            export_training_checkpoint(args.generator, args.discriminator, args.output),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
