# AI2Apps release gate

The release gate binds every supported engine to an immutable Hugging Face
checkpoint revision, a checksummed Scope Pack, and a named conversion format.
It deliberately separates static/package checks from real Metal inference
evidence: a package cannot claim inference validation merely because its files
are present.

## Preflight

Run the source/package checks before building a release:

```bash
ai2apps-release-gate \
  --mode preflight \
  --run-tests \
  --archive dist/ai2apps-0.1.0.dev2-py3-none-any.whl \
  --archive dist/ai2apps-0.1.0.dev2.tar.gz \
  --json artifacts/release-gate/preflight.json \
  --markdown artifacts/release-gate/preflight.md
```

This verifies all catalog commit pins, Scope Pack hashes and compatibility,
package contents, publishable dependency metadata, and the focused release
tests. Public archives must use index-resolvable dependencies only; a
`Requires-Dist` entry containing a Git or HTTP URL fails the gate.

The source checkout still resolves the reviewed MLX ecosystem commits through
`[tool.uv.sources]`. Those development-only source overrides are deliberately
not copied into wheel metadata. The first public wheel therefore installs
`mlx-lm`, `mlx-vlm`, `mlx-embeddings`, and the optional `mlx-audio` extra from
PyPI. The reviewed DFlash fork remains in the source development group until a
compatible index release exists; it is not required by the three AI2Apps
release engines.

## Installed-model gate

```bash
ai2apps-release-gate \
  --mode installed \
  --model-dir /path/to/models \
  --json artifacts/release-gate/installed.json
```

Each installed model must have a version-2 `ai2apps-model.json` recording the
exact source commit, conversion variant, Scope Pack version/hash, and expert
store. Older installs remain discoverable by the runtime, but do not pass a
reproducible release gate until they are re-prepared.

## Real Metal release gate

Generate the evidence skeleton first:

```bash
ai2apps-release-gate \
  --write-evidence-template artifacts/release-gate/evidence.json
```

Populate it from the checked-in Metal benchmark scripts, then run:

```bash
ai2apps-release-gate \
  --mode release \
  --model-dir /path/to/models \
  --evidence artifacts/release-gate/evidence.json \
  --json artifacts/release-gate/release.json \
  --markdown artifacts/release-gate/release.md
```

The full gate requires, for all three release models:

- the exact pinned checkpoint revision;
- exact Top-10, long-decode (at least 1024 tokens), and multi-turn parity;
- a zero-miss static-oracle run;
- static-oracle TPS of at least 85% of the unchanged full-resident engine;
- lower cache-engine memory than the full-resident engine;
- for Qwen, parity across all three engines and with Auto L1 enabled.

`deployed_tps` is recorded separately from the static-oracle performance gate.
It describes real cache/SSD behavior and is not expected to reach 85% in a
cold or miss-heavy workload.

The 2-bit DeepSeek checkpoint has an immutable catalog pin but must remain
failed/pending in full-release evidence until it has been downloaded, converted,
and exercised on a real Metal device.
