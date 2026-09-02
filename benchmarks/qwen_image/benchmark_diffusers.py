#!/usr/bin/env python3
"""DGX Spark BF16 Diffusers reference benchmark for Qwen Image."""

import argparse
import json
import statistics
import time
from pathlib import Path

import torch
from diffusers import DiffusionPipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompts", type=Path, default=Path(__file__).with_name("prompts.json"))
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--guidance", type=float, default=4.0)
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    prompts = json.loads(args.prompts.read_text())
    torch.cuda.reset_peak_memory_stats()
    load_started = time.perf_counter()
    pipeline = DiffusionPipeline.from_pretrained(
        args.model_path,
        torch_dtype=torch.bfloat16,
    ).to("cuda")
    load_seconds = time.perf_counter() - load_started

    rows = []
    for prompt_index, item in enumerate(prompts):
        timings = []
        for repeat in range(args.repeats):
            seed = int(item.get("seed", 2000 + prompt_index))
            generator = torch.Generator(device="cuda").manual_seed(seed)
            started = time.perf_counter()
            image = pipeline(
                prompt=item["prompt"],
                negative_prompt="blurry, distorted, unreadable text, watermark",
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
                "seed": int(item.get("seed", 2000 + prompt_index)),
                "seconds": timings,
                "first_seconds": timings[0],
                "steady_median_seconds": statistics.median(timings[1:] or timings),
            }
        )
    report = {
        "backend": "cuda-diffusers-bf16",
        "model": "Qwen/Qwen-Image-2512",
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
    (args.output / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
