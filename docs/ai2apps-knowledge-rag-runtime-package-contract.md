# AI2Apps Knowledge RAG Runtime Package Contract

Status: MVP implementation contract v0.1.1
Last updated: 2026-08-26

## 1. Package split

Knowledge and SQLite FTS5 remain part of Core. Semantic retrieval is installed through ACPF as a
trusted component stack:

```text
ai2apps/runtime-knowledge-rag
  native Runtime Provider; Python + LanceDB + Arrow + MLX text dependencies; no App or Tool

ai2apps/service-knowledge-lancedb
  thin managed Worker; VectorIndexBackend RPC; depends on the exact RAG Runtime generation

ai2apps/model-multilingual-e5-small
  thin Embedding Provider/Model Package; runs from the exact Knowledge RAG Runtime generation

Knowledge RetrievalProfile
  SQLite FTS5 + LanceDB vector + RRF; authoritative ACL recheck in Core
```

The Runtime Provider is analogous to `ai2apps/runtime-omlx`: its outer `.ai2service` contains only
signed metadata and a platform variant payload. It does not expose Tools and is not launched as a
normal Service. The Host verifies and materializes the native payload; only a locked dependent Worker
can execute its Python and libraries.

## 2. Runtime Provider manifest

Target outer manifest:

```yaml
schema: ai2apps.service/v1
id: ai2apps.runtime.knowledge-rag
name: AI2Apps Knowledge RAG Runtime
version: 0.1.0
publisher: {id: ai2apps}
runtime:
  mode: process
  protocol: ai2apps-native-runtime/v1
  role: knowledge_backend_provider
  descriptor: META/runtime-manifest.json
capabilities: [knowledge-runtime-v1, lancedb, arrow, vector-f32]
permissions: {network: {outbound: false}}
compatibility: {os: [macos], architectures: [arm64]}
variants:
  - id: darwin-arm64
    files: [variants/darwin-arm64/AI2AppsKnowledgeRAGRuntime.dmg]
tools: []
models: []
```

The descriptor uses immutable package identity, signed payload digest, Python home, framework
site-packages and launcher paths. The final DMG must pass the same Developer ID, Hardened Runtime,
notarization/stapling, Gatekeeper, Team ID and clean-device checks as the oMLX Runtime.

## 3. Vector Worker contract

`ai2apps/service-knowledge-lancedb` is a normal managed Service Package with a required dependency on
`ai2apps.runtime.knowledge-rag`. Its dependency lock selects the exact Runtime digest. The Host starts
the Worker with the resolved Runtime Python; it must never fall back to Host site-packages.

MVP operations:

```text
health
upsert
delete
search
count
```

Every search request carries installation, actor, visibility and selected bucket constraints, which
LanceDB applies as prefilters. Bucket membership edits advance the authoritative item change log so
the rebuildable vector metadata stays current. Returned Item IDs remain untrusted proposals: Core
always rechecks visibility, status, tags and current bucket membership in Platform SQLite. Durable
shadow-generation create/validate/activate/drop operations remain the next migration increment; the
MVP generation name is versioned and the index is fully rebuildable.

## 4. ACPF lifecycle

Opening Knowledge performs only `probe(knowledge.semantic_retrieval)`. Clicking “Enable semantic
search” performs `ensure`, displays the exact Runtime, Worker, Embedding Provider and checkpoint, then
creates a durable Provisioning Session after the user selects a profile. Confirmation installs and
verifies components in dependency order.

Successful setup returns to Knowledge with `configure_only`; index construction runs as a resumable
derived-data job. It builds a shadow generation and activates it only after count, ACL, delete and
retrieval validation. Until activation, and whenever the Runtime is missing or degraded, retrieval
remains FTS5-only.

## 5. MVP implementation status

Implemented and verified on macOS arm64:

- native Runtime resolution is generalized to `ai2apps-native-runtime/v1` roles;
- managed Workers resolve `runtime.provider` and never fall back to Host site-packages;
- the slim `knowledge-rag` dependency layer builds independently from the full oMLX layer;
- LanceDB Worker and E5 Embedding Provider expose loopback HTTP services managed by Package Supervisor;
- the pinned `multilingual-e5-small-mlx` checkpoint produces 384-dimensional normalized embeddings;
- Knowledge change-log replay indexes text incrementally and hybrid retrieval uses FTS5 + vector RRF;
- Core performs authoritative ACL/bucket recheck and degrades safely to FTS5 on any semantic error;
- ACPF resolves the three Packages plus checkpoint and reports the profile ready.

The real local smoke installs the stack into an isolated AI2Apps base path and validates upsert,
filtered search, delete, embeddings, hybrid retrieval and ACPF readiness. The slim Runtime is about
676 MB unpacked / 194 MB as the local development `.ai2service`, versus about 1.7 GB for the generic
full MLX layer.

Production release still requires official Publisher signing, Developer ID Hardened Runtime,
notarization/stapling, clean-device Gatekeeper verification and Registry publication. The Platform now
persists per-profile index watermarks and runs catch-up in a retryable background worker while FTS5
remains immediately available. Shadow-generation migration, uninstall retention UI and storage
accounting remain post-MVP hardening and must not disable Knowledge Core or FTS5.
