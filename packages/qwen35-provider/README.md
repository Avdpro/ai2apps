# Qwen3.5 Model Provider Package

This is a standalone AI2Apps Service Package for Qwen3.5 on Apple Silicon.
It exposes OpenAI-compatible Chat Completions and Responses endpoints while
reusing the optimized Qwen3.5 engine shipped by the installed AI2Apps runtime.

The Package does not contain model weights and does not download them itself.
The Host resolves the Package's published Checkpoint Distribution IDs, acquires
and verifies the selected checkpoint, and grants the resulting read-only path
through `AI2APPS_MODEL_CHECKPOINTS_JSON`.

Included model profiles:

- `ai2apps.qwen35/qwen3.5-2b-4bit` (default)
- `ai2apps.qwen35/qwen3.5-0.8b-4bit` (lightweight validation profile)

Build a Contract v1 release artifact with the standard signed Registry builder:

```bash
python scripts/build_signed_registry_release.py \
  --source packages/qwen35-provider \
  --output dist/ai2apps.model.qwen35-0.1.2.ai2service \
  --publisher-id "$PUBLISHER_ID" \
  --publisher-key-id "$PUBLISHER_KEY_ID" \
  --keychain-secret "$PUBLISHER_KEY_SECRET" \
  --keychain-namespace "$KEYCHAIN_NAMESPACE"
```

The publisher private key remains in the configured secret backend and is not
stored in this source directory.

To verify the exact install path (trusted local publisher registration,
managed-process sandbox, model catalog discovery, HF cache reuse, Metal load,
OpenAI request, and shutdown), run:

```bash
python scripts/smoke_qwen35_provider_package.py
```

The smoke test defaults to the 0.8B checkpoint so it does not disturb a larger
resident model. Pass `--repository mlx-community/Qwen3.5-2B-4bit` to exercise
the default Package profile.
