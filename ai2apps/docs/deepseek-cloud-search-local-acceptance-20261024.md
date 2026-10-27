# DeepSeek Cloud Search Local acceptance — 2026-10-24

Local integrates the published Cloud OpenAPI 1.78.0 contract through existing Device/actor authorization. No Cloud code was modified.

## Behavior

- Official configured DeepSeek BYOK has priority. Confirmation pins the selected route; a BYOK failure never silently switches to paid Cloud.
- Without BYOK, available Cloud capability exposes DeepSeek in Desktop/Mobile Search All and AaAT. Cloud requires explicit consent to the quoted price/version and maximum charge before dispatch. Capability/policy failures remain unavailable.
- Runtime privacy/offline mode and Task privacy profile block external DeepSeek calls. Keys and Device authorization remain backend-only.
- Immutable receipt-scoped request IDs are persisted before the single POST. Interrupted/unknown requests recover by GET of the same ID, without a second POST or another provider. Read/cancel/delete verify owner, Installation and Task scope. Deleting results preserves billing metadata and does not imply a refund.
- Fast preparation can use the user's query directly without a planning LLM call. Cloud fee confirmation remains a separate explicit action.
- Source progress and final results retain transport and billing metadata. UI fee, privacy and billing labels cover all supported locales.

## Verification

132 targeted Python tests and 12 Chrome checks passed. Chrome exercises 390px and 1100px views, explicit consent/cancel, BYOK availability, immutable repeat submissions and progressive results. Python covers price changes, privacy guards, single dispatch/recovery, cancellation/deletion, ownership and AaAT exact form consent. These provider responses and AaAT executions are fixtures.

All 297 mandatory AaAT boundary checks passed in 145.71 seconds, exit 0; an existing headless Metal atexit warning follows successful completion.

## Live production acceptance

User explicitly authorized the current account for at most 1 Point. In the native App-Dev UI, with no official BYOK configured, the public query `DeepSeek` used the no-LLM fast preparation. The UI showed the 1 Point confirmation before dispatch. After explicit acceptance, five search results appeared. Cloud reported `completed`, `points_charged: "1"`, `billing_status: "charged"`, price version `deepseek-search-v1-20261024`.

- Browser Task: `btask_f3bc5c85cc769a65b6c8a7583a2753b1f08c58081103f1a4390ed8828aa7aa29`
- Run: `run_40021058fba64bca926e2189c44609c4`
- Cloud request: `search-688d16a3951cb048a3fe31befa8979299c0456df986d84f3`
- Local log: POST at 03:00:37 UTC and one explicit GET status read at 03:00:55 UTC on 2026-10-24. The GET retained the same charge and result identity.

Total authorized live expenditure: exactly 1 Point. No second paid search or planning/summarizing LLM call was made. No live cancellation/deletion was performed on the user's result. Physical iPhone Safari and a real paid Agent conversation remain unverified; Mobile viewport and AaAT fixture tests use the shared production paths.

Both fixed Dev and App-Dev were checked idle and restarted via their own standard Helpers. App/Helper source metadata and actual running workflow module paths match the live checkout. Dev PID55839/port65383 and App-Dev PID55840/port65385 return health 200; all three changed shared JS assets byte-match source in both instances. Static Package assets are authenticated; native App-Dev rendering provided live UI evidence. Test and production Desktop were not replaced or published.
