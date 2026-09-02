#!/usr/bin/env python3
"""Real Metal smoke test through the production Z-Image package pipeline."""

import argparse
import json
import sys
import time
from pathlib import Path

import mlx.core as mx
from mflux.models.common.config.model_config import ModelConfig


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages/ai2apps-model-z-image-mlx/src"))

from optimized_pipeline import OptimizedZImage  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quantize", type=int, choices=(4, 8), default=8)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    pipeline = OptimizedZImage(
        model_config=ModelConfig.z_image_turbo(),
        model_path=args.model_path,
        quantize=args.quantize,
    )
    loaded = time.perf_counter() - started
    mx.reset_peak_memory()
    started = time.perf_counter()
    generated = pipeline.generate_image(
        seed=3100,
        prompt="一张现代科技发布会海报，深蓝色背景，中央清晰写着『AI2Apps 本地智能』，下方小字『速度、隐私、创造力』，文字必须准确可读，专业摄影棚灯光",
        num_inference_steps=8,
        width=512,
        height=512,
        guidance=0.0,
    )
    elapsed = time.perf_counter() - started
    generated.save(args.output / "package-smoke.png", overwrite=True)
    report = {
        "load_seconds": loaded,
        "generation_seconds": elapsed,
        "peak_memory_bytes": mx.get_peak_memory(),
        "optimization": pipeline.ai2apps_optimization_stats(),
    }
    (args.output / "metrics.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
