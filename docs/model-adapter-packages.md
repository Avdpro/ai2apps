# oMLX model adapter packages

Model adapters let a separately released Python distribution add checkpoint
classification, pre-load compatibility work, or a custom loader without
releasing a new desktop client.

## Registration

Publish a wheel with an entry point in the `omlx.model_adapters` group:

```toml
[project.entry-points."omlx.model_adapters"]
my_model = "omlx_model_example.adapter:ExampleAdapter"
```

Entry-point modules must remain lightweight. In particular, do not import MLX
or construct a model during adapter discovery. Import runtime dependencies
inside `prepare()` or `load()` instead.

The minimum adapter contract is:

```python
class ExampleAdapter:
    adapter_id = "example"
    priority = 100

    def match(self, context):
        return context.config.get("model_type") == "example"

    def classify(self, context):
        return "llm"
```

Optional operations are:

- `classify(context)`: return `llm`, `vlm`, `embedding`, `reranker`,
  `audio_stt`, `audio_tts`, or `audio_sts`.
- `prepare(context)`: register model modules or install idempotent patches
  before mlx-lm/mlx-vlm loads the checkpoint.
- `load(context)`: return `(model, tokenizer_or_processor)` when the adapter
  owns a custom checkpoint representation; return `None` for the standard
  loader.
- `installation_recipes()`: return reviewed checkpoint preparation recipes
  for a generic client-side installer. Cached-MoE uses this hook for pinned
  sources, conversion identity, memory tiers and packaged scope assets.

Returning `None` preserves oMLX's existing discovery and loading paths. Match
errors from an optional package are isolated during discovery. Once a package
matches a checkpoint, errors from its operation propagate instead of silently
loading weights through an incompatible fallback.

## Compatibility

Adapter distributions must pin the supported oMLX runtime range, Python ABI,
and MLX version. Native extensions additionally need a platform-specific wheel
and must match the MLX/nanobind ABI used by the runtime.

Each recommended conversation model is one independently versioned package.
The reference packages are `packages/omlx-model-qwen38`,
`packages/omlx-model-deepseek-v4-flash`,
`packages/omlx-model-deepseek-v4-flash-2bit`, and
`packages/omlx-model-qwen36-cached-moe`.

## Installation lifecycle

The desktop app's **Model Adapters** screen installs local wheel files into
`<base_path>/model-adapters`. The server never invokes `pip` and never imports
package code during installation. Instead it:

1. validates the wheel filename and runtime platform tags;
2. checks the package metadata, runtime dependencies, archive paths, and the
   required `omlx.model_adapters` entry point;
3. extracts the wheel into a content-addressed immutable version directory;
4. atomically updates `active.json` to select that version.

Install, upgrade, and uninstall operations require a server restart. This is
intentional: hot-swapping Python modules could leave model classes and patches
from two package versions in one process.

Prepared checkpoints have a separate lifecycle from their adapter package.
During preparation, package-owned runtime assets are copied into the model's
`.ai2apps/scope-assets` directory. Uninstalling a package therefore removes its
catalog recommendation and future preparation support, but does not delete or
break checkpoints that the user already downloaded. Model deletion remains an
explicit, separate operation.

Prepared DeepSeek V4 Flash, DeepSeek V4 Flash 2-bit, and Qwen3.6 35B A3B
checkpoints retain their original Hugging Face weights as well as the derived
expert store. Their per-model `moe_execution_mode` setting can therefore switch
between `cached` (the default, using the resident expert bank) and `full`
(standard oMLX loading with every expert resident). Switching modes reloads the
model, is rejected while requests are active, and uses the complete checkpoint
size for memory admission in full mode. It does not redownload or reconvert the
checkpoint.

The corresponding authenticated admin endpoints are:

- `GET /admin/api/model-adapter-packages`
- `POST /admin/api/model-adapter-packages/inspect`
- `POST /admin/api/model-adapter-packages/install`
- `GET /admin/api/model-adapter-packages/catalog`
- `POST /admin/api/model-adapter-packages/install-from-catalog`
- `POST /admin/api/model-adapter-packages/install-checkpoint`
- `DELETE /admin/api/model-adapter-packages/{package_name}`

The local inspect/install endpoints accept
`{"wheel_path": "/absolute/path/package.whl"}`. Catalog installs accept
`{"package_name": "omlx-model-qwen38", "version": "0.1.0"}`.

## Signed release catalog

Remote releases use the Ed25519 repository-snapshot envelope shared with the
AI2Apps package contract. The server pins the repository public-key
fingerprint and verifies the complete catalog before it downloads executable
bytes. A model-adapter release has this shape inside `payload.releases`:

