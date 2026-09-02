#!/usr/bin/env bash
set -euo pipefail

ROOT="${HOME}/flux2-bench"
MODEL="${ROOT}/models/FLUX.2-klein-4B"
RESULTS="${ROOT}/results/4b"
LOG="${RESULTS}/suite.log"
mkdir -p "${RESULTS}"
exec >>"${LOG}" 2>&1

echo "suite_started=$(date -Iseconds)"
while pgrep -f 'download_modelscope.py --model 4b' >/dev/null; do
  echo "download_bytes=$(du -sb "${MODEL}" | cut -f1) time=$(date -Iseconds)"
  sleep 60
done

python3 - "${MODEL}" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
expected = {
    "transformer/diffusion_pytorch_model.safetensors": 7751109744,
    "text_encoder/model-00001-of-00002.safetensors": 4967215360,
    "text_encoder/model-00002-of-00002.safetensors": 3077766632,
    "vae/diffusion_pytorch_model.safetensors": 168120878,
}
for name, size in expected.items():
    path = root / name
    actual = path.stat().st_size if path.is_file() else -1
    if actual != size:
        raise SystemExit(f"checkpoint verification failed: {name} expected={size} actual={actual}")
print("checkpoint_size_verification=ok")
PY

cd "${ROOT}"
mlx-env/bin/python scripts/benchmark_mlx.py \
  --model 4b --model-path "${MODEL}" --output "${RESULTS}/mlx-optimized-q8" \
  --quantize 8 --width 1024 --height 1024 --steps 4 --repeats 3
mlx-env/bin/python scripts/benchmark_mlx.py \
  --model 4b --model-path "${MODEL}" --output "${RESULTS}/mlx-baseline-q8" \
  --quantize 8 --width 1024 --height 1024 --steps 4 --repeats 3 --baseline

docker run --rm --gpus all --ipc=host \
  --ulimit memlock=-1 --ulimit stack=67108864 \
  -v "${ROOT}:/work" \
  -e PYTHONPATH=/work/ref-python:/work/mlx-env/lib/python3.12/site-packages \
  m.daocloud.io/nvcr.io/nvidia/pytorch:25.11-py3 \
  python /work/scripts/benchmark_diffusers.py \
    --model 4b --model-path /work/models/FLUX.2-klein-4B \
    --output /work/results/4b/diffusers-bf16 \
    --width 1024 --height 1024 --steps 4 --repeats 2

echo "suite_finished=$(date -Iseconds)"
