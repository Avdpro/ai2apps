# AI2Apps architecture

AI2Apps keeps the product surface separate from its upstream-derived runtime.
This makes the public identity clear while preserving small, reviewable oMLX
patches.

```text
ai2apps/                    Public product package
  cli.py                    `ai2apps` command
  branding.py               Product and attribution strings
  runtime.py                Supported engine imports

omlx/                       Embedded oMLX-derived runtime
  engine/flesh.py           DeepSeek V4 Flesh orchestration
  cache/moe_expert_store.py Expert storage and loading
  patches/deepseek_v4/      Scope cache, policy, routing and kernels
  admin/                    AI2Apps-branded WebUI served by the runtime

configs/                    Scope catalogs and runtime configurations
scripts/                    Research, conversion and benchmark tools
artifacts/                  Local experiment outputs (not product source)
docs/                       Design notes and reproducible benchmark records
```

## Compatibility boundary

The Python import namespace `omlx` and the `OMLX_*` environment variables are
retained where changing them would break the embedded runtime or existing
deployments. New applications should invoke `ai2apps` and import product
engines from `ai2apps.runtime`. The legacy `omlx` executable is retained as a
compatibility alias during migration.

Runtime data remains under `~/.omlx` for now so upgrading does not orphan model
settings, downloads, or KV cache data. A future migration may introduce a
`~/.ai2apps` home with an explicit one-time importer.
