# Qwen3.5 Model Provider Package

This is a standalone AI2Apps Service Package for Qwen3.5 on Apple Silicon.
It exposes OpenAI-compatible Chat Completions and Responses endpoints while
reusing the optimized Qwen3.5 engine shipped by the installed AI2Apps runtime.

The Package does not contain model weights. It first resolves an existing
Hugging Face cache entry and downloads into Package-owned data only when the
checkpoint is missing. HF cache access is read-only and requires the explicit
`model_weights.huggingface_cache: read` permission.

Included model profiles:

- `ai2apps.qwen35/qwen3.5-2b-4bit` (default)
- `ai2apps.qwen35/qwen3.5-0.8b-4bit` (lightweight validation profile)

Build the local development artifact with:

```bash
python scripts/build_model_provider_package.py packages/qwen35-provider
```

The generated archive is written to `dist/`. A publisher private key is never
stored in this source directory; pass one explicitly for a stable release
identity, or let the build command create an ephemeral local-test key.

To verify the exact install path (trusted local publisher registration,
managed-process sandbox, model catalog discovery, HF cache reuse, Metal load,
OpenAI request, and shutdown), run:

```bash
python scripts/smoke_qwen35_provider_package.py
```

The smoke test defaults to the 0.8B checkpoint so it does not disturb a larger
resident model. Pass `--repository mlx-community/Qwen3.5-2B-4bit` to exercise
the default Package profile.
