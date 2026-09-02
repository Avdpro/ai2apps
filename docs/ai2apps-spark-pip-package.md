# AI2Apps Spark pip package

The Spark distribution is an inference-free AI2Apps Host for Linux ARM64.
Model inference runs in managed CUDA Runtime Services rather than inside the
WebUI process. This keeps CUDA/PyTorch engine dependencies independently
versioned and prevents one model backend from breaking the control plane.

Build the wheel:

```sh
.venv/bin/python scripts/build_spark_pip_package.py
```

Install it on a DGX Spark:

```sh
python3 -m venv ~/.local/share/ai2apps/venv
~/.local/share/ai2apps/venv/bin/pip install ai2apps_spark-*.whl
~/.local/share/ai2apps/venv/bin/ai2apps doctor --deep
```

The Host can run without Docker for WebUI and remote-provider use. Locally
installed CUDA Model Worker Packages use a hardened Docker container with a
read-only root, dropped capabilities, private IPC, and no network by default.
Granting a long-running service access to the Docker daemon is effectively a
root-equivalent permission, so it is never added implicitly. Enable it only on
a dedicated trusted Spark Host:

```sh
~/.local/share/ai2apps/venv/bin/ai2apps service install \
  --allow-docker-control
```

The CUDA Worker listens on a short Unix-domain socket inside the no-network
container. The Host exposes a random loopback-only HTTP proxy to the AI2Apps
gateway; the Worker endpoint is not published by Docker.

The Spark entry point defaults to `~/.local/share/ai2apps` and listens on
`127.0.0.1:8000`. Use an SSH tunnel until authenticated HTTPS/LAN access has
been configured. For a foreground development run, use `ai2apps serve`; the
same safe defaults apply when `--base-path` and `--host` are omitted.

Register an OpenAI-compatible Runtime that listens on the Spark loopback
interface:

```sh
ai2apps models add-openai \
  --id local-transformers \
  --base-url http://127.0.0.1:8766/v1 \
  --model /absolute/path/to/local-model
```

The command stores provider configuration through AI2Apps' encrypted Secret
backend and enables the resulting `cloud/local-transformers/...` gateway model.
Non-loopback endpoints are rejected unless `--allow-remote` is explicit.

## CUDA Runtime and Model Packages

Spark uses two independently signed Package layers:

- `ai2apps.runtime.cuda-torch` contains a private ARM64 CPython runtime,
  PyTorch/Transformers dependencies, and the Model Worker launcher. CUDA driver
  libraries remain supplied by the Spark Host.
- `ai2apps.model.qwen25-0.5b-cuda` contains the adapter and immutable model
  metadata. Its weights are pinned to an exact Hugging Face revision and stay
  in the shared local cache rather than being copied into every Package.

Build the Runtime on the target ARM64/CUDA host, then build model Packages with
the same trusted publisher key:

```sh
python scripts/build_cuda_torch_runtime_package.py \
  --source-venv /path/to/cuda-venv \
  --package packages/ai2apps-runtime-cuda-torch
python scripts/build_model_provider_package.py \
  packages/ai2apps-model-qwen25-0.5b-cuda
```

The Runtime payload is a SHA256-pinned `tar.gz`. Installation streams and
limits both the signed Package archive and expanded Runtime payload, rejects
path/link escapes and special files, then makes the installed Runtime
immutable. Runtime, adapter, and checkpoint roots are mounted read-only into
the Worker; only its Package data, temporary directory, and Unix-socket
directory are writable.
