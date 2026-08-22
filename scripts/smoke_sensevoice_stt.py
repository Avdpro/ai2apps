#!/usr/bin/env python3
"""Run the pinned SenseVoiceSmall checkpoint through the oMLX STT engine."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from omlx.engine.stt import STTEngine


async def transcribe(model: Path, audio: Path, language: str | None) -> dict:
    engine = STTEngine(str(model))
    await engine.start()
    try:
        return await engine.transcribe(str(audio), language=language)
    finally:
        await engine.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--language")
    args = parser.parse_args()
    result = asyncio.run(
        transcribe(
            args.model.expanduser().resolve(strict=True),
            args.audio.expanduser().resolve(strict=True),
            args.language,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
