# AI2Apps Authority and Secret Baseline

AI2Apps uses one deterministic authority path for Agent Tool calls.

## Action risk

Before a Tool is dispatched, its declared effects are classified as `read`,
`write`, `external`, or `destructive`. Approval requests contain a bounded,
redacted action preview with the Tool name, concrete target, reversibility, and
`low`/`medium`/`high`/`critical` risk. Sensitive argument names and
`secret://...` references never expand in the preview or AI auditor request.

## Grant leases

User approval can be scoped to:

- `once`: consumed atomically before one Tool dispatch;
- `run`: the current Agent run;
- `session`: the current conversation Session;
- `agent`: the Agent definition;
- `app`: the current App instance.

Leases may be bound to displayed resource arguments. They expire automatically,
are revocable, stop matching after a Tool service digest changes, and are all
revoked when Safe Mode is enabled.

## Secret Store

Secret metadata is available under `/v1/platform/secrets`. Values are never
persisted in SQLite or returned by an API. A Tool receives a value only when an argument
contains `secret://sec_<id>` and its qualified name matches the secret's
`allowed_tools` patterns.

The runtime selects a provider through `SecretBackendFactory`:

- macOS uses Keychain;
- Linux with a desktop Secret Service uses `secret-tool`;
- headless Linux (including DGX Spark) and other hosts use an AES-256-GCM vault.

`AI2APPS_SECRET_BACKEND` overrides automatic selection. The encrypted provider
accepts `AI2APPS_SECRET_VAULT_KEY`; otherwise it creates a machine-local key with
mode `0600`. TPM, systemd credential, Windows Credential Manager, and KMS
providers can register without changing Secret URIs or Tool code. The selected
provider is visible at `GET /v1/platform/secrets/backend`.

Tool invocation records retain the opaque reference. Injection occurs after
authorization and input validation. Progress, output, and error strings are
redacted against values injected for that invocation.
