# Qwen3.6 DynaMoe installation

`Qwen3.6-35B-A3B 4-bit` is a verified DynaMoe catalog recipe. The Download
page uses the normal DynaMoe source and performs these stages automatically:

1. Reuse a complete `mlx-community/Qwen3.6-35B-A3B-4bit` Hugging Face
   snapshot when it is already in the local HF cache; otherwise download it.
2. Index the stacked affine-Q4 routed tensors directly in their original
   safetensors shards. A layer may span more than one shard.
3. Build page-aligned expert-major records and convert them to the Qwen
   gate/up-fused v2 runtime layout.
4. Write `dynamoe-model.json` selecting the independent `qwen3.6-tiered`
   engine, the chosen Top80/96/120 memory tier, Tail24, the expert store, and
   the Scope Pack.
5. Validate every converted layer and rediscover the completed model.

The conversion is resumable. Existing valid fused layers are retained, so a
cancelled or failed installation does not repeat completed layers.

## Scope Pack

Release packages include the verified Scope Pack at the engine asset path. A
normal DynaMoe download needs no profile environment variable. The installer
checks the bundled profile SHA-256 and records its pack ID, version, and hash in
`dynamoe-model.json`.

For a development checkout that deliberately omits packaged assets, an
external profile can provide the fallback path:

```bash
export OMLX_QWEN36_SCOPE_PROFILE=/absolute/path/to/decode-top120.json
```

The fallback profile must contain matching `prefill` and `decode` phases, all
configured scopes, and all forty routed layers. Release packages always prefer
their checksummed Scope Pack.

## Installed layout

```text
HF model directory/
├── config.json
├── model-*.safetensors          # links into HF cache when reused
├── dynamoe-model.json
└── .dynamoe/
    ├── offsets-qwen36/offset-manifest.json
    ├── expert-store-split/      # resumable conversion intermediate
    └── expert-store-fused/      # runtime store selected by the manifest
```

The full checkpoint is retained. The first release favors predictable retries
and validation over disk minimization.
