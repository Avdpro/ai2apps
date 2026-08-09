# Qwen3.6 Install Pipeline Release Gate (2026-08-10)

## Result

The Qwen3.6-35B-A3B 4-bit DynaMoe install pipeline passes the local release
gate. A pinned Hugging Face snapshot was resolved from an isolated HF cache,
converted into the dedicated fused/split expert stores, interrupted, resumed,
reinstalled idempotently, loaded by the Tiered engine, and exercised through a
two-turn Auto-L1 conversation.

This run deliberately reused the existing read-only 19 GiB checkpoint at
`/Users/avdpropang/sdk/dmoe/artifacts/qwen3.6-35b-a3b-4bit/source` to avoid a
second network transfer. The isolated cache contains only Hugging Face cache
links to that checkpoint; the DMoE repository was not modified. This validates
cache discovery and conversion, but it is not a cold-network bandwidth test.

## Resume defect found and fixed

The first interrupted run completed four routed layers. With the previous
all-or-nothing `conversion.json`, restarting rewrote `layer-000.moe`; its mtime
changed from `1786309982307026413` to `1786310007959000202`.

The installer now atomically checkpoints `completed_layers` and
`split_completed_layers` after every layer. A layer is reused only when the
conversion identity matches and its store validates. A different checkpoint
revision or conversion variant starts with an empty ledger, so stale outputs
cannot be accepted.

After the fix:

- the interrupted ledger contained layers 0-4 in both stores;
- resume preserved all five fused-layer mtimes and converted only the remaining
  35/40 layers in approximately 28.7 seconds;
- a third identical install completed in 0.824 seconds;
- no fused or split expert file changed on the third install;
- both final completion ledgers contain all 40 layers.

## Installed model validation

The installed manifest reports:

- engine: `qwen3.6-tiered` v1;
- checkpoint revision: `38740b847e4cb78f352aba30aa41c76e08e6eb46`;
- conversion: `qwen3.6-affine-q4-gate-up-fused-v2`;
- Scope Pack: `qwen3.6-35b-a3b-scope-pack` version `2026.08.09.1`;
- expert store: `expert-store-fused`;
- default memory tier: `auto` (resolved to Top-120 on this 128 GiB device);
- Tail arena: 24 experts per routed layer.

The installed-mode gate marked every Qwen check PASS. Its aggregate result is
PENDING only because the isolated model directory intentionally does not
contain the two DeepSeek release models.

## Real engine checks

Single-turn Tiered, 64-token generation:

- model load: 1.584 s;
- TTFT: 1.160 s;
- derived decode: 33.409 TPS;
- peak MLX: 11.489 GiB;
- physical bank: Top-120 plus Tail-24 across all 40 routed layers;
- Auto-L1: enabled and triggered once;
- lossy acceleration: disabled.

Two-turn Tiered Auto-L1 conversation, 128 tokens per turn:

| Turn | Prompt tokens | TTFT | Decode |
|---:|---:|---:|---:|
| 1 | 41 | 1.300 s | 34.672 TPS |
| 2 | 216 | 0.982 s | 35.804 TPS |

Overall decode was 35.229 TPS. Auto-L1 performed one optimization trigger; its
four bank commits reused 7,514 GPU-resident expert slots and loaded 2,570 slots
from the local store. The second-turn TTFT remained below the first turn, which
also exercises the installed engine's multi-turn session path.

## Automated gate

The preflight release gate passed all catalog, pinned-revision, Scope Pack and
focused test checks:

```text
Overall: PASS
134 passed in 183.16s
```

The downloader suite also passed independently:

```text
118 passed in 182.74s
```

The installer regression test now asserts the per-layer completion ledger and
verifies that a repeated pinned install preserves fused and split store mtimes.

## Evidence

- `artifacts/release-gate/qwen36-install-pipeline-2026-08-10/preflight.md`
- `artifacts/release-gate/qwen36-install-pipeline-2026-08-10/installed.md`
- `artifacts/release-gate/qwen36-install-pipeline-2026-08-10/tiered-64.json`
- `artifacts/release-gate/qwen36-install-pipeline-2026-08-10/tiered-auto-2turn-128.json`

Before publishing, the remaining operational smoke test is one real cold or
partially interrupted Hugging Face network download from the WebUI/API. It is
not necessary to repeat the 19 GiB transfer for conversion correctness, but it
will validate credentials, CDN behavior, progress reporting and cancellation
outside the mocked downloader tests.
