"""Real checkpoint Worker smoke; run with the exported Runtime Python, not pytest."""

import argparse
import asyncio
import importlib.util
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "src"))
import av
import mlx.core as mx
import numpy as np
import soundfile as sf
from ai2apps.model_worker import ModelWorkerRequest, ModelWorkerPart

spec = importlib.util.spec_from_file_location(
    "flashhead_worker", PACKAGE / "src/worker_adapter.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


async def main(args):
    args.output.mkdir(parents=True, exist_ok=True)
    source, rate = sf.read(args.audio, dtype="float32")
    assert rate == 16000
    receipts = []
    for variant, seconds in [("lite", 60), ("pro", 10)]:
        count = 16000 * seconds - 1
        audio = np.tile(source, 1 + count // len(source))[:count]
        wav = args.output / (variant + ".wav")
        sf.write(wav, audio, 16000)
        model_id = f"ai2apps.model.flashhead-mlx/{variant}"
        context = SimpleNamespace(
            models=[
                {
                    "id": model_id,
                    "upstream_id": f"SoulX-FlashHead-{variant.title()}-MLX",
                }
            ],
            checkpoint_for=lambda _: SimpleNamespace(
                path=args.checkpoints / variant, revision="frozen-local-candidate"
            ),
        )
        adapter = module.create_adapter(context)
        await adapter.start()
        mx.reset_peak_memory()
        parts = {
            name: ModelWorkerPart(name, path, mime, path.name, path.stat().st_size, "")
            for name, path, mime in [
                ("reference_00_image", args.image, "image/png"),
                ("audio", wav, "audio/wav"),
            ]
        }

        def progress(value):
            if value["current"] % 40 == 0:
                print(variant, value["current"], value["total"], flush=True)

        start = time.perf_counter()
        result = await adapter.invoke(
            ModelWorkerRequest(
                "video_generation",
                {
                    "model": model_id,
                    "reference_parts": [
                        {"kind": "image", "part_name": "reference_00_image"}
                    ],
                    "resolution": "512x512",
                    "preset": "standard",
                },
                "smoke-" + variant,
                parts,
                args.output,
                progress,
            )
        )
        with av.open(str(result.path)) as media:
            assert len(media.streams.audio) == 1
            frames = 0
            for frame in media.decode(video=0):
                frames += 1
                if frames in (1, 25):
                    frame.to_image().save(
                        args.output / (variant + "-" + str(frames) + ".png")
                    )
            assert frames == (count + 639) // 640
        with av.open(str(result.path)) as media:
            decoded = sum(frame.samples for frame in media.decode(audio=0))
            assert decoded >= count - 1024, (decoded, count)
        receipt = {
            "variant": variant,
            "seconds_including_load": time.perf_counter() - start,
            "frame_count": frames,
            "peak_bytes": mx.get_peak_memory(),
            "output": str(result.path),
            "python": sys.version.split()[0],
            "mlx": mx.__version__,
            "torch_imported": "torch" in sys.modules,
        }
        assert not receipt["torch_imported"]
        receipts.append(receipt)
        print(json.dumps(receipt), flush=True)
        await adapter.stop()
    (args.output / "receipt.json").write_text(json.dumps(receipts, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["checkpoints", "image", "audio", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    asyncio.run(main(parser.parse_args()))
