#!/usr/bin/env python3
"""Run the pinned Qwen3 TTS checkpoint through the oMLX TTS engine."""

from __future__ import annotations

import argparse
import asyncio
import json
import wave
from pathlib import Path

from omlx.engine.tts import TTSEngine


async def synthesize(model: Path, text: str, voice: str, output: Path) -> dict:
    engine = TTSEngine(str(model))
    await engine.start()
    try:
        content = await engine.synthesize(text, voice=voice, language="zh")
    finally:
        await engine.stop()
    output.write_bytes(content)
    with wave.open(str(output), "rb") as audio:
        return {
            "output": str(output),
            "bytes": len(content),
            "channels": audio.getnchannels(),
            "sample_width": audio.getsampwidth(),
            "sample_rate": audio.getframerate(),
            "frames": audio.getnframes(),
            "duration_seconds": audio.getnframes() / audio.getframerate(),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--text", default="你好，这是 AI2Apps 的语音输出测试。")
    parser.add_argument("--voice", default="serena")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = asyncio.run(
        synthesize(
            args.model.expanduser().resolve(strict=True),
            args.text,
            args.voice,
            args.output.expanduser().resolve(),
        )
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
