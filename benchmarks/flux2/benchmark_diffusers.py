#!/usr/bin/env python3
"""PyTorch Diffusers BF16 reference benchmark for FLUX.2 Klein."""

import argparse
import json
import statistics
import time
from pathlib import Path

import torch
from diffusers import Flux2KleinPipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=("4b", "9b"), required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompts", type=Path, default=Path(__file__).with_name("prompts.json"))
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    prompts = json.loads(args.prompts.read_text())
    torch.cuda.reset_peak_memory_stats()
    load_start = time.perf_counter()
    pipeline = Flux2KleinPipeline.from_pretrained(
        args.model_path, torch_dtype=torch.bfloat16
    ).to("cuda")
    load_seconds = time.perf_counter() - load_start

    rows = []
    for prompt_index, item in enumerate(prompts):
        timings = []
        for repeat in range(args.repeats):
            seed = 1000 + prompt_index
            generator = torch.Generator(device="cuda").manual_seed(seed)
            started = time.perf_counter()
            image = pipeline(
                prompt=item["prompt"], generator=generator,
                num_inference_steps=args.steps, guidance_scale=1.0,
                width=args.width, height=args.height,
            ).images[0]
            torch.cuda.synchronize()
            elapsed = time.perf_counter() - started
            timings.append(elapsed)
            if repeat == args.repeats - 1:
                image.save(args.output / f"{item['id']}.png")
        rows.append({
            "id": item["id"], "prompt": item["prompt"], "seed": 1000 + prompt_index,
            "seconds": timings, "median_seconds": statistics.median(timings),
        })
    report = {
        "backend": "diffusers-bf16", "model": args.model,
        "width": args.width, "height": args.height, "steps": args.steps,
        "load_seconds": load_seconds,
        "peak_memory_bytes": torch.cuda.max_memory_allocated(),
        "median_generation_seconds": statistics.median(row["median_seconds"] for row in rows),
        "runs": rows,
    }
    (args.output / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