```json
{
  "packageId": "omlx-model-qwen38",
  "packageType": "model-adapter",
  "version": "0.1.0",
  "status": "published",
  "displayName": "Qwen3.8 adapter",
  "checkpoints": [
    {
      "source": "huggingface",
      "repoId": "unsloth/Qwen3.8-27B-NVFP4",
      "revision": "16b6615af3548b88e2d8e382457bc705b00479cf",
      "displayName": "Qwen3.8 27B NVFP4",
      "estimatedSizeBytes": 23444511709
    }
  ],
  "artifact": {
    "url": "/assets/model-adapters/omlx_model_qwen38-0.1.0-py3-none-any.whl",
    "sha256": "<64 lowercase hex characters>",
    "size": 12345
  }
}
```

The catalog, key, and artifacts must share one HTTPS origin (plain HTTP is
accepted only for loopback test servers). The installer rejects expired or
future-dated metadata, catalog-version rollback, adapter-version downgrade,
redirects, cross-origin artifacts, incorrect signed sizes and digests, and any
wheel that fails the normal local inspection boundary. Only verified releases
are returned to the desktop client.

Checkpoint recommendations are part of the signed snapshot. Hugging Face
recommendations must pin an immutable 40-character commit SHA; the client
passes that revision to the existing downloader instead of following a mutable
branch. Installing an adapter prompts the user to download its sole recommended
checkpoint, while multiple validated variants are presented as a menu. An
adapter release may omit `checkpoints` until real-weight loading and inference
validation has completed.

Cached-MoE recommendations additionally declare `"installMode": "cache-moe"`
and a package-owned `recipeId`. The desktop then starts the generic Cached-MoE
preparation task instead of treating the checkpoint as an ordinary HF download.
The server cross-checks the signed recommendation against the active package
recipe before downloading or converting any weights.

Defaults point at the independently upgradable AI2Apps channel at
`https://coder.ai2apps.com/assets/model-adapters/`. A deployment can override
them with `OMLX_MODEL_ADAPTER_CATALOG_URL`,
`OMLX_MODEL_ADAPTER_CATALOG_KEY_URL`, and
`OMLX_MODEL_ADAPTER_CATALOG_FINGERPRINT`. The fingerprint is a trust anchor and
must be distributed independently of the catalog it authenticates.

## Release workflow

The release builder is intentionally offline and never uploads files. Model
adapters use the existing AI2Apps repository trust root; there is no second
oMLX production key. Its authoritative fingerprint is defined in
`ai2apps/packages/repository_config.py` and shared by both installers. The
`generate-key` command and local `build` signing are for tests and CI previews.
Production payloads are signed on the AI2Apps host with
`scripts/sign_repository_snapshot.mjs`, so the online private key never leaves
the service-side read-only secret mount.

Build the adapter wheel, then create a complete static release directory:

```bash
python -m build --wheel --outdir dist/model-adapters \
  packages/omlx-model-qwen38

python scripts/model_adapter_release.py build \
  --wheel dist/model-adapters/omlx_model_qwen38-0.1.0-py3-none-any.whl \
  --private-key /secure/ephemeral-preview-private.pem \
  --output-dir dist/model-adapter-release \
  --metadata-version 1 \
  --artifact-url-prefix /assets/model-adapters \
  --checkpoint-manifest packages/omlx-model-qwen38/release-checkpoints.json \
  --allow-non-production-key

python scripts/model_adapter_release.py verify \
  --catalog dist/model-adapter-release/catalog.json \
  --public-key ai2apps-repository-public.pem \
  --artifacts-dir dist/model-adapter-release \
  --fingerprint <pinned-fingerprint>
```

The `build` command checks the signing key against the pinned AI2Apps
fingerprint by default and fails before writing a catalog if it differs.
`--allow-non-production-key` is reserved for the explicitly labelled CI/local
preview path. Publication copies the verified payload and every referenced
wheel into a new immutable AI2Apps release directory, signs the payload on the
host, verifies it against the pinned public fingerprint, and only then advances
the `current` catalog pointer.

`release-checkpoints.json` is keyed by the exact adapter release and is itself
embedded in the signed catalog:

```json
{
  "omlx-model-qwen38@0.1.0": [
    {
      "source": "huggingface",
      "repoId": "unsloth/Qwen3.8-27B-NVFP4",
      "revision": "16b6615af3548b88e2d8e382457bc705b00479cf",
      "displayName": "Qwen3.8 27B NVFP4",
      "estimatedSizeBytes": 23444511709
    }
  ]
}
```

Do not add a checkpoint recommendation based only on its config file. Its
pinned revision must first pass full loading, first-token, text/image inference,
and memory validation on supported hardware.

For subsequent releases, build into the existing release directory and pass
its current `catalog.json` as `--previous-catalog`; the metadata version must
increase. Existing package/version bytes are immutable. Catalog publication
must happen after its referenced wheels and `repository-key.json` have been
uploaded.

`.github/workflows/model-adapter-release.yml` runs the same build and
verification path with an ephemeral CI key. Its downloadable artifact is a
non-production preview and never contains the generated private key. Production
signing and hosting remain a separately authorized deployment step.
