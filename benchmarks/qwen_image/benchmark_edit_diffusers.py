#!/usr/bin/env python3
"""DGX Spark BF16 Diffusers reference benchmark for Qwen Image Edit 2511."""

import argparse
import json
import statistics
import time
from pathlib import Path

import torch
from diffusers import DiffusionPipeline
from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--guidance", type=float, default=2.5)
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    torch.cuda.reset_peak_memory_stats()
    load_started = time.perf_counter()
    pipeline = DiffusionPipeline.from_pretrained(
        args.model_path,
        torch_dtype=torch.bfloat16,
    ).to("cuda")
    load_seconds = time.perf_counter() - load_started

    rows = []
    for case_index, item in enumerate(cases):
        reference_paths = [(args.cases.parent / value).resolve() for value in item["images"]]
        references = [Image.open(path).convert("RGB") for path in reference_paths]
        timings = []
        for repeat in range(args.repeats):
            generator = torch.Generator(device="cuda").manual_seed(3000 + case_index)
            started = time.perf_counter()
            image = pipeline(
                prompt=item["prompt"],
                negative_prompt="blurry, distorted, unreadable text, watermark",
                image=references,
                generator=generator,
                num_inference_steps=args.steps,
                true_cfg_scale=args.guidance,
                width=args.width,
                height=args.height,
            ).images[0]
            torch.cuda.synchronize()
            timings.append(time.perf_counter() - started)
            if repeat == args.repeats - 1:
                image.save(args.output / f"{item['id']}.png")
        rows.append(
            {
                "id": item["id"],
                "prompt": item["prompt"],
                "images": [str(path) for path in reference_paths],
                "seed": 3000 + case_index,
                "seconds": timings,
                "first_seconds": timings[0],
                "steady_median_seconds": statistics.median(timings[1:] or timings),
            }
        )

    report = {
        "backend": "cuda-diffusers-bf16",
        "model": "Qwen/Qwen-Image-Edit-2511",
        "width": args.width,
        "height": args.height,
        "steps": args.steps,
        "guidance": args.guidance,
        "load_seconds": load_seconds,
        "peak_memory_bytes": torch.cuda.max_memory_allocated(),
        "median_generation_seconds": statistics.median(
            row["steady_median_seconds"] for row in rows
        ),
        "runs": rows,
    }
    (args.output / "metrics.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
