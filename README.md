# DynaMoe

Scope-aware dynamic MoE inference for Apple Silicon.

DynaMoe is an independent inference product built on the open-source
[oMLX](https://github.com/jundot/omlx) runtime. It adds scope selection,
cache-aware routed experts, SSD expert storage, optional lossy acceleration,
session-safe KV reuse, and DynaMoe-specific observability for very large MoE
models such as DeepSeek V4 Flesh.

> DynaMoe is not affiliated with, sponsored by, or endorsed by the oMLX
> project or its maintainers. The oMLX name is used only to identify the origin
> of the runtime. See [NOTICE](NOTICE) for attribution.

[中文说明](README.zh.md) · [Architecture](docs/architecture.md) ·
[Flesh engine](docs/deepseek-v4-flesh-engine.md) ·
[Benchmark records](docs/moe-cache-benchmark-2026-08-08.md) ·
[Release gate](docs/release-gate.md)

## What DynaMoe adds

- Configurable flat or hierarchical scope catalogs.
- Shared-expert scope probing, 16 layers by default and configurable to 43.
- Per-scope static expert banks with device-side Top-K routing.
- Exact, conservative, `tail1`, `tail2`, and aggressive `head2` policies.
- Expert-major SSD storage and cache-aware fallback loading.
- Multi-turn sessions and scope-namespaced KV-cache reuse.
- OpenAI-compatible endpoints, CLI, chat UI, and live scope/cache status.
- Reproducible prefill/decode, miss handling, I/O, and scope benchmarks.

The inherited oMLX runtime continues to provide model loading, attention,
fused MoE kernels, continuous batching, paged KV caching, audio/VLM engines,
MCP integration, and the original administration capabilities.

## Repository layout

```text
dynamoe/                 DynaMoe product package and public CLI
omlx/                    Embedded, modified oMLX runtime
  engine/flesh.py        DeepSeek V4 Flesh request orchestration
  cache/                 KV and MoE expert storage
  patches/deepseek_v4/   Scope router, banks, policies and kernels
  admin/                 DynaMoe WebUI served by the runtime
configs/                 Scope catalogs and profiles
scripts/                 Conversion, profiling and benchmark tools
docs/                    Architecture and experiment records
artifacts/               Local experiment output
```

The `omlx` Python namespace and `OMLX_*` environment variables are retained as
runtime compatibility interfaces. New consumers should use the `dynamoe`
command and import product engines from `dynamoe.runtime`.

## Install

Requirements: Apple Silicon Mac, Python 3.11–3.13, and macOS with Metal support.

```bash
brew install uv
uv sync --dev
source .venv/bin/activate
```

Alternatively, create a Python 3.11–3.13 virtual environment and install the
project with `python -m pip install -e '.[dev]'`.

Verify the product and embedded runtime:

```bash
dynamoe --version
dynamoe info
```

Runtime data currently remains under `~/.omlx` so existing models, settings,
and KV cache data are not orphaned during migration.

## Start the server

```bash
dynamoe serve --model-dir ~/models --port 8000
```

- Chat UI: <http://127.0.0.1:8000/admin/chat>
- Dashboard: <http://127.0.0.1:8000/admin/dashboard>
- OpenAI base URL: <http://127.0.0.1:8000/v1>
- Chat completions: `POST /v1/chat/completions`
- Models: `GET /v1/models`

Example:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"source","messages":[{"role":"user","content":"Hello"}]}'
```

The legacy `omlx` executable remains available as a temporary compatibility
alias, but documentation and integrations should use `dynamoe`.

## DeepSeek V4 Flesh

Models installed from the DynaMoe Download source use the verified Scope Pack
shipped in the release automatically. Manual research checkouts can still
override the profile and expert store before starting:

```bash
export DYNAMOE_DEEPSEEK_V4_EXPERT_STORE=/path/to/expert-store
export DYNAMOE_DEEPSEEK_V4_SCOPE_PROFILE=/path/to/scope-profile.json
export DYNAMOE_DEEPSEEK_V4_SCOPE_NAME=general
export DYNAMOE_DEEPSEEK_V4_SCOPE_PROBE_DEPTH=16
export DYNAMOE_DEEPSEEK_V4_SCOPE_LOSSY_MODE=exact

dynamoe serve --model-dir /path/to/models
```

The `dynamoe` entry point translates `DYNAMOE_*` variables to the retained
`OMLX_*` runtime interface; legacy deployment files therefore continue to
work. The profile override is not required for models prepared by DynaMoe.
Lossy mode is opt-in. Use `exact` for quality-sensitive serving; benchmark
`conservative`, `tail1`, `tail2`, or `head2` against representative prompts
before deployment. The dashboard reports the active scope, probe depth, lossy
mode, scope switches, and fallback count without introducing a GPU sync.

## Development and performance gate

The experimental branch is `experiment/moe-cache`. Preserve oMLX model,
attention, router, and fused MoE behavior unless a DynaMoe feature explicitly
requires a small isolated patch. Benchmark changes with identical prompts and
generated tokens and record memory, cold TPS, and steady TPS.

```bash
pytest -q
python scripts/bench_scope_once.py --help
python scripts/bench_moe_expert_store.py --help
dynamoe-release-gate --mode preflight --run-tests
```

Before dynamic replacement is considered production-ready, the static oracle
bank must retain exact Top-10 parity, have zero runtime misses, reduce resident
memory, and preserve at least 85% of full-resident steady-state TPS.

## Origin, license, and trademarks

DynaMoe is based on oMLX commit
[`49ec271`](https://github.com/jundot/omlx/commit/49ec271676ba9c14bbebb75da1912e3fcb5fb0f4)
and retains upstream copyright and attribution notices. Modified files and the
repository history identify the DynaMoe changes.

This project is licensed under the [Apache License 2.0](LICENSE). Copyright
2025 oMLX contributors; Copyright 2026 DynaMoe contributors. Apache-2.0 does
not grant broad rights to upstream trade names or marks. DynaMoe does not use
the oMLX name or logo as its product identity and makes no claim of upstream
affiliation, sponsorship, certification, or endorsement.
