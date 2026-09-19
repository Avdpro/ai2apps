# AI2Apps oMLX Runtime 1.7.3 Chat metrics / Engine Boost

Date: 2026-09-19 (Asia/Shanghai)

## Status

Candidate built and Developer ID signed; Apple accepted.
Apple submission: `6212d14b-20c5-4460-933d-6c39f3ca77b5`.
Staple, staple validation and Gatekeeper passed.
Published to Cloud Registry. App-Dev and Test rebuilds are in progress.

The user authorized Apple notarization and current Dev Cookie access only for
`ai2apps/runtime-omlx 1.7.3`. The standard publication script could not read
the exact running Dev Profile because SQLite reported `database is locked`.
Installation-session Publisher lookup also requires an active user session.
The standard tool now supports explicit `--browser-live` via authenticated
BiDi. With Dev Local/Shell running, Publisher and submission queries passed
without SQLite access or shutting down the App. The original Publisher key
remains active with matching fingerprint. No 1.7.3 submission was listed.
Cloud submission `99416633-5c2f-477a-9c8d-f4b986ace281` is published; review
`09829510-5529-4cea-a805-476759b946bb`, Repository metadata version 162.
The complete submit/review/publish flow succeeded with `--browser-live` while
Dev Shell stayed running. No Cookie value was logged or written to disk.

Signed Package: `packages/ai2apps-runtime-omlx/dist/ai2apps-runtime-omlx-1.7.3-production.ai2service`.
SHA-256 `873eceadb745d8009145c03ca0c3cee3dacab019ed0360672caab197f86370be`,
371786272 bytes. Exact signed Runtime + published Qwen3.8 0.3.2 installed in
an isolated temporary smoke instance, dependency lock selected 1.7.3 and
the managed Worker reached running. This is not a real inference throughput test.

## Scope and candidate

- Repository HEAD: `8ff6faf966d56ae92d21bf2d36d9512da5745784` (dirty worktree).
- Frozen source: `artifacts/runtime-1.7.3/source/` copied from the published,
  signed Runtime 1.7.2 payload; only `ai2apps/model_worker/omlx_chat.py`,
  `ai2apps/model_worker/server.py`, and `omlx/server.py` are overlaid.
- No model Package or checkpoint changes; no experiment sources added.
- Final streaming usage provides native throughput when available and marks
  Worker-observed estimates otherwise. Worker boost controls only the loaded
  model through the authenticated control endpoint, outside generation queues.
- Host Package capability and forwarding changes still require updated Local
  code in App-Dev/Test/Desktop, in addition to installing this Runtime.
- Standard builder: `scripts/build_omlx_runtime_dmg.py`, `packaging/_export`,
  explicit frozen `--runtime-source-root`, existing Developer ID Team
  `84XL5V265N`.
- Internal DMG: `artifacts/runtime-1.7.3/AI2Apps-oMLX-Runtime-1.7.3-internal.dmg`
- Bytes: `373974663`
- SHA-256: `f3cc12315b33d8725675c3b2f7998da4d58b3602f390e6877562d055309c4823`
- Deep/strict inner codesign, DMG integrity, and outer signature: passed by
  the standard builder.
- Chat Adapter, Provider, Worker, Chat UI, Runtime Package tests: 109 passed.

## Remaining acceptance

Anonymous production verification passed: Repository metadata 162, exact
artifact bytes/size/SHA-256 and exact Publisher envelope JSON. The 1.7.3
release currently uses Cloud only. ModelScope/GitHub replication and independent
source activation review remain pending; this is a temporary distribution
exception, not a completed three-source acceptance claim.

Fixed App-Dev and Test were rebuilt through their prescribed scripts. Both
passed `verify-release-app.sh` during construction and independent
`codesign --verify --deep --strict`. Previous Apps were archived as
`AI2Apps-app-dev-20260919-002557.app` and `AI2Apps-test-20260919-002601.app`.
No instance data was reset/copied. App-Dev identity/source mount/cloud Runtime
profile are correct; live title is `AI2Apps-App-Dev: App-Dev 127.0.0.1:60766`.
Test identity is `com.ai2apps.desktop.test` / `test`, live port 60767.

App-Dev Discover downloaded and verified 1.7.3; its `Review and continue`
button directly resumed installation rather than opening a separate review
dialog. This was clicked by the agent, not a separate user approval; do not
count it as user-performed audit acceptance. Discover then showed installation
complete (100%), Local 1.7.3 / Cloud 1.7.3, and the standard Restart Local action
was invoked. Test is awaiting user login.
Live Chat/Rush verification and multi-source acceptance remain incomplete.
