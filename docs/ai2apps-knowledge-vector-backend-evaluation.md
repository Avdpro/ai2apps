# AI2Apps Knowledge Vector Backend Evaluation

Status: K6A harness implemented; native-runtime matrix pending
Last updated: 2026-08-26

## Current result

LanceDB remains the first candidate for AI2Apps semantic retrieval. The adapter and repeatable
benchmark harness are implemented without adding LanceDB to the Core Host dependency graph. The
current development environment does not contain LanceDB, so performance, packaging, signing and
cross-platform acceptance are not yet claimed.

Implemented safeguards:

- LanceDB imports lazily and is intended to execute only in an isolated `.ai2service` Worker;
- every row carries installation, owner, visibility and bucket metadata;
- vector search uses an ACL prefilter before nearest-neighbour calculation;
- every semantic candidate is rechecked against authoritative Platform SQLite before fusion;
- backend absence or failure falls back to SQLite FTS5;
- upsert uses stable Chunk IDs and indices remain disposable/rebuildable;
- lexical and semantic ranks use reciprocal-rank fusion rather than backend-specific scores.

## Reproducible command

```bash
.venv/bin/python scripts/bench_knowledge_vector_backend.py \
  --chunks 10000 --dimension 384 --queries 100 \
  --output artifacts/knowledge-backend-spike/local/10k-384.json \
  --require-ready
```

Repeat for 10k, 100k and 1M chunks and 384, 768 and 1024 dimensions. Results must be generated in
the isolated Runtime environment that will be packaged for users, not by installing native LanceDB
libraries into the AI2Apps Host environment.

## Remaining acceptance matrix

- macOS arm64 and Linux arm64/x86_64, Python 3.11–3.13;
- signed Runtime Package, macOS notarization/stapling and clean-device installation;
- cold import time, installed bytes, RSS and offline startup;
- incremental upsert/delete, restart and concurrent read/background indexing;
- private/shared/bucket adversarial filters and stale-row tests;
- generation rebuild, shadow activation and crash recovery;
- filtered Top-20 p95 target of 150 ms at 100k chunks;
- Apache-2.0 NOTICE, SBOM, package digest, upgrade and rollback verification.

LanceDB must not become the default semantic backend until this matrix passes. Failing the matrix
does not affect the Knowledge authority or FTS5 baseline.
