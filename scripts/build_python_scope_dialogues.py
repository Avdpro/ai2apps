#!/usr/bin/env python3
"""Generate an isolated mixed-context Python dialogue corpus."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--max-tokens", type=int, default=96)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-text", type=Path, required=True)
    return parser.parse_args()


def _load_encoder(model: Path):
    path = model / "encoding" / "encoding_dsv4.py"
    spec = importlib.util.spec_from_file_location("omlx_python_scope_encoding", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load DeepSeek encoder from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.encode_messages


async def _run(args: argparse.Namespace) -> tuple[dict, str]:
    from omlx.engine.batched import BatchedEngine

    model = args.model.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve()
    manifest = json.loads(manifest_path.read_text())
    prompts = manifest["prompts"]
    encode_messages = _load_encoder(model)
    engine = BatchedEngine(str(model))
    await engine.start()
    examples = []
    documents = []
    try:
        for index, item in enumerate(prompts):
            user = {"role": "user", "content": item["content"]}
            encoded_prompt = encode_messages([user], thinking_mode="chat")
            output = await engine.generate(
                prompt=encoded_prompt,
                max_tokens=args.max_tokens,
                temperature=0.0,
                top_p=1.0,
                skip_cache_store=True,
            )
            assistant = {"role": "assistant", "content": output.text}
            document = encode_messages([user, assistant], thinking_mode="chat")
            documents.append(document)
            examples.append(
                {
                    **item,
                    "completion": output.text,
                    "completion_tokens": output.completion_tokens,
                }
            )
            print(
                json.dumps(
                    {
                        "index": index + 1,
                        "total": len(prompts),
                        "id": item["id"],
                        "completion_tokens": output.completion_tokens,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    finally:
        await engine.stop()

    payload = {
        "format": "omlx-code-python-generated-dialogues",
        "version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "model": str(model),
        "source_manifest": str(manifest_path),
        "max_tokens": args.max_tokens,
        "examples": examples,
    }
    return payload, "\n\n".join(documents) + "\n"


def main() -> None:
    args = _args()
    json_path = args.output_json.expanduser().resolve()
    text_path = args.output_text.expanduser().resolve()
    for path in (json_path, text_path):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite generated corpus: {path}")
    payload, corpus = asyncio.run(_run(args))
    json_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("x") as target:
        target.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    with text_path.open("x") as target:
        target.write(corpus)


if __name__ == "__main__":
    main()
