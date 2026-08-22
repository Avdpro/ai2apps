# AI2Apps oMLX Runtime

Official `inference_provider` Service Package for macOS arm64. It owns CPython,
MLX/oMLX, the Model Worker framework, Cached-MoE implementations, and all
native inference libraries. It contains no checkpoint or instance data.

Build a local ad-hoc development artifact:

```bash
AI2APPS_ALLOW_DEVELOPMENT_RUNTIME=1 \
  .venv/bin/python scripts/build_omlx_runtime_package.py \
  --source packages/ai2apps-runtime-omlx \
  --layers packaging/_export \
  --sign-identity -
```

For a release artifact, first run `scripts/build_omlx_runtime_dmg.py` with the
AI2Apps Developer ID Application identity. The release flow is deliberately
two-phase: notarize and staple that DMG, then pass it to the Package builder with
`--prepared-dmg --prepared-signing developer-id --team-id 84XL5V265N` while
signing the outer Package with the official AI2Apps Publisher key. An
unstapled Developer ID DMG is never accepted into a release Package.
