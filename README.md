# AI2Apps

**A local-first AI application and Agent platform for personal AI nodes.**

AI2Apps turns local and connected model runtimes into durable Apps, Agents,
and versioned Services. It provides a server-owned Agent Harness, application
shell, tool and capability gateway, package trust system, multi-user identity,
and remote access above one or more model backends.

Apple Silicon and the embedded [oMLX](https://github.com/jundot/omlx) runtime
are the first implementation. AI2Apps also keeps its platform contracts
hardware-neutral so that external providers and future NVIDIA/CUDA or AMD/ROCm
nodes can expose the same model and Service capabilities.

> AI2Apps is not affiliated with, sponsored by, or endorsed by the oMLX
> project or its maintainers. The oMLX name identifies the origin of the
> embedded runtime. See [NOTICE](NOTICE) for attribution.

[中文说明](README.zh.md) ·
[Platform architecture](docs/ai2apps-platform-architecture.md) ·
[ACPF capability provisioning](docs/ai2apps-capability-provisioning-framework-v1.md) ·
[Backend plan](docs/ai2apps-backend-development-plan.md) ·
[Local Knowledge/RAG](docs/ai2apps-local-knowledge-rag-architecture.md) ·
[Security baseline](docs/security-authority-baseline.md) ·
[Release gate](docs/release-gate.md)

## Product model

AI2Apps is organized around four product objects and one runtime layer:

```text
User / API client
        ↓
App      interaction, UI, instances, Sessions, files and artifacts
        ↓
Agent    goals, instructions, model policy, tools and durable execution
        ↓
Service  stable, versioned and auditable capabilities
        ↓
Runtime  local oMLX/Fusion, Cloud, external or future federated providers
```

- **Apps** own user interaction and persistent application state. Built-in
  Apps currently include Chat, Coder, Account, Agents, Models, Trust Center,
  Terminal, settings, logs, and benchmarks.
- **Agents** run through an authoritative server-side Harness. Runs, steps,
  status, interactions, approvals, events, retries, delegation, pause, resume,
  cancellation, and final output are durable and restart-aware.
- **Services** expose models, tools, workspace operations, processes, browser
  control, documents, images, research, terminal access, and external
  capabilities through stable identities instead of fixed physical URLs.
- **AI nodes** keep application and Session data local while supporting Cloud
  models, remote/mobile access, installation membership, and controlled
  Service federation as the next node-to-node layer.
- **Model runtimes** remain replaceable backends. Cache-MoE and Fusion are
  important local inference optimizations, not the boundary of the platform.

## Implemented platform capabilities

The current alpha includes:

- a SQLite-backed App, AppInstance, Session, Message, AgentRun, Step, Event,
  Workspace, Artifact, Service, Tool, capability, package, and identity control
  plane;
- persistent asynchronous Agent execution with Tool calls, user interactions,
  capability approval, bounded delegation, recovery, and replayable events;
- a Service Registry and Tool Gateway for embedded, sandboxed managed-process,
  and external Services;
- signed and content-addressed `.ai2service`, `.ai2agent`, `.ai2app`, and local
  `.ai2patch` package flows with verification, lifecycle, rollback, and Safe
  Mode;
- Session-scoped workspaces, ResourceHandles, artifacts, document parsing and
  source-located reads, process limits, Secret injection, and audit events;
- Chat as a per-user singleton App with independently isolated thread Sessions;
- Coder projects and threads for Codex, OpenCode, and Claude CLIs, including
  source validation, tests, browser preview, development bundles, TestFlight,
  and a bounded file editor;
- local installation identity, multiple member roles, per-user ownership,
  Cloud device binding, unified billing identity, revocable local sessions,
  and role-aware App access;
- a desktop shell, mobile-ready App contracts, managed remote access, and
  Cloud model bridging;
- OpenAI-compatible model APIs backed by the existing oMLX runtime.

The project is still under active development. Node-to-node Service federation,
complete OS-level sandbox coverage, a first-class local knowledge/retrieval
Service, and additional hardware backend providers remain ongoing work. Design
documents distinguish implemented behavior from target architecture.

## Local inference and Fusion

The embedded oMLX backend retains model loading, attention, fused MoE kernels,
continuous batching, paged KV caching, audio/VLM engines, embeddings,
reranking, and MCP integration. AI2Apps adds local inference capabilities for
large MoE models such as DeepSeek V4 Flesh:

- configurable flat or hierarchical scope catalogs;
- shared-expert scope probing and per-scope static expert banks;
- device-side Top-K routing with exact and explicitly enabled lossy policies;
- expert-major SSD storage and cache-aware fallback loading;
- Session-safe KV/prefix-cache namespaces and adaptive L1 expert residency;
- reproducible memory, quality, prefill, decode, miss, and I/O release gates.

See the [Flesh engine](docs/deepseek-v4-flesh-engine.md),
[Fusion design](docs/fusion-engine-design.md), and
[MoE benchmark record](docs/moe-cache-benchmark-2026-08-08.md).

## Repository layout

```text
ai2apps/                 Platform, App, Agent, Service and product code
  agents/                Durable Agent Runtime and built-in Agents
  api/                   Versioned platform APIs
  apps/                  App definitions, access policy and lifecycle
  packages/              Signed package trust and Service lifecycle
  services/              Service Registry, adapters and Tool Gateway
  storage/               SQLite schema, migrations and repositories
  workspace/ documents/  Session resources, artifacts and document tools
  web/                    Desktop/mobile Shell and built-in App UI
apps/omlx-mac/            Native macOS application shell
omlx/                     Embedded and modified oMLX model runtime
  engine/flesh.py         DeepSeek V4 Flesh request orchestration
  cache/                  KV and routed-expert storage
  patches/deepseek_v4/    Scope routing, expert banks and kernels
configs/                  Scope catalogs and model profiles
scripts/                  Conversion, profiling, packaging and benchmarks
docs/                     Architecture, product contracts and experiment records
tests/                    Platform, security, API and inference tests
```

The `omlx` Python namespace and `OMLX_*` variables remain compatibility
interfaces for the embedded runtime. New integrations should use the
`ai2apps` command and `AI2APPS_*` configuration where available. Runtime data
currently remains under `~/.omlx` so existing models and settings survive the
product migration.

## Install

The bundled local model backend currently requires an Apple Silicon Mac,
Python 3.11–3.13, and Metal-capable macOS.

```bash
brew install uv
uv sync --dev
source .venv/bin/activate

ai2apps --version
ai2apps info
```

Alternatively, create a Python 3.11–3.13 virtual environment and run:

```bash
python -m pip install -e '.[dev]'
```

## Start AI2Apps

```bash
ai2apps serve --model-dir ~/models --port 8000
```

- App shell / dashboard: <http://127.0.0.1:8000/admin/dashboard>
- Chat: <http://127.0.0.1:8000/admin/chat>
- OpenAI base URL: <http://127.0.0.1:8000/v1>
- Platform API root: <http://127.0.0.1:8000/v1/platform>
- Chat completions: `POST /v1/chat/completions`
- Model catalog: `GET /v1/models`

If an API key is configured, send it as a Bearer token. The legacy `omlx`
executable remains a compatibility alias; new documentation and integrations
should use `ai2apps`.

## DeepSeek V4 Flesh research overrides

Models prepared through AI2Apps use their verified Scope Pack automatically.
Manual research environments can override the expert store and profile:

```bash
export AI2APPS_DEEPSEEK_V4_EXPERT_STORE=/path/to/expert-store
export AI2APPS_DEEPSEEK_V4_SCOPE_PROFILE=/path/to/scope-profile.json
export AI2APPS_DEEPSEEK_V4_SCOPE_NAME=general
export AI2APPS_DEEPSEEK_V4_SCOPE_PROBE_DEPTH=16
export AI2APPS_DEEPSEEK_V4_SCOPE_LOSSY_MODE=exact

ai2apps serve --model-dir /path/to/models
```

Lossy modes are opt-in. Use `exact` for quality-sensitive serving and evaluate
other policies with representative prompts before deployment.

## Development and release gates

Before developing an AI2Apps App or System App, read the
[AI2Apps App development guide](docs/ai2apps-app-development-guide.md), including
the shared cross-environment Artifact download UX contract.

Before developing an installable Service or model Package, read the
[Service/Package runtime and Sandbox development guide](docs/service-package-sandbox-development-guide.md).
For the Model Worker protocol, Adapter API, and checkpoint contract, see the
[Model Worker Package manual](docs/model-worker-package-manual.md). A local
Harness or terminal run does not reproduce installed Sandbox permissions; a
real `.ai2service` installation and activation is required before release.

The active experimental branch is `experiment/moe-cache`. Preserve existing
oMLX model, attention, router, scheduler, and fused-kernel behavior unless an
AI2Apps feature requires a small, isolated compatibility patch. Platform code
should remain under `ai2apps` and depend on model runtimes through adapters.

```bash
pytest -q
python scripts/bench_scope_once.py --help
python scripts/bench_moe_expert_store.py --help
ai2apps-release-gate --mode preflight --run-tests
```

Inference comparisons use identical prompts and generated tokens and record
source commit, resident/peak memory, cold TPS, and steady TPS. The original
static oracle gate requires exact Top-10 parity, zero runtime misses, lower
resident memory, and at least 85% of full-resident steady-state TPS.

Platform changes must additionally preserve ownership isolation, capability
enforcement, package verification, restart recovery, API compatibility, and
bounded resource behavior.

## Origin, license, and trademarks

AI2Apps is based on oMLX commit
[`49ec271`](https://github.com/jundot/omlx/commit/49ec271676ba9c14bbebb75da1912e3fcb5fb0f4)
and retains upstream copyright and attribution notices. Modified files and the
repository history identify AI2Apps changes.

This project is licensed under the [Apache License 2.0](LICENSE). Copyright
2025 oMLX contributors; Copyright 2026 AI2Apps contributors. Apache-2.0 does
not grant broad rights to upstream trade names or marks. AI2Apps does not use
the oMLX name or logo as its product identity and makes no claim of upstream
affiliation, sponsorship, certification, or endorsement.
