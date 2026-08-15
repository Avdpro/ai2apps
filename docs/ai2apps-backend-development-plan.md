# AI2Apps Backend Development Plan

Status: Draft v2.9 — Stabilization active; W9 Coding Harness deferred
Last updated: 2026-08-11
Architecture source: [AI2Apps Platform Architecture](ai2apps-platform-architecture.md)

## 1. Objective

Build AI2Apps from its current oMLX-based model server into a local-first App
and Agent Harness backend without destabilizing the existing inference runtime.

The backend must eventually provide:

- durable App, AppInstance, Thread/Session, Message, Run, Step, and Event state;
- an authoritative asynchronous Agent loop;
- a Service Registry, Service Gateway, and Tool Registry;
- model and MCP capabilities through Service adapters;
- Workspace, Artifact, Process, Web, Memory, and other foundational Services;
- status-line, user input, interactive View, approval, and cancellation
  primitives;
- Session sandboxes, capabilities, ResourceHandles, GrantLeases, and audit;
- installable, signed, auditable, dependency-aware Service/Agent/App packages;
- Apple Silicon/oMLX, NVIDIA/CUDA Linux, and AMD/ROCm Linux backend providers.

Implementation proceeds through small vertical slices. Every milestone must
leave the server runnable, preserve current OpenAI-compatible behavior, and
have an explicit acceptance gate.

## 2. Current baseline

The current repository has these relevant characteristics:

- `omlx.server` owns the FastAPI application, lifespan, model runtime,
  OpenAI-compatible APIs, MCP initialization, and administrative routes;
- the `ai2apps` package is currently a thin product boundary around oMLX plus
  AI2Apps-specific inference/Fusion functionality;
- model management, inference scheduling, streaming, MCP execution, auth, and
  extensive runtime tests already exist;
- there is no SQLite-backed application database in the current checkout. The
  only `sqlite` match in runtime configuration is an example external MCP
  server command;
- durable server state currently uses several purpose-specific stores:
  `settings.json`, model settings/profile/template JSON files, bounded
  per-response JSON records, metric JSON, and model/package files;
- current Chat thread/history state is browser-owned `localStorage`, not a
  backend database;
- no authoritative AI2Apps App/Agent/Session persistence or general Tool
  Runtime exists yet;
- the WebUI is being separated into `ai2apps/web`; backend work must avoid
  depending on unfinished UI implementation;
- the worktree contains ongoing product/UI and inference experiments, so
  backend changes must stay isolated under `ai2apps` and avoid unrelated files.

The plan therefore adds a new AI2Apps platform layer beside oMLX and integrates
it through narrow adapters. Existing model, router, cache, scheduler, and kernel
code is not moved merely to satisfy the new architecture.

### 2.1 Reuse-first inventory

Before implementing each milestone, classify existing behavior as **reuse**,
**wrap**, **migrate**, or **replace**. “New AI2Apps abstraction” does not mean
“new implementation” when the current implementation already satisfies the
contract.

| Existing capability | Location | Plan |
| --- | --- | --- |
| FastAPI app and lifespan | `omlx.server` | Reuse; mount one AI2Apps router and attach one PlatformRuntime lifecycle |
| API-key authentication | `omlx.server.verify_api_key`, admin auth | Reuse initially through FastAPI dependencies; extend later for user/package identity |
| Base/data path and hierarchical configuration | `omlx.settings` | Reuse path resolution and settings; put the platform DB/artifacts under the same resolved data root |
| Global and model settings persistence | `omlx.settings`, `omlx.model_settings` | Reuse existing versioned/atomic JSON stores through adapters; do not migrate stable settings into SQLite without need |
| EnginePool, scheduler, memory guard, model load/unload | oMLX runtime | Reuse unchanged behind Model Runtime Service adapter |
| In-process model ownership registry | `omlx.model_registry` | Reuse for engine ownership; do not confuse it with the durable Service Registry |
| MCP connections, discovery, execution, timeout, parallel limit | `omlx.mcp` | Reuse behind MCP Service/Tool adapters; add Session identity, policy, audit, and cancellation around it |
| Tool-call parsing and OpenAI/Anthropic formatting | `omlx.api` adapters/parsers | Reuse where model-format compatible; normalize into AI2Apps ToolCall/ToolResult contracts |
| OpenAI Responses previous-response store | `omlx.api.responses_utils.ResponseStore` | Preserve for API compatibility; optionally import/link records, but do not use its bounded JSON store as the Session database |
| SSE formatting and benchmark progress streams | `omlx.api.adapters`, admin benchmark routes | Reuse format/header/heartbeat lessons; replace in-memory replay logs with a durable Event Store for Harness semantics |
| Atomic JSON writes | settings, profiles, metrics, response records | Reuse for their current bounded configuration/statistics roles |
| Chat history and UI preferences | `ai2apps/web` localStorage | Migrate thread/message state to backend Sessions; retain device-local presentation preferences where appropriate |
| MarkItDown, audio, embedding, reranking, downloaders | existing oMLX APIs/runtime | Wrap as built-in Service capabilities before considering replacement |
| SQLite App/Agent/Session/Event storage | not present | Add once as the shared AI2Apps transactional platform database |

The target is one AI2Apps platform database per resolved installation/data
root, not one database per App or Service. Services may own private databases
only when their package contract requires independent internal state; those
databases are not substitutes for the shared control-plane/session database.

### 2.2 Storage coexistence rule

SQLite becomes the source of truth for relational, transactional Harness state:
Apps, instances, Sessions, Messages, Runs, Steps, semantic Events, installed
packages, capabilities, Grants, ResourceHandles, and Artifact metadata.

Existing JSON stores remain authoritative for the oMLX settings they already
own. The AI2Apps database references their logical objects through adapters and
stable IDs rather than duplicating their complete content. Migration into the
database is justified only when a feature needs cross-object transactions,
queries, ownership, or durable event ordering that the current store cannot
provide.

## 3. Implementation principles

1. **One authoritative backend.** Web, native, CLI, and future remote clients
   use the same APIs and event stream.
2. **Contract before orchestration.** Persisted schemas, IDs, state machines,
   events, and tool contracts are fixed before building a complex Agent loop.
3. **Semantic events are replayable.** Live token deltas may be ephemeral, but
   state transitions, approvals, status, tool results, and final message parts
   must survive restart and reconnect.
4. **Security begins with the first Tool.** Every Tool declares effects and
   capabilities even before the final OS sandbox adapters are complete.
5. **No ambient host authority.** Host paths, credentials, network, processes,
   and external side effects require scoped handles or Grants.
6. **Adapters protect oMLX.** The initial model provider delegates to existing
   oMLX code without rewriting inference internals.
7. **SQLite first, explicit repositories.** Use SQLite transactions and small
   repository interfaces for new Harness state, sharing the existing resolved
   installation data root and lifecycle. Do not rewrite working oMLX JSON stores
   merely for storage uniformity. Avoid a distributed system or a large ORM
   until a demonstrated requirement exists.
8. **Async at the boundary, bounded underneath.** Long work returns a Run or
   Operation ID, supports cancellation, and emits progress. Blocking libraries
   execute through bounded workers.
9. **Backward compatibility is tested.** Existing `/v1/*`, admin APIs, CLI,
   and model tests remain gates during migration.
10. **Backend contracts are hardware-neutral.** MLX, CUDA, ROCm, macOS, and
    Linux details remain behind providers and platform adapters.

## 4. Reference implementation strategy

### 4.1 OpenCode

OpenCode is a useful primary reference because it separates a local server from
its clients, publishes OpenAPI, models sessions/messages as resources, supports
asynchronous prompts and SSE, provides a schema-based Tool Registry, passes
Session context into tools, and applies action/resource permission rules.

AI2Apps should study and adapt these patterns:

| OpenCode pattern | AI2Apps treatment |
| --- | --- |
| Local headless server plus multiple clients | Adopt; AI2Apps FastAPI is authoritative for WebUI, native shell, and API clients |
| OpenAPI-generated client contract | Adopt after the first resource schemas stabilize |
| Session, message, and structured message parts | Adapt to ConversationSession, AgentRun, Step, StatusLine, View, and Artifact |
| REST snapshot plus SSE updates | Adopt with durable replay for all semantic events |
| JSON-schema custom and built-in tools | Adopt behind stable Service-qualified Tool IDs |
| Tool execution receives Session context | Extend with AppInstance, AgentRun, package digest, Sandbox, and CapabilityContext |
| `allow` / `ask` / `deny` action-resource rules | Extend into deterministic policy plus CapabilityRequest and scoped GrantLease |
| MCP tool aggregation | Adopt through `ai2apps.mcp`, preserving provider identity and permissions |
| Child sessions for subagents | Adapt with explicit depth, budget, cancellation, and permission narrowing |
| Coding-specific workspace and shell assumptions | Do not generalize into platform contracts |
| Host-authority shell execution | Do not adopt; Process Service runs inside a Session sandbox |
| Custom tool name replacing a built-in | Do not adopt by default; identity includes signed provider and version |
| Project-wide remembered approval | Replace with explicit, expiring, revocable GrantLease scopes |

OpenCode is MIT licensed. Source-level reuse is legally possible when its
copyright and license conditions are preserved, but AI2Apps should normally use
clean interfaces and independent Python implementations. Any copied or derived
code must be isolated, attributed, reviewed, and recorded in `NOTICE`.

Primary references:

- [OpenCode server architecture and API](https://dev.opencode.ai/docs/server/)
- [OpenCode built-in tools](https://dev.opencode.ai/docs/tools/)
- [OpenCode custom Tool contract](https://opencode.ai/docs/custom-tools/)
- [OpenCode permission model](https://opencode.ai/v2/docs/permissions)
- [OpenCode source repository](https://github.com/anomalyco/opencode)
- [OpenCode MIT license](https://github.com/anomalyco/opencode/blob/dev/LICENSE)

### 4.2 MCP

MCP remains the external tool/context interoperability protocol. AI2Apps is the
host and policy boundary; an MCP server is not automatically trusted merely
because it implements MCP.

Patterns to adopt include capability negotiation, isolated client/server
connections, tool/resource/prompt discovery, JSON Schema inputs, progress
notifications, and stdio/Streamable HTTP transports. AI2Apps adds Session
identity, Sandbox policy, ResourceHandles, audit, and GrantLease enforcement
around MCP calls.

Primary references:

- [MCP architecture](https://modelcontextprotocol.io/specification/2025-06-18/architecture)
- [MCP architecture overview and primitives](https://modelcontextprotocol.io/docs/learn/architecture)
- [MCP official example servers](https://modelcontextprotocol.io/examples)

## 5. Target backend module boundaries

The implementation should grow toward this structure without creating empty
modules prematurely:

```text
ai2apps/
  api/
    router.py
    errors.py
    dependencies.py
    health.py
    sessions.py
    events.py
    services.py
    tools.py
    runs.py
    capabilities.py
    artifacts.py
    apps.py

  storage/
    database.py
    migrations.py
    repositories.py
    schema/

  events/
    models.py
    store.py
    bus.py
    stream.py

  sessions/
    models.py
    repository.py
    service.py

  services/
    models.py
    registry.py
    gateway.py
    client.py
    operations.py
    builtin/
      model_runtime.py
      mcp.py
      workspace.py
      artifacts.py
      process.py

  tools/
    models.py
    registry.py
    executor.py
    results.py

  agents/
    models.py
    registry.py
    runtime.py
    loop.py
    context.py
    interaction.py

  apps/
    models.py
    registry.py
    instances.py
    sessions.py
    builtin/
      chat.py

  sandbox/
    models.py
    policy.py
    capabilities.py
    resources.py
    broker_client.py
    platform/
      macos.py
      linux.py

  artifacts/
    models.py
    store.py

  packages/
    manifests.py
    verification.py
    resolver.py
    audit.py
```

`omlx.server` should eventually call one AI2Apps bootstrap function and mount
one AI2Apps router. It must not import every platform implementation module.

## 6. Initial contracts

### 6.1 ID and time rules

- IDs are opaque, lowercase, prefixed values such as `ses_`, `msg_`, `run_`,
  `step_`, `evt_`, `svc_`, `tool_`, `capreq_`, and `grant_`.
- The first implementation may use UUID4 payloads with a separate ordered
  database sequence; clients must not infer ordering from IDs.
- Stored timestamps are UTC RFC 3339 with microsecond precision.
- API payloads include `schema_version` where durable compatibility matters.
- Mutating API calls accept an idempotency key when replay is plausible.

### 6.2 Durable Event envelope

```json
{
  "event_id": "evt_...",
  "sequence": 1042,
  "type": "agent.run.status.changed",
  "occurred_at": "2026-08-11T12:00:00.000000Z",
  "scope": {
    "app_instance_id": "appi_...",
    "session_id": "ses_...",
    "run_id": "run_..."
  },
  "subject_id": "run_...",
  "schema_version": 1,
  "payload": {}
}
```

Rules:

- the state mutation and its Event are committed in one transaction;
- Event sequences are monotonically increasing per database;
- SSE accepts `Last-Event-ID` or an explicit `after` cursor;
- authorization is checked both when the snapshot is fetched and when Events
  are streamed;
- slow clients have bounded buffers and reconnect through durable replay;
- token/reasoning deltas may use a separate transient channel, but completion
  produces a durable message-part Event.

### 6.3 Tool contract

Every registered Tool has a `ToolDescriptor`:

```text
tool ID and version
provider Service ID and package digest
title and model-facing description
JSON Schema input and output
effect classes
required capabilities
timeout and cancellation behavior
idempotency and retry policy
stream/progress support
result kinds: JSON | text | Artifact | ResourceHandle | View
risk and approval defaults
```

Every invocation receives a `ToolExecutionContext`:

```text
user and installation identity
AppDefinition / AppInstance
AgentDefinition / effective package and Patch digest
ConversationSession / Message / AgentRun / Step
SandboxInstance / CapabilityContext / active GrantLeases
trace ID, deadline, cancellation token, and event emitter
```

Tool output is never an untyped exception or arbitrary stdout. Failures map to
stable typed errors such as `invalid_input`, `permission_required`, `denied`,
`not_found`, `conflict`, `timeout`, `cancelled`, `unavailable`, and
`internal_error`.

### 6.4 Initial persistence schema

The first migrations should cover:

```text
schema_migrations
app_definitions
app_instances
sessions
messages
message_parts
agent_runs
run_steps
events
service_definitions
service_instances
tool_definitions
capability_requests
grant_leases
resource_handles
artifacts
```

Large file content, package archives, model files, and Artifact payloads remain
outside SQLite. SQLite stores metadata, hashes, ownership, paths inside managed
storage, and lifecycle state.

## 7. Delivery milestones

Milestones are dependency-ordered rather than calendar estimates. Each should
be implemented and reviewed as one or more small, independently testable
changes.

### Milestone 0 — Backend seam and contract scaffold

Deliverables:

- create `ai2apps.api`, `ai2apps.storage`, `ai2apps.events`, and shared core
  model/error modules only as required;
- add a single `create_ai2apps_router()` or bootstrap boundary;
- mount it from `omlx.server` without changing inference routes and attach one
  PlatformRuntime to the existing server lifespan;
- add `GET /v1/platform/health` with platform/database schema information;
- derive platform storage paths from the existing resolved base/data path;
- reuse the existing API-key dependency rather than implementing parallel auth;
- ensure the `ai2apps` product entry enables the platform while the legacy
  `omlx` entry remains compatible;
- define API error envelope, ID helpers, UTC clock, and configuration paths;
- add focused backend test directories and fixtures.

Exit gate:

- server starts and shuts down cleanly through both product entry points;
- `/v1/platform/health` works under existing authentication policy;
- existing OpenAI-compatible and model tests show no behavior change;
- no new import from oMLX inference internals into general platform modules.

### Milestone 1 — SQLite, Sessions, Messages, and replayable Events

Deliverables:

- SQLite connection/transaction layer with WAL, foreign keys, busy timeout,
  migration locking, backup-safe paths, and corruption diagnostics;
- one platform database under the resolved installation data root, with no
  per-App database split;
- migrations for AppDefinition, AppInstance, Session, Message, MessagePart, and
  Event;
- Session create/get/list/update/archive APIs;
- Message append/list APIs with structured parts;
- transactional Event Store and in-process notification bus;
- per-Session and global SSE with cursor replay and heartbeat;
- idempotent message creation and optimistic version checks.

Exit gate:

- restart retains all Sessions, Messages, and semantic Events;
- a disconnected client reconnects without gaps or duplicate effects;
- concurrent threads cannot read or mutate each other's records without an
  explicit authorized relationship;
- migration and crash-recovery tests pass.

### Milestone 2 — Singleton Chat App backend

Deliverables:

- seed built-in `ai2apps.general-chat` AppDefinition;
- resolve exactly one Chat AppInstance in the current local-user scope;
- model existing Chat threads as App-owned ConversationSessions;
- implement thread create/list/select/rename/pin/archive/delete semantics;
- designate and reassign the HomeSession/default thread;
- persist Chat collection state separately from thread content;
- add compatibility adapters for existing thread IDs/data when discovered;
- expose generic AppInstance Session APIs plus Chat-friendly route aliases.

Exit gate:

- creating ten threads still yields exactly one Chat AppInstance;
- each thread has independent messages and Session identity;
- archiving/deleting a thread does not close the Chat AppInstance;
- two clients can display different threads from the same instance;
- thread migration is idempotent and rollback-safe.

### Milestone 3 — Service Registry, Tool Registry, and existing adapters

Deliverables:

- ServiceDescriptor, ServiceInstance, ToolDescriptor, and lifecycle state;
- in-memory plus persisted Service/Tool registries;
- Service Client/Gateway dispatch that resolves stable identity rather than
  physical URLs;
- built-in adapter for the existing oMLX model runtime;
- built-in adapter for the existing MCP manager/executor;
- adapters for existing embedding, reranking, audio, and document-conversion
  capabilities where their contracts already satisfy the Service boundary;
- Tool discovery filtered by caller, Agent, Session, policy, and model format;
- schema validation for Tool inputs and outputs;
- no-op/echo diagnostic Tool used only by tests.

Exit gate:

- existing model and MCP implementations can be invoked through Service Client
  without changing their public compatibility APIs;
- duplicate Tool identity, invalid schema, missing Service, timeout, and
  cancellation behavior are deterministic;
- callers cannot spoof a Service or Tool provider ID.

### Milestone 4 — Logical capability policy and approval flow

Deliverables:

- Capability, CapabilityRequest, GrantLease, ResourceHandle, and AuditDecision
  models;
- ordered deterministic policy rules with default deny/ask behavior;
- effects and target resources resolved before a Tool begins;
- `once`, `run`, `session`, `app-instance`, `package-version`, and explicit
  persistent-rule Grant scopes;
- approve, narrow, deny, expire, and revoke APIs;
- `waiting_capability` Run state and durable approval Events;
- independent AI-audit hook interface, initially manual/deterministic only;
- safe behavior when no UI client is connected to answer a request.

Exit gate:

- no Tool side effect occurs before policy resolution;
- a denied or expired Grant cannot be reused;
- changing the effective package/Patch digest invalidates digest-bound Grants;
- pending approval has a deadline and cannot hang a Run forever;
- approval replay is idempotent and auditable.

### Milestone 5 — Workspace and Artifact Services

Deliverables:

- one managed workspace and temporary area per SessionSandbox;
- opaque ResourceHandles for user-selected external files/directories;
- `workspace.list`, `workspace.stat`, `workspace.read`, `workspace.search`,
  `workspace.write`, and `workspace.apply_patch` Tools;
- canonical path and symlink-escape protection;
- Artifact create/list/read/preview/export lifecycle;
- atomic writes, content hashes, quotas, and trash/recovery where practical;
- transactional export through the Host Broker abstraction;
- structured truncation/pagination for large Tool results.

Exit gate:

- one Session cannot address another Session's workspace or handle;
- relative paths and symlinks cannot escape the sandbox root;
- an SVG can be selected, copied into the Session, transformed into an
  Artifact, and exported only after the required Grant;
- cancellation/failure never leaves a partial host export.

### Milestone 6 — Minimal asynchronous Agent Runtime

Deliverables:

- AgentDefinition, EffectiveAgent, AgentRun, RunStep, StatusLine, and AgentView
  persistence;
- model -> tool call -> tool result -> model loop using Model Runtime Service;
- strict Run state machine, maximum steps, token/time/resource budgets, retry
  policy, and repeated-call/doom-loop detection;
- `queued`, `planning`, `running`, `waiting_input`, `waiting_capability`,
  `completed`, `failed`, and `cancelled` states;
- mandatory status-line fallback and progress Events;
- user text/menu/file/approval interaction primitives;
- cancellation propagation through model and Tool calls;
- context assembly and compaction interface;
- per-Session concurrency policy and recovery of interrupted Runs.

Exit gate:

- an Agent can complete a multi-step model/Tool task after server reconnect;
- every Run always has a visible durable status;
- cancelling a Run stops or safely fences all child work;
- duplicate client retries do not create duplicate AgentRuns or side effects;
- an interrupted Run resumes safely or reaches an explicit recoverable state.

### Milestone 7 — Process Service and enforced Session sandbox

Deliverables:

- `process.start`, `process.write_stdin`, `process.status`, `process.logs`, and
  `process.cancel` Tools;
- bounded process count, CPU, memory, output, wall-time, and idle limits;
- environment allowlist and Secret references rather than ambient environment;
- Session workspace as the default working directory;
- common Host Broker protocol;
- first macOS process/filesystem sandbox adapter;
- Linux adapter contract and test double;
- process-tree cancellation and orphan cleanup after restart;
- network default deny with explicit capability mediation.

Exit gate:

- a process cannot access another Session or unauthorized host resource;
- output flooding cannot exhaust server memory or Event storage;
- Run cancellation terminates its process tree;
- broker requests are authenticated, scoped, expiring, and logged;
- third-party executable code remains disabled until this gate passes.

### Milestone 8 — Service lifecycle and package trust

Deliverables:

- embedded, managed-process, and external Service lifecycle implementations;
- health/readiness, logs, operations, restart/backoff, and dependency ordering;
- `.ai2service` parsing, canonical digest, immutable package store, and SBOM;
- signature/publisher trust interface and offline verification;
- dependency solver/lock and platform/accelerator compatibility selection;
- staged install, enable, disable, upgrade, rollback, and uninstall;
- audit attestation storage and local AI audit interface;
- safe failure and rollback across database, filesystem, and processes.

Exit gate:

- package code cannot execute before validation and policy approval;
- failed install/upgrade restores the prior active graph;
- dependents prevent unsafe disable/uninstall;
- source, selected native artifacts, permissions, audit, and signatures are
  inspectable before installation.

### Milestone 9 — Installable Agents, Apps, and local Patch stacks

Deliverables:

- `.ai2agent`, `.ai2app`, and `.ai2patch` canonical formats;
- immutable upstream definitions and ordered device-signed local Patches;
- EffectiveAgent/EffectiveApp assembly and cache;
- install, enable, disable, upgrade, rollback, and uninstall control plane;
- App Entry/Mini-Entry registration and View bridge contracts;
- multiple/singleton AppInstance enforcement;
- state-schema migration snapshots and atomic activation;
- three-way Patch rebase workspace and explicit conflict state;
- unpatchable Safe Mode recovery controls.

Exit gate:

- an upstream upgrade cannot silently discard or reinterpret a local Patch;
- conflicted or unaudited effective definitions do not activate;
- App state migration succeeds for all instances or rolls back atomically;
- Safe Mode can disable Patches and restore built-ins without normal App UI.

### Milestone 10 — Additional foundational Services

Implement as independent packages in this priority order:

1. Web Fetch/Search Service;
2. Memory/Retrieval Service;
3. Browser Service;
4. remaining Document conversion/rendering capabilities not covered by the
   existing MarkItDown path;
5. Job/Schedule Service;
6. Media Service;
7. notification and external connector Services.

Each Service must use the same Tool, progress, cancellation, capability,
ResourceHandle, audit, packaging, and lifecycle contracts. A Service is not
promoted to built-in merely because a single App needs it.

Exit gate for each Service:

- contract and capability review;
- isolated unit and integration tests;
- bounded resource and output behavior;
- cancellation and restart behavior;
- no Session data leakage;
- package/audit/install test fixture.

### Milestone 11 — Hardware-neutral model providers and Linux qualification

Deliverables:

- normalized HardwareProfile and shared-memory pressure accounting;
- formal ModelBackendProvider conformance suite;
- preserve oMLX as the Apple Silicon reference provider;
- NVIDIA/CUDA Linux provider package;
- AMD/ROCm Linux provider package;
- Linux Host Broker/sandbox enforcement implementation;
- package compatibility matrix for OS, architecture, driver, runtime, and
  native dependencies;
- cross-provider API, cancellation, memory-pressure, and failure tests;
- documented performance gates for each supported device family.

Exit gate:

- Apps and Agents run unchanged across providers;
- model identity and compatibility failures are explicit;
- memory admission uses reported live capacity rather than hard-coded RAM/VRAM;
- platform safety and lifecycle tests pass on each qualified Linux target.

## 8. Initial API slice

The first implementation cycle should expose only the endpoints needed for
Milestones 0–2:

```text
GET    /v1/platform/health

GET    /v1/apps/ai2apps.general-chat/instances/default
GET    /v1/app-instances/{instance-id}/sessions
POST   /v1/app-instances/{instance-id}/sessions
GET    /v1/app-instances/{instance-id}/sessions/{session-id}
PATCH  /v1/app-instances/{instance-id}/sessions/{session-id}
DELETE /v1/app-instances/{instance-id}/sessions/{session-id}

GET    /v1/sessions/{session-id}/messages
POST   /v1/sessions/{session-id}/messages
GET    /v1/sessions/{session-id}/events
GET    /v1/events
```

Deletion initially means a retained soft-delete/archive transition. Permanent
destruction and retention policy are separate administrative operations.

## 9. Agent Runtime execution contract

The initial loop is deliberately linear and observable:

```text
accept user message
-> create/idempotently resolve AgentRun
-> assemble context and visible Tool catalog
-> set status-line
-> call Model Runtime Service
-> persist completed text/reasoning/tool-call parts
-> evaluate Tool capability
   -> deny and return typed result
   -> wait for input/approval
   -> execute Tool with deadline and cancellation
-> persist Tool result and Events
-> repeat within budgets
-> complete, fail, cancel, or suspend explicitly
```

Graph workflows, speculative multi-agent execution, autonomous background
planning, and distributed queues are deferred. Agent-to-Agent invocation first
uses the same child-Session/Run primitives with explicit depth and budgets.

## 10. Concurrency, recovery, and consistency

- A Session has an explicit active-Run policy; the first release may serialize
  mutating Runs per Session while allowing independent Sessions in parallel.
- Each Run/Step transition uses compare-and-swap versioning or an equivalent
  transactional guard.
- Tool calls have stable call IDs and settlement records. A recovered loop
  never blindly repeats an unknown external side effect.
- Internal read-only Tools may be retried according to descriptor policy.
- External/mutating Tools require idempotency support or enter
  `needs_reconciliation` after ambiguous failure.
- Run cancellation is durable and checked before every model/Tool boundary.
- Event publication occurs after commit; notification loss is repaired through
  the durable Event cursor.
- SQLite writes use short transactions. Model inference, network calls, and
  process execution never hold database transactions open.

## 11. Security gates

The following features remain disabled until their corresponding gate exists:

| Feature | Required gate |
| --- | --- |
| Third-party Tool with side effects | Tool schema validation plus logical capability policy |
| External file access | ResourceHandle plus explicit GrantLease |
| Host file mutation/export | transactional Host Broker operation |
| Third-party process Service | enforced process/filesystem/resource sandbox |
| Outbound network | destination-scoped network capability |
| Secret use | non-exportable Secret reference and brokered injection |
| Package installation | digest, file-index, source inspection, dependency, permission, and signature verification |
| AI auto-approval | independent auditor, bounded policy, evidence, timeout, and fail-closed behavior |

## 12. Test strategy

### Contract tests

- JSON schemas and OpenAPI snapshots;
- stable error codes and state-machine transition tables;
- Tool descriptor and capability vocabulary;
- Event backward/forward compatibility fixtures.

### Repository and migration tests

- fresh database, every supported upgrade path, rollback, backup, corruption,
  and concurrent access;
- foreign-key ownership and cross-Session isolation;
- idempotent commands and optimistic concurrency.

### Runtime tests

- model/Tool loop, user input, approval, cancellation, retry, timeout,
  compaction, restart, and ambiguous external failure;
- SSE reconnect, cursor replay, heartbeat, slow client, and bounded memory;
- multi-thread Chat with one AppInstance.

### Security tests

- path traversal, symlink escape, stale handle, forged Grant, digest change,
  expired Grant, confused deputy, secret exfiltration, and network denial;
- process tree escape, output flooding, resource exhaustion, and orphan cleanup;
- malicious package archive and dependency-confusion fixtures.

### Compatibility tests

- existing oMLX model load/inference/streaming and MCP suites;
- existing OpenAI-compatible routes and clients;
- `ai2apps` and legacy `omlx` CLI entry points;
- macOS and qualified Linux provider matrices.

### Performance gates

- Event append and replay latency;
- SQLite contention with concurrent Sessions;
- SSE memory per client and bounded slow-consumer behavior;
- Tool dispatch overhead;
- Agent loop overhead excluding model time;
- no material regression to full-resident oMLX model TPS/memory gates.

## 13. Observability

Every request, Run, Step, Tool call, Service invocation, broker operation, and
Event carries a trace ID plus applicable AppInstance/Session/Run IDs.

Minimum metrics:

```text
active Sessions and Runs
Run queue/wait/execution duration
model and Tool call duration/errors/cancellation
pending approvals and approval age
Service readiness/restarts/queue depth
Event append/replay lag and SSE clients
SQLite busy time and transaction failures
workspace/artifact quota usage
sandbox violations and revoked Grant use
model memory reservation and live pressure
```

Logs never include secret values, raw authorization tokens, or unrestricted
user file contents. Audit records and operational logs are separate retention
classes.

## 14. Step-by-step execution protocol

For each milestone:

1. inventory overlapping oMLX/AI2Apps capabilities and record each decision as
   reuse, wrap, migrate, replace, or genuinely new;
2. select the smallest vertical slice and record its exact acceptance tests;
3. inspect overlapping user changes before editing;
4. add contracts and failing tests;
5. implement the minimum backend behavior behind the AI2Apps boundary;
6. run focused tests, then relevant oMLX compatibility tests;
7. inspect API schema and replay/restart behavior;
8. update architecture/decision records when implementation changes a contract;
9. stop at the milestone gate and review before expanding scope.

Do not combine a new persistence model, Agent loop, package manager, and OS
sandbox into one change. The system should remain demonstrable after every
slice.

## 15. First implementation slice

**Milestone 0A: backend seam is complete.** Its implementation consists of:

```text
ai2apps/api/router.py
ai2apps/api/health.py
ai2apps/api/errors.py
ai2apps/config.py
tests/test_ai2apps_platform_health.py
```

Scope:

- implement an AI2Apps APIRouter and health response;
- mount it once from `omlx.server`;
- expose product/runtime/database-schema placeholders without opening a
  database yet;
- verify authentication and both CLI entry modes;
- make no changes to model execution, MCP behavior, or WebUI.

Acceptance evidence:

- the standalone platform contract, embedded configuration, existing API-key
  authentication, OpenAPI publication, and stable error envelope are covered
  by `tests/test_ai2apps_platform_health.py`;
- the focused platform tests and the existing authentication, status, and
  AI2Apps product and CLI compatibility suites pass (59 tests total), and the
  AI2Apps CLI help entry point completes successfully;
- the platform path is derived from the existing resolved installation data
  root without creating directories or opening a database;
- no WebUI files are part of this slice.

### Milestone 0B: database bootstrap

**Milestone 0B is complete.** It adds:

```text
ai2apps/platform_runtime.py
ai2apps/storage/database.py
ai2apps/storage/migrations.py
tests/test_ai2apps_platform_storage.py
```

The platform now creates one `ai2apps-platform.sqlite3` database beneath the
existing resolved installation data root during FastAPI startup. Schema v1 is
deliberately limited to `schema_migrations`; no App, Agent, Session, or Event
tables are introduced before their contracts are implemented.

Database bootstrap enables WAL, foreign keys, a bounded busy timeout, and
`PRAGMA quick_check`. Migrations run in short `BEGIN IMMEDIATE` transactions,
are idempotent under concurrent startup, roll back on failure, reject newer
schemas without downgrade, and distinguish lock timeout from corruption.
FastAPI lifespan owns PlatformRuntime startup and shutdown, while health reports
actual and target schema versions plus journal mode.

Acceptance evidence:

- fresh, repeated, concurrent, rollback, future-schema, corrupt-file, runtime,
  health, and complete FastAPI lifespan cases are covered;
- platform, authentication, status, product, CLI, and server-entry regression
  suites pass (72 tests total);
- scoped static checks pass;
- no model execution, MCP, existing oMLX data store, or WebUI behavior changed.

Milestone 1 can now begin with its first vertical slice: core IDs/time helpers
and the AppDefinition, AppInstance, Session, Message, MessagePart, and Event
schema contracts. Resource APIs and SSE should follow only after that migration
is stable.

## 16. Milestone 1 implementation progress

### M1A: core contracts and relational schema

**M1A is complete.** Schema v2 introduces the first Harness resource tables:

```text
app_definitions
app_instances
sessions
messages
message_parts
events
```

Internal resource IDs use lowercase UUID4 payloads with typed prefixes:
`app_`, `appi_`, `ses_`, `msg_`, `part_`, and `evt_`. Package-facing IDs such
as `ai2apps.general-chat` remain separate readable identifiers. Durable time is
canonical UTC RFC 3339 with six fractional digits and a `Z` suffix.

Relational rules in schema v2 include:

- App instance mode/scope consistency and database-enforced singleton keys;
- one optional HomeSession per AppInstance without limiting additional
  Sessions;
- strict AppInstance -> Session -> Message -> MessagePart ownership through
  foreign keys;
- per-Session message ordering and idempotency-key uniqueness;
- JSON validity, lifecycle vocabulary, opaque ID shape, revision, and timestamp
  checks;
- a database-global monotonically increasing Event sequence;
- Session/AppInstance Event scope consistency and append-only Event records;
- indexes for App lifecycle, Session collection, message replay, and Event
  replay queries.

The v1 -> v2 migration is transactional, preserves the existing migration
ledger, and remains safe under repeated and concurrent startup. This slice adds
no resource routes and performs no browser-owned thread migration. Core/schema,
platform lifecycle, authentication, status, product, CLI, and server-entry
regression suites pass (92 tests total), and scoped static checks pass.

The next slice is **M1B: repositories and transactional Event Store**. It will
implement typed row models, App/Session/Message repositories, atomic state plus
Event commits, optimistic revisions, and idempotent message append. REST and
SSE remain M1C so repository behavior can be tested independently first.

### M1B: repositories and transactional Event Store

**M1B is complete.** It adds typed records and explicit repositories for
AppDefinition, AppInstance, Session, Message, MessagePart, and Event without
introducing an ORM or changing schema v2.

All mutations use short caller-owned SQLite transactions. Repository state and
its semantic Event are committed together; an Event failure rolls back the
resource mutation and any structured MessageParts. The Event Store supports a
database-global cursor, bounded replay after a sequence, Session/AppInstance
filters, and subject lookup.

Implemented concurrency contracts:

- AppInstance state and Session metadata/lifecycle updates require an expected
  revision and return a typed conflict containing the actual revision;
- Message sequence allocation occurs under the write transaction, producing a
  gapless per-Session order under concurrent append;
- an idempotency key is scoped to one Session. An identical replay returns the
  original Message, parts, and Event without another write; reuse with different
  content raises a typed idempotency conflict;
- concurrent identical idempotency requests settle to one Message and one
  Event;
- scoped reads treat a resource owned by another AppInstance/Session as not
  found rather than exposing it;
- relational conflicts, missing resources, stale revisions, and idempotency
  conflicts have separate Repository error types.

Repository, core/schema, lifecycle, authentication, status, product, CLI, and
server-entry suites pass (103 tests total), and scoped static checks pass. No
REST/SSE endpoint or WebUI file is part of M1B.

The next slice is **M1C: Session/Message REST and replayable Event transport**.
It should add request/response schemas, Repository-error mapping, snapshot APIs,
an in-process notification bus, and SSE cursor replay with heartbeat and bounded
subscriber queues.

### M1C: generic Session REST and replayable Event transport

**M1C is complete.** Schema v3 makes the Session model explicitly broader than
the Chat App thread model:

```text
session_kind = app | chat_thread | mini_chat | in_app_chat | agent_child
visibility   = listed | unlisted
retention    = durable | temporary
expires_at   = optional UTC timestamp
```

`mini_chat` and `in_app_chat` default to `unlisted + temporary`. They remain
authoritative backend Sessions with Messages, Events, Agent context, and future
sandbox ownership, but do not enter the Chat App's persistent ThreadCollection.
A `chat_thread` is database-constrained to `listed + durable`; Chat ownership
itself will be enforced when the built-in Chat App is seeded in Milestone 2.

M1C exposes authenticated platform APIs for:

```text
POST/GET  /v1/platform/app-instances/{app-instance-id}/sessions
GET/PATCH/DELETE
          /v1/platform/app-instances/{app-instance-id}/sessions/{session-id}
POST/GET  /v1/platform/sessions/{session-id}/messages
GET       /v1/platform/sessions/{session-id}/events
GET       /v1/platform/events
```

The global Event endpoint is SSE. It accepts `after` or `Last-Event-ID`, replays
durable Events in global sequence order, then waits on an in-process commit
notification bus. Subscriber queues contain only one coalesced wake token, so a
slow client cannot create an unbounded in-memory Event backlog; it catches up
from SQLite. Idle streams emit heartbeat comments.

Notifications are registered inside the write transaction but published only
after commit. Rollback discards both the Event and notification. REST errors use
the stable platform envelope for authentication, validation, missing resources,
revision conflicts, relational conflicts, and idempotency conflicts.

REST/SSE, generic Session classification, commit/rollback notification,
heartbeat, cursor replay, bounded backpressure, repository, migration,
authentication, and oMLX compatibility suites pass (114 tests total), and
scoped static checks pass. No WebUI file is part of M1C.

M1 now has durable schema, repositories, snapshots, and replay transport. Its
remaining hardening slice should cover temporary-Session expiry/retention jobs,
SSE disconnect/load behavior, database backup/corruption operator diagnostics,
and broader crash-recovery/performance gates before declaring the milestone
fully closed.

### M1D: retention, recovery, and operator hardening

**M1D is complete, and Milestone 1 is Finished.** Schema v4 closes the
temporary-Session lifecycle contract. A newly created temporary Session gets a
24-hour expiry unless the caller provides an explicit UTC expiry; durable
Sessions cannot carry an expiry. The migration backfills legacy temporary
Sessions and database triggers preserve the retention/expiry invariant.

PlatformRuntime owns a bounded retention loop. Each pass soft-deletes at most
one batch of expired temporary Sessions and appends `session.expired` in the
same transaction. The operation is ordered and idempotent, preserves Messages
and Events for audit/recovery, and never promotes an unlisted interaction into
a Chat thread.

SQLite operator support now includes:

- read-only schema, journal, integrity, foreign-key, page-count, and page-size
  diagnostics;
- online backups through SQLite's backup API, written to a temporary sibling,
  integrity-checked, then atomically published;
- rejection of a backup target that aliases the live database;
- explicit tests proving uncommitted writes disappear after a connection crash
  and committed snapshot state remains readable.

SSE hardening verifies subscriber cleanup after cancellation, one-slot wake
coalescing, rollback silence, heartbeat behavior, and a 250-Event replay using
small batches without cursor gaps. The M1 backend and oMLX compatibility gate
passes **183 tests**, and scoped static checks pass. No WebUI file is part of
M1D.

Milestone 1 therefore delivers the generic Session substrate—not a Chat-only
thread store—together with durable Messages, atomic semantic Events, replayable
transport, temporary retention, restart/crash behavior, and operator-safe
SQLite diagnostics/backup. Milestone 2 may now build the singleton Chat App on
these generic contracts.

## 17. Milestone 2 implementation progress

### M2A: singleton Chat backend and ThreadCollection

**M2A is complete.** Schema v5 adds `chat_collections` and
`chat_thread_entries` without creating a second kind of message or conversation
store. Runtime startup idempotently seeds built-in `ai2apps.general-chat`,
resolves the initial local user to the stable singleton key
`ai2apps.general-chat:user:local`, and creates exactly one Chat AppInstance and
one collection under concurrent resolution.

Every Chat thread remains a generic `chat_thread + listed + durable` Session.
Session owns title, lifecycle, revision, metadata, Messages, and Events;
ThreadCollection owns selected-thread recovery state, pinning, ordering, and an
optional legacy browser-thread identity. Database triggers prevent managed
threads from changing classification and prevent generic Session calls from
archiving/deleting the selected Home thread without first reassigning it.

The transactional Chat repository implements:

- create, get, list, rename, pin, archive, and logical delete;
- optimistic collection selection independent of Session revisions;
- HomeSession designation and automatic selected/Home fallback;
- one AppInstance with any number of independently addressable Sessions;
- idempotent legacy-thread import, including browser message content and
  Session metadata, with rollback of the entire import if any Event/write fails.

Chat-friendly backend aliases are available at:

```text
GET         /v1/platform/chat
POST/GET    /v1/platform/chat/threads
GET/PATCH   /v1/platform/chat/threads/{thread-id}
DELETE      /v1/platform/chat/threads/{thread-id}
POST        /v1/platform/chat/threads/{thread-id}/select
POST        /v1/platform/chat/threads/{thread-id}/home
POST        /v1/platform/chat/threads/{thread-id}/archive
```

The existing oMLX WebUI stores history in browser `localStorage` under
`omlx_chat_history`; the backend cannot discover that browser-owned data by
itself. M2A therefore supplies the authenticated atomic import contract. M2B
below adopts that contract in the WebUI and completes the migration.

Singleton concurrency, ten-thread ownership, Message isolation, two-client
projection, selection/revision conflicts, Home fallback, AppInstance survival,
legacy idempotency/rollback, schema migration, platform API, authentication,
CLI, server-entry, and oMLX compatibility suites pass (**191 tests**), and
scoped static/compile checks pass. No WebUI file is part of M2A.

### M2B: authoritative Chat WebUI adoption

**M2B and Milestone 2 are complete.** The existing oMLX-style Chat Entry now
uses the authenticated platform Chat API as its authoritative thread store.
The UI creates one backend Session per thread and persists selection, title,
pinning, deletion, branching, imported chats, Session metadata, and message
content with optimistic revisions. Message snapshots remain generic Session
Messages/MessageParts; each replacement also emits a semantic Event.

On first authenticated startup, browser-owned legacy threads are imported by
stable legacy ID. Import is idempotent and resumable: an interrupted pass can
retry without duplicating threads. The migration marker records completion,
but `omlx_chat_history` is deliberately retained as a local recovery copy and
UI cache; it is no longer the source of truth. A backend failure leaves that
copy readable rather than destroying user history.

Content writes are debounced and serialized per thread. Every mutation carries
the last observed Session or collection revision, so stale browser windows get
an explicit conflict instead of silently overwriting newer state. Operations
whose local projection would be destructive, including thread deletion, commit
to the backend before removing the local copy.

The browser workflow was exercised against a real local server: creating,
renaming, pinning, legacy import, refresh, and backend recovery all succeeded.
Focused repository/API/UI suites and the complete M1/M2 compatibility gate pass
(**236 tests**), together with scoped Ruff and Python compile checks.

## 18. Milestone 3 implementation progress

### M3A: durable Service and Tool contracts

**M3A is complete.** Schema v6 adds `service_descriptors`,
`service_dependencies`, `service_instances`, and `tool_descriptors`. Stable
`svc_`, `svci_`, and `tool_` identifiers distinguish persisted identity from a
physical endpoint or process-local provider. Descriptors store runtime mode,
package/version, capabilities, dependency constraints, configuration, JSON
Schemas, declared effects, required capabilities, timeouts, lifecycle state,
health, and optimistic revisions.

The registry supports embedded and external JSON providers. Package
installation, signature verification, dependency solving, managed-process
supervision, and uninstall remain Milestone 8 responsibilities; M3 establishes
the control-plane records those systems will operate on.

### M3B: existing model runtime adapter

**M3B is complete.** `ai2apps.model-runtime` is seeded as an in-process built-in
Service backed by the existing oMLX EnginePool. `model.status`, `model.load`,
and `model.unload` are registered Tools, with lifecycle mutations requiring the
`model.manage` capability. Existing `/v1/chat/completions`, `/v1/responses`,
embedding, and reranking routes remain the model Service's authoritative
OpenAI-compatible inference contract; they are referenced by the Service
descriptor rather than duplicated or internally looped back.

### M3C: existing MCP adapter

**M3C is complete.** `ai2apps.mcp` wraps the current MCP Manager. Connected MCP
servers are projected into the shared Tool Registry as `mcp.<server>__<tool>`
without replacing the existing `/v1/mcp/*` compatibility API. Refresh disables
tools no longer discovered, execution delegates to the original manager, and
MCP enable/disable/restart delegates to its real start/stop lifecycle.

### M3D: Service Client/Gateway and control API

**M3D and Milestone 3 are complete.** The Tool Gateway resolves stable Tool and
provider identity, rejects provider spoofing, filters discovery by lifecycle
and granted capabilities, verifies active Session context before effects,
validates Draft 2020-12 input/output JSON Schemas, bounds execution time,
propagates cancellation, normalizes provider errors, and emits durable semantic
Events for completed, failed, timed-out, and cancelled calls. The built-in
`system.echo` Tool is the end-to-end diagnostic reference.

The authenticated control surface is:

```text
GET  /v1/platform/services
GET  /v1/platform/services/{service-key}
POST /v1/platform/services/{service-key}/enable
POST /v1/platform/services/{service-key}/disable
POST /v1/platform/services/{service-key}/restart
GET  /v1/platform/tools
POST /v1/platform/tools/{qualified-name}/invoke
```

Service lifecycle changes are revision-checked. Public Tool invocation never
accepts caller-supplied capability claims or provider identity; future Agent
Runtime calls use an internal `ToolCallContext` populated by policy and Session
grants. The complete M1-M3 plus existing MCP compatibility gate passes
(**451 tests**), together with scoped Ruff and Python compile checks.

## 19. Asynchronous Agent Runtime implementation progress

This foundation was pulled forward from Milestone 6 because it is the common
execution substrate for capability approvals, workspace Tools, and later App
integration. It does not mark the full Milestone 4 capability/GrantLease policy
or every Milestone 6 context/budget feature complete.

### AR-A: durable definitions, Runs, steps, status, and interactions

**AR-A is complete.** Schema v7 adds Agent definitions, shared concurrency
groups, AgentRuns, RunSteps, mandatory primary status-lines, and typed
interactions. Run and interaction state transitions are database-validated;
creation, client responses, and Tool action keys are idempotent. Menu, text,
file, form, and approval interactions carry JSON Schema plus UI hints and have
durable deadlines.

### AR-B: queueing, resource admission, and restart recovery

**AR-B is complete.** The asynchronous scheduler atomically claims priority
queue entries. An Agent may be ungrouped, share an N-wide concurrency group,
or claim an exclusive group with limit 1 for scarce hardware. Waiting for user
input or capability approval releases that capacity. Runtime shutdown,
cancellation, deadlines, interaction expiry, and restart recovery are explicit.
Interrupted effectful Tool calls become uncertain and require an operator/user
reconciliation decision before execution continues.

### AR-C: model and Tool action bridge

**AR-C is complete for the runtime action contract.** Resumable Agent executors
emit one durable action at a time. Model actions call the existing oMLX
OpenAI-compatible inference route through an in-process ASGI adapter. Tool
actions resolve the registered descriptor and execute through the Tool Gateway.
Missing Tool capabilities create a per-Run approval interaction before any
effect occurs; approval grants only the requested capabilities to that Run,
while denial or expiry fails closed. Durable action IDs prevent settled work
from being repeated during normal retries.

The diagnostic Agent exercises individual echo, model, Tool, menu, text, file,
and approval paths. The production general loop is completed in AR-E below.
Persistent GrantLease scopes and semantic/token-aware context compaction remain
their original Milestone 4/6 responsibilities.

### AR-D: frontend synchronization contract

**AR-D backend support is complete.** Authenticated HTTP endpoints create,
inspect, answer, approve/deny, cancel, and resume Runs. Every snapshot includes
the primary status-line, steps, interactions, revisions, and a Run-scoped SSE
URL. SSE filters by Run, persists sequence numbers, and replays after
`Last-Event-ID`; response IDs make repeated interaction submissions harmless.
The frontend can therefore render immediately from a snapshot and converge by
Events after reconnect without polling or relying on browser-only state.

At AR-D completion no concrete Chat renderer had changed; AR-F below now
delivers that integration without enabling rich HTML execution.

### AR-E: built-in General Agent model/Tool loop

**AR-E is complete.** `ai2apps.general-agent` is seeded as the default public
Agent target. It accepts either an existing Session User `message_id` or a
direct `prompt`; direct prompts and final Assistant answers use Run-derived
idempotency keys. The final Message carries its AgentRun/definition provenance.

Every scheduler pass reconstructs the OpenAI transcript from bounded Session
history plus completed model and Tool Steps. Model-requested function aliases
are stable across Tool catalog changes and resolve back to canonical qualified
Tool names. Multiple Tool calls in one model response settle durably in order,
retain their original `tool_call_id`, and feed the next model request. Missing
capabilities enter the existing fail-closed approval interaction before the
Tool handler executes.

The initial production guards include definition-level Tool allow patterns,
message-count context bounds with an explicit omission marker, cumulative
model-token budget, maximum Run steps and wall time, and consecutive identical
Tool-call detection. A final model answer may complete exactly at the Step
budget boundary, while a model that exhausts its token budget requesting an
effect cannot execute that effect. Full semantic context summarization and
persistent GrantLease policy remain later milestones.

### AR-F: Chat status and interaction renderer

**AR-F is complete.** New Chat turns create the built-in General Agent instead
of running the model/MCP loop in the browser. Each Run card is anchored beneath
its invoking User Message and converges from a Run snapshot plus authenticated,
cursor-replayable fetch-SSE. Cancelling the Chat turn durably cancels its Run;
page reload restores active Runs from Message provenance and retained Run IDs.
The legacy streaming path remains available to existing regenerate/variant
flows during their later migration.

The initial `StatusRendererRegistry` enables `status-v1`: semantic theme tones,
host icons, progress, expandable detail, bounded motion effects, terminal-state
normalization, dark-theme inheritance, and reduced-motion behavior. Unknown or
failing renderers always show non-empty text. `safe-html-v1` and
`sandbox-html-v1` are recognized but deliberately disabled; no Agent status
content reaches `x-html`.

Menu, text/form, and approval interactions render as independent schema-driven
cards and submit idempotent response IDs. File requests render an explicit
unavailable state until the Workspace ResourceHandle bridge exists, rather
than exposing an unsafe ambient browser path. Browser verification exercised a
durable waiting menu, selection submission, SSE convergence, reload recovery,
and terminal collapse.

## 20. M4A-D capability policy implementation progress

**M4A-D's initial vertical slice is complete.** Schema v8 introduces ordered
capability policies, durable GrantLeases, and immutable capability decision
records. The runtime evaluates every effectful Tool action before creating a
Tool Step: active non-expired leases are resolved first, then deterministic
rules by priority, with deny winning equal-priority conflicts. The built-in
fallback is `require_approval`; no Tool handler begins while the decision is
deny or unresolved.

GrantLeases support `run`, `session`, `agent`, and `app` scopes, remain bound to
the requesting Agent definition and Tool pattern, and carry issuer, expiry,
resource-selector, and evidence fields. Run grants expire at the Run deadline;
all grants can be listed and revoked through the authenticated platform API.
The old per-Run capability JSON remains only as a compatibility projection and
is not authoritative for execution, so revocation takes effect on the next
Tool checkpoint.

Chat approval cards default to **Allow once** and additionally offer **Allow
for session**, **Always allow agent**, and **Deny**. Approval response IDs remain
idempotent; the selected scope and response evidence are persisted with both
the interaction decision and issued lease. The management surface is:

```text
GET  /v1/platform/capability-policies
PUT  /v1/platform/capability-policies/{policy-key}
GET  /v1/platform/grant-leases
POST /v1/platform/grant-leases/{grant-id}/revoke
```

An independent AI auditor can be bound through
`PlatformRuntime.bind_ai_capability_auditor`. It receives a narrowed structured
request and may return allow, deny, or require-approval with evidence. Invalid
output or an auditor error fails closed to user approval. Deterministic denial
is never sent to or overridden by the auditor. Every policy evaluation, user
decision, lease issue, and revocation emits semantic audit Events.

This slice deliberately does not claim the remaining security-hardening items
from the full Milestone 4 gate: ResourceHandle target resolution arrives with
M5, and package/Patch digest-bound invalidation will be connected when the
package manager has canonical effective digests.

## 21. M5 Workspace and Artifact implementation progress

**The M5 vertical slice is complete.** Schema v9 adds one quota-tracked
SessionSandbox record per Session, opaque ResourceHandles, immutable Artifacts,
and durable Artifact export operations. Filesystem state lives below the
configured platform sandbox/artifact roots rather than in SQLite; SQLite holds
identity, ownership, content hashes, lifecycle, and audit metadata.

The built-in `ai2apps.workspace` Service publishes:

```text
workspace.list       workspace.stat
workspace.read       workspace.search
workspace.write      workspace.apply_patch
resource.read
artifact.create      artifact.list
artifact.preview     artifact.export
```

All workspace paths are relative to the owning Session root. Absolute paths,
parent traversal, and symlink escape are rejected after canonical resolution.
Reads/search/listing are bounded and paginated; writes and exact text patches
use same-directory temporary files plus `fsync`/atomic replacement, enforce a
per-Session quota, and return SHA-256 content hashes. Workspace writes and
Artifact creation are preauthorized only for the built-in General Agent inside
its own Session; third-party Agents continue through M4 policy.

Browser file interactions now copy the selected bytes into
`workspace/imports/...`, create a read-only `resource://res_...` handle, and
submit only that URI to the Agent. The backend independently verifies that a
file-interaction handle is live and owned by the Run's Session. A forged,
revoked, expired, or cross-Session handle is rejected even if it matches the
interaction's JSON Schema.

Artifacts are immutable content-addressed blobs with Session-scoped metadata,
bounded text/base64 previews, authenticated downloads, and idempotent creation
for the same Session/hash/name. Agent-driven external export requires both an
`artifact.export` GrantLease and an opaque directory handle created by a trusted
host picker. The initial local Host Export Broker writes a temporary sibling,
flushes it, and atomically replaces the destination; failures remove the
temporary and leave a durable failed export record.

The authenticated user API now includes Workspace list/read/write,
ResourceHandle import/list/revoke, and Artifact create/list/preview/download.
End-to-end browser verification exercised a real SVG selection, Session import,
opaque handle submission, Run resume, and terminal completion. The scoped
AI2Apps/Chat/API regression gate passes **319 tests**.

M5 is a logical filesystem security boundary inside the trusted main process.
It does not claim hostile-process containment or eliminate filesystem TOCTOU
races against a compromised process with ambient host authority; those are M7
Host Broker and enforced OS sandbox responsibilities.

## 22. M7 Process Service implementation progress

**The M7 vertical slice is complete.** Schema v10 adds durable Process
executions, bounded stdout/stderr chunks, authenticated Host Broker requests,
and argument-dependent Tool capabilities. The built-in `ai2apps.process`
Service publishes:

```text
process.start       process.write_stdin
process.status      process.logs       process.cancel
```

Commands are arrays passed to `exec`, never shell strings. An executable must
be system-provided or live inside the owning Session workspace. The child sees
only a constructed environment (`PATH`, Session workspace/home/temp identity,
an allowlist of locale/application keys, and values resolved from opaque Secret
references); the server's ambient environment is never copied.

Every execution is bound to its Session and, when invoked by an Agent, its
originating Run. Status, logs, stdin, and cancellation fail closed across either
boundary. A Session has a bounded concurrent-process count. CPU, memory,
captured output, wall time, idle time, stdin writes, argv count, and argv bytes
are limited. Output is incrementally drained into bounded SQLite chunks and is
truncated exactly at the configured ceiling before the complete process group
is terminated.

macOS uses a generated Seatbelt profile importing the platform's system
bootstrap rules, then grants filesystem access only to system runtime paths and
the owning Session's workspace/temporary roots. Network remains denied unless
`process.start(network=true)` has both `process.execute` and the dynamically
resolved `network.outbound` capability. Linux uses the parallel bubblewrap
contract with user/PID/IPC/UTS namespaces, `--die-with-parent`, read-only system
mounts, writable Session roots, and an unshared network namespace by default.
Production selection fails closed when the OS adapter is unavailable; the
unconfined adapter exists only as an explicit test double.

Before spawn, the in-process Host Broker issues an HMAC-authenticated,
operation/Session/Run-scoped, nonce-bearing, short-lived envelope. SQLite stores
only its digest and audit evidence, then records accepted or denied resolution.
Agent terminal/cancel callbacks terminate the whole process group. Graceful
platform shutdown does the same; restart recovery first verifies PID birth time
against the durable record, reaps the matching stale process group, and then
marks the execution orphaned, avoiding unsafe PID-reuse kills.

The M7 gate covers Session/Run isolation, environment denial, exact output
bounds, stdin, concurrency and idle limits, process-tree cancellation, verified
orphan reaping, Broker tamper/scope checks, dynamic network capability
resolution, Linux command construction, and real macOS cross-Session Seatbelt
denial. Rich Process-specific frontend work was unnecessary: existing Agent
status-line, approval, interaction, and cancel surfaces carry this Service.

## 23. M8 Service lifecycle and package trust implementation progress

**The M8 vertical slice is complete.** Schema v11 adds trusted publishers,
immutable Service package/version records, complete file indexes, audit
attestations, dependency locks, lifecycle operations, bounded structured logs,
and managed-process supervision records. Active Service descriptors and
GrantLeases now carry the exact package digest; an upgrade therefore invalidates
authority issued for the previous implementation.

The `.ai2service` reader accepts a bounded ZIP archive with `service.yaml`, an
exact SHA-256 `META/files.json`, SPDX 2.2/2.3 SBOM, publisher attestation, and
Ed25519 signature. It rejects traversal, links, duplicates, unindexed content,
hash/size disagreement, malformed manifests, and undeclared native artifacts.
The canonical package digest covers the normalized manifest and complete file
index. Installed payloads are extracted into a content-addressed immutable
store and are re-hashed before every activation or restart.

Publisher verification is fully offline and supports trusted, untrusted, and
revoked states. Embedded code is restricted to trusted publishers. A bounded
static source snapshot and findings are passed to an independently bindable
local AI auditor; its decision, model/policy metadata, evidence, and reviewed
file set are persisted as an attestation. Missing or inconclusive AI audit
requires explicit review approval, while rejection and auditor failure fail
closed before package code is imported or a process starts.

Dependency resolution is deterministic and produces digest-pinned locks with
cycle detection and dependency-first activation. Required reverse dependents
block stop, disable, and uninstall, and an upgrade is rejected if its version
would violate an unchanged active dependent. OS, architecture, Python,
accelerator, feature, and signed variant compatibility are selected before
execution.

The Service manager now controls embedded, managed-process, and external JSON
Services through install, audit, start, stop, enable, disable, restart,
upgrade, rollback, and uninstall operations. Managed Services use Seatbelt on
macOS or bubblewrap on Linux, with read-only package files, separate writable
data/temp roots, default-denied outbound network, readiness checks, process
group termination, bounded structured logs, restart/backoff, and PID birth-time
orphan verification. Transactional compensation restores the previous active
Service graph and removes newly staged files after a failed install or upgrade.

The authenticated platform API exposes publisher trust, package
inspect/audit/install/detail, lifecycle controls, rollback/uninstall, and
paginated Service logs. Existing Service list/detail surfaces report active
package digests and declared permissions, so a future management UI can be
added without another backend contract change.

The final M1–M8 backend regression gate passes **185 tests**, including real
macOS Seatbelt managed-Service execution and the isolated server-lifespan
health boundary. The scoped M8 implementation also passes Ruff and Python
bytecode compilation checks.

## 24. M9 installable Agent, App, and local Patch implementation progress

**The M9 backend vertical slice is complete.** Schema v12 adds immutable
Agent/App upstream packages, ordered device-local Patch stacks, cached Effective
definitions, App mounts, state snapshots, operation records, and durable Safe
Mode state. Agent and App definitions now bind both their verified upstream
digest and independently computed Effective digest.

`.ai2agent`, `.ai2app`, and `.ai2patch` use bounded archives, exact SHA-256 file
indexes, canonical manifest/file digests, SPDX SBOM, and the M8 publisher trust
store. Upstream Agent/App packages require a trusted Ed25519 publisher. Local
Patches are signed by an installation-local Ed25519 key stored with owner-only
permissions; a Patch copied from another device fails closed rather than being
silently treated as local authority. Source/UI inputs are bounded and included
in the independently bindable local AI audit request before activation.

Effective definitions are assembled from an immutable upstream plus the
ordered enabled Patch stack. Semantic operations carry stable dotted targets,
optional kind/digest preconditions, intent, rebase policy, resources, and
declarative acceptance tests. The cache identity separately covers upstream,
Patch-set, manifest, and resources. A changed target produces a durable
conflict and leaves the previous package and Effective definition active.
Explicit preserve-local, accept-upstream, or disable resolutions are required
before a conflicted candidate can activate.

Installed Agents reuse the existing asynchronous Agent Runtime and executor
registry; package manifests control status/instructions/runtime limits without
introducing a second scheduler. Installed Apps reuse AppDefinition,
AppInstance, and Session persistence. Every App declares Entry, may declare a
dedicated inline/sidebar Mini-Entry, registers navigation metadata, and can be
launched independently to create or restore its HomeSession. Existing database
constraints enforce multiple or scoped-singleton instance policy.

App upgrades snapshot every live instance, dry-run declarative state migration
for all instances, and atomically switch definition plus migrated state. Any
missing or failed migration retains the old EffectiveApp, instance state, and
upstream package. Retained versions support rollback; disable, enable, candidate
activation, uninstall protection, and structured operation history share the
same authenticated management API.

Safe Mode saves each Patch's prior state, disables all local Agent/App Patches,
reassembles clean upstream Effective definitions, and can later restore the
exact Patch stack. The minimal recovery endpoint is independent of App Entry
rendering. AI-created local Patches can be exported as device-signed
`.ai2patch` archives and reinstalled through the same verification path.

The final M1–M9 backend gate passes **198 tests**, including the isolated real
server-lifespan health test. M9's source passes scoped Ruff and Python bytecode
compilation. No WebUI files were changed: Entry/Mini-Entry/navigation/mount and
conflict contracts are ready for a separately agreed frontend implementation.

## 25. WebUI Shell and System App migration plan

The post-M9 frontend phase turns the separated `ai2apps/web` surface into an
AI-device Shell rather than extending the old administrative navigation. The
Shell is an unpatchable recovery boundary and owns the Dock, App Launcher,
current App frame, overlays, theme/locale propagation, authenticated App
Bridge, and Safe Mode entry. Apps cannot draw over or impersonate Shell UI.

### 25.1 Dock contract

The Dock has two persisted presentation modes:

- `docked`: always visible; the current App frame occupies the content region
  below it;
- `immersive`: the App frame remains full viewport size; the Dock appears as an
  overlay when requested by the App Bridge, keyboard/touch affordance, or a
  delayed pointer hot zone at the top edge.

Dock identity distinguishes `pinned`, `running`, and `current`. Pinned Apps may
be stopped; running Apps expose an indicator and optional instance count;
current is the one AppInstance projected by the frame host. Singleton clicks
focus the existing instance. Multiple-instance Apps focus the most recent
instance by default and expose explicit new/switch actions. Shell-managed
status badges cover notifications, waiting approval, degraded, and failed
states. A bounded recently-used frame cache may keep fast-switching Apps
mounted; older frames suspend rather than remaining indefinitely resident.

### 25.2 App Launcher contract

App Launcher is a full-Shell overlay, not an ordinary third-party App. It
lists enabled installed Apps as an icon grid with search and categories derived
from system classification, signed manifest metadata, and user override.
Clicking an icon starts or focuses the correct AppInstance and closes the
Launcher. Initial categories are System, AI & Chat, Models, Developer,
Utilities, User-created, and Third-party. Drag sorting, folders, and richer
touch editing are deferred until the launch/focus lifecycle is stable.

### 25.3 App frame and Bridge

The route hierarchy is `/apps/{app-id}` and
`/apps/{app-id}/instances/{instance-id}`. The Shell owns browser history and
loads the selected Entry in an iframe App Frame. `host`, `schema`, `safe-html`,
and `sandbox` renderers share one mount envelope, with progressively stricter
isolation for third-party content. API credentials are never handed to an App
frame; authenticated operations cross a source/instance-validated Bridge or
the normal protected platform API.

The first Bridge vocabulary includes `app.ready`, `app.set_title`,
`app.set_badge`, `app.request_dock`, `app.navigate`, `app.open_entry`,
`app.mount_mini_entry`, `app.request_capability`, `app.create_agent_run`,
`app.export_artifact`, and `app.close`. Host messages include theme, locale,
instance, HomeSession, interaction Session, visibility, resume/suspend, and
safe-area changes. Parent DOM access, arbitrary top navigation, credential
access, and unvalidated cross-App messaging remain denied.

### 25.4 System App migration order

The old oMLX pages become built-in Apps while their URLs remain compatibility
redirects:

1. Dashboard/Status -> `ai2apps.dashboard`, singleton/system;
2. Models/Downloads -> `ai2apps.models`, singleton/system;
3. Settings -> `ai2apps.settings`, singleton/system;
4. Logs -> `ai2apps.logs`, singleton/system;
5. Accuracy/Context/Throughput Bench -> `ai2apps.benchmark`, one singleton App
   with internal pages;
6. Chat -> existing `ai2apps.general-chat`, singleton/user with multiple
   thread Sessions.

App Launcher, Dock, frame recovery controls, and Safe Mode stay in the Shell
and are not converted into patchable Apps.

### 25.5 Delivery slices and gates

**W1 — Shell foundation:** App Frame Host, docked/immersive layout, top hot
zone, persisted preference, keyboard/touch accessibility, theme and locale.

**W2 — Launcher and lifecycle:** installed-App discovery, pin persistence,
running/current projection, singleton launch/focus, multiple-instance menu,
history/deep links, suspend/resume.

**W3 — System App migration:** move Dashboard first, then Models, Settings,
Logs, Benchmark, and finally Chat; preserve API/runtime behavior and legacy URL
redirects at every step.

**W4 — constrained Views:** schema host renderer, sanitized safe HTML, sandbox
iframe/CSP/Bridge, Mini-Entry inline/sidebar, conflict workspace, package trust
details, and Safe Mode management.

The first programming slice is W1 plus W2's minimal Launcher and Dashboard as
the reference System App. Its exit gate requires functional keyboard and
pointer navigation, correct docked/immersive geometry, no App resize when the
immersive Dock overlays, stable deep-link/back behavior, singleton Dashboard
reuse, and unchanged backend/OpenAI-compatible tests.

### 25.6 First implementation slice

**W1 and the system-App portion of W2 are now implemented.** The authenticated
Shell is available at `/apps/{app-id}` and the reserved multi-instance form
`/apps/{app-id}/instances/{instance-id}`. The legacy `/admin/dashboard` entry
opens Dashboard inside the same Shell, so existing login and bookmark flows
continue to work.

The first Dock supports persisted docked and immersive modes, pinned/running/
current projections, pointer and keyboard access, an immersive top-edge hot
zone, and a same-origin App Bridge button that explicitly requests the Dock.
The App Launcher provides category filtering, search, launch/focus, and pin or
unpin controls. Dashboard, Models, Settings, Logs, Benchmark, and the existing
`ai2apps.general-chat` are exposed as built-in system Apps.

During this compatibility slice, Dashboard/Models/Settings/Logs/Benchmark use
one existing dashboard renderer with an App-specific initial tab; its old
navbar is suppressed when embedded. This deliberately preserves the mature
oMLX behavior while establishing the Shell boundary. The next slice must bind
Launcher discovery and running instances to the M9 App lifecycle API, serve
verified third-party Entry resources through the constrained View host, add
multi-instance switching, and replace the initial same-origin bridge with
instance-bound message envelopes before third-party content is enabled.

### 25.7 Authoritative App Runtime integration

**W2 lifecycle integration is now implemented.** Platform startup idempotently
registers Dashboard, Models, Chat, Settings, Logs, and Benchmark as built-in
AppDefinitions. The M9 App catalog now returns built-in and installed Apps in
one ordered response with navigation metadata, instance policy, live non-closed
instances, HomeSession identity when one exists, and running counts.

The Shell uses an administrator-session adapter rather than receiving the model
API key. Launch, focus, suspend, close, Entry resolution, and package resource
requests pass through that adapter to the existing M9 App Runtime. Singleton
instances reopen after close without violating their durable singleton key;
multiple-instance Apps can create, list, switch, close, and restore exact
instances. Running state is SQLite-authoritative. Only Dock mode and pin order
remain device-local preferences. Canonical instance URLs and browser history
restore the requested AppInstance after refresh, forward, and back navigation.

The Entry Frame Host now selects among four renderer boundaries:

- `host` resolves only product-owned resource identifiers;
- `schema` loads verified JSON into a non-executable generic host renderer;
- `safe-html` sanitizes verified HTML through the bundled DOMPurify runtime;
- `sandbox` serves re-hashed package resources under restrictive iframe and CSP
  sandboxing with network and form submission denied.

Installed resources are resolved only from the active digest-bound package or
enabled local Patch store and are re-hashed before every response. Frame
messages carry a per-mount random token and exact AppInstance identity; the
Shell also validates the mounted window and expected same-origin or opaque
sandbox origin. Broader capability, AgentRun, Artifact, and Mini-Entry bridge
operations remain separately policy-gated W4 work.

### 25.8 Independent System App Entries

**W3 is now implemented.** Dashboard, Models, Settings, Logs, and Benchmark no
longer mount the complete legacy dashboard document and select one hidden tab.
Each built-in App has an independent Host Entry template containing only its
owned surface. Chat was already an independent Entry and now returns to the
canonical Dashboard App route through the Shell.

The five dashboard-derived Apps intentionally share the mature oMLX-derived
Alpine business controller, CSS, API clients, translations, and focused
partials. This is a compatibility runtime, not a shared page: model-management
modals are mounted only by Models, sibling panels are absent from the DOM, and
the fixed App identity cannot be changed with an iframe query parameter. This
preserves runtime behavior without duplicating thousands of lines of proven
model, settings, log, and benchmark logic.

Legacy `/admin/dashboard` bookmarks remain valid. Its historical `tab` query
selects the matching System App (`models`, `settings`, `logs`, or `bench`) in
the Shell, while unknown or missing values open Dashboard. Canonical App and
AppInstance URLs remain authoritative after resolution.

### 25.9 W4 constrained Views and Mini-Entry completion

**W4A–D are now implemented.** W4A replaces the initial Dock-only message
hook with an instance-bound App Bridge. Every request carries a random mount
token and AppInstance identity, and the Shell verifies the mounted source
window and expected origin before handling title, badge, navigation, Entry,
Mini-Entry, capability, AgentRun, Artifact, or close operations. Capability and
Artifact requests remain policy-gated and cannot use the Bridge to bypass an
approval or trusted host picker.

W4B makes Mini-Entry a durable projection of the same AppInstance rather than
a second lightweight App. Chat can mount it inline beside the triggering user
message, move it to the right sidebar, close it, or expand it into the full
Entry without losing App state. The interaction Session and message context
are stored in SQLite schema v13, so mounted Mini-Entries restore with the
conversation after refresh. Installed Apps may declare natural-language
activation examples, but third-party matches are suggestions requiring an
explicit user action; they do not silently auto-mount.

W4C adds the Shell-owned System Control surface. It exposes installed Agent and
App package identity, version, publisher, signature verification, local audit
evidence, requested permissions, dependency metadata, renderer boundary, and
the ordered local Patch stack. This recovery UI is outside every patchable App
frame and remains available when normal App UI is damaged.

W4D connects Patch conflict decisions and Safe Mode to effective runtime
state. Keep-local, accept-upstream, and disable decisions reassemble the target
definition and activate the recoverable upgrade candidate once all conflicts
are resolved. Multi-conflict decisions remain durable between steps while the
previous active package stays usable. Safe Mode temporarily removes eligible
local Patches, rebuilds active Agent/App definitions from signed upstream
packages, and restores the recorded Patch states and effective definitions on
exit.

### 25.10 W5 capability approval and recovery completion

**W5A–D are now implemented.** W5A adds one Shell-owned Approval Inbox for
both AgentRun approval interactions and App Bridge CapabilityRequests. Each
card identifies the requesting App or Agent, capability, Tool, side-effect
class, resource selector, risk level, reason, and deadline. The same Agent
approval remains visible inline in Chat so the user can decide without leaving
the conversation.

W5B exposes active GrantLeases in System Control with scope, subject, Session,
resource selector, issuer, expiry, and explicit revocation. App requests can be
approved once, for the interaction Session, or for the App. “Once” is a
short-lived App lease tied to the exact approved request; durable Session/App
decisions remain revocable. Agent approvals additionally retain Run and Agent
scopes. Grant identity and lifecycle remain SQLite-authoritative.

W5C turns `requestCapability()` into a real asynchronous Bridge operation. The
calling frame's Promise stays pending while the durable request is in the
Inbox, then resolves with the decision and GrantLease without exposing an API
credential. AgentRun approval continues to use the existing
`waiting_capability -> queued` transition and wakes the scheduler immediately
after approval. Frame/source/origin/mount-token checks remain in force for the
entire wait.

W5D extends Safe Mode across subsystems. Entering it revokes every active
GrantLease, terminates active managed sandbox processes, disables eligible
local Patches, and rebuilds signed effective definitions. Grant creation,
decision, expiry, revocation, and Safe Mode recovery actions are emitted into
the durable event audit stream with subject, AppInstance, Session, risk, scope,
resource, and evidence. Revoked Grants deliberately remain revoked when
leaving Safe Mode.

Schema v14 adds generic `capability_requests`, request/App indexes derived from
the Inbox queries, and request-linked App GrantLeases whose AgentDefinition may
be absent. Existing Agent grants migrate without changing their policy or
matching semantics.

Browser acceptance also corrected a W4 Bridge ambiguity: the authenticated
caller `instanceId` and Mini-Entry/Entry `targetInstanceId` are now distinct.
Chat can therefore mount Dashboard (or another App), move the same instance to
its sidebar, and expand that exact instance into full Entry without
accidentally mounting Chat itself.

### 25.11 W6 Agent Harness Tool execution completion

**W6A–D are now implemented.** Earlier M3/M5/M7 and Agent Runtime slices had
already established the Service/Tool Registry, Workspace and Process
providers, and a resumable General Agent loop. W6 formalizes those components
as one Harness execution contract rather than introducing a parallel Tool
system: a Tool is the model-visible invocation and authorization boundary,
while its owning Service remains the installation, lifecycle, dependency, and
execution boundary.

W6A adds durable `ToolInvocation` identity and schema v15 persistence. Every
accepted call records the canonical Tool and provider, caller, Session and Run
trace, validated arguments, effective timeout, progress, attempt count,
terminal output or error, and timestamps. The Gateway emits started, progress,
retrying, completed, failed, cancelled, and restart-interrupted audit events.
Installed Service packages may declare an explicit retry policy bounded to
three attempts; no Tool retries implicitly, and only declared stable error
codes are retried.

W6B projects the existing Workspace/Resource/Artifact Service through that
Gateway. List, stat, bounded read/search, atomic write, exact patch,
ResourceHandle read, and Artifact create/list/preview/export remain
Session-sandboxed and capability checked. Write and patch operations now emit
progress through the invocation and Agent status-line channels.

W6C completes the Process Tool family with start, stdin, status, logs, bounded
wait, and cancel. `process.wait` has an explicit maximum timeout and prevents a
model from consuming steps with unbounded polling. Dynamic network requests
continue to add `network.outbound` to the required capability set, and every
process remains scoped to the originating Session and, when present, Run.

W6D connects invocation progress to the existing durable General Agent
`model -> Tool -> model` loop. RunSteps remain the replay authority for model
conversation reconstruction; ToolInvocations provide the finer execution and
audit authority. Step and token budgets, repeated-call protection, bounded
Session context, approval pause/resume, cancellation, uncertain effectful
steps, idempotent final Messages, and restart recovery all remain enforced.
No new WebUI surface is required: status-line and W5 Approval Inbox protocols
carry Harness progress and decisions.

### 25.12 W7A Chat Agent Mode completion

**W7A is now implemented.** Chat exposes a Session-scoped Chat/Agent switch
without splitting conversation history. Chat mode streams directly from the
selected model and deliberately omits model-visible MCP Tools. Agent mode
creates an `ai2apps.general-agent` AgentRun in the same Session so the Harness
may select only its registered and policy-approved Tools and Apps. The selected
mode is stored in authoritative Chat session metadata and survives navigation,
refresh, branch creation, and backend migration.

Every Agent turn is anchored beneath the invoking user message. The existing
replayable authenticated event stream converges status-line, RunStep, Tool
activity, approval/menu/text/file interactions, output, and terminal state with
snapshot refresh. The compact card shows current status and aggregated Tool
names/counts; expanded details retain step and recovery evidence. Agent turns
do not lock the composer, so independent Runs may coexist in one Session while
each Run retains its own cancel control.

Run lifecycle controls now include pause and resume in addition to cancel.
Schema v16 adds explicit `queued/planning -> interrupted` transitions while
preserving the database state-machine guard. Pausing cancels active execution
but keeps the Run durable: a non-effectful Tool is abandoned for a safe retry,
an effectful in-flight Tool becomes uncertain and requires the user to choose
retry or assume-completed, and model/planning work resumes from the durable
queue. The WebUI restores interrupted Runs and exposes the required recovery
choice inline.

### 25.13 W7B installed Agent selection completion

**W7B is now implemented.** Agent mode no longer assumes that every turn uses
the built-in General Agent. Chat loads the authoritative installed Agent
catalog from `/v1/platform/agents`, presents enabled definitions in a compact
selector, and stores the selected `agent_key` in the current Chat Session.
New and branched Sessions receive an explicit selection, while a disabled or
removed definition falls back deterministically to the General Agent (or the
first enabled definition when the General Agent is unavailable).

Each Agent turn records `execution_agent` on its invoking message and submits
that exact key to AgentRun creation. AgentRun API snapshots now include the
canonical Agent key and display name alongside the immutable definition ID, so
restored status cards identify their executor without relying on current
catalog ordering. Catalog refresh occurs at login and when Chat becomes visible
after Agent installation or management changes.

W7B deliberately keeps Agent choice explicit. Natural-language routing and
delegation are separate policy decisions: the system does not silently replace
the Session-selected Agent based only on prompt text.

### 25.14 W7C schema-driven Agent invocation completion

**W7C is now implemented.** Agent definitions may declare `discoverable`,
`aliases`, a JSON Schema `invocation_schema`, and non-executable
`invocation_ui` hints. Built-in Diagnostic Agent is hidden from ordinary Chat
discovery, while General Agent publishes stable `general` and `agent` aliases.
Third-party `.ai2agent` archives fail closed before installation when these
fields are malformed or the invocation schema is invalid or non-object-shaped.

Chat renders only controlled string, number, integer, boolean, and enum fields;
it never renders Agent-provided HTML. Parameter defaults are stored per Agent
inside authoritative Session metadata, inherited by thread branches, and may be
overridden before each turn. Required and basic type constraints are checked in
the client for immediate feedback, then the Agent Repository validates the
complete parameter object with JSON Schema before a Run is accepted.

A leading `@alias` explicitly chooses an enabled discoverable Agent for one
turn without mutating the Session default. The visible user message retains the
mention, while the Agent receives the cleaned natural-language prompt. Every
invoking message records Agent key, invocation source, and parameter snapshot;
the Run input replaces caller-asserted identity with the authoritative
definition ID, key, package version, and bounded source string. AgentRun API
snapshots expose the captured package version for audit and replay.

### 25.15 W7D bounded Agent delegation completion

**W7D is now implemented.** Schema v17 gives every AgentRun a durable tree
position (`parent_run_id`, `root_run_id`, and depth) and adds a request-keyed
delegation ledger. The built-in `ai2apps.agent-runtime` Service publishes
`agent.delegate`; it creates or reattaches to a child Run, projects the parent
status as `waiting_subruns`, waits for a terminal result, and settles that
result through the ordinary durable Tool step before the parent continues.

The first scheduling envelope allows at most two child levels and four direct
children per Run. Child timeouts cannot outlive the parent, and delegated
step/model-token budgets can only reduce definition limits. Children share the
conversation Session for resource attribution but do not inherit parent Run
capabilities and do not append their private prompt or output as Chat Messages.
Their Tools and approval requests pass independently through the existing
Harness policy boundary.

Cancel and pause operations cascade to active descendants, while terminal
waiters are awakened from durable Run state and idempotent delegation replay
reuses the prior child. AgentRun API snapshots expose tree identity and direct
child IDs, with a dedicated children endpoint. Chat renders recursive child
status lines and child interactions beneath the invoking root Run, and only
the root completion is projected as the final assistant message.

### 25.16 W8 Agent Manager completion

**W8 Agent Manager is now implemented without Agent Studio.** The new
`ai2apps.agents` singleton system App has three bounded surfaces: Catalog for
definition identity, lifecycle and policy inspection; Runs for filtered global
AgentRun operations; and Packages for signed archive installation, uninstall,
version provenance, Effective Definition identity, and local Patch/conflict
diagnostics.

The Agent API now exposes complete definition management metadata, persistent
enable/disable operations, filtered Run listing, Run counts, and an aggregated
management snapshot. Run controls reuse the existing W7 pause/resume/cancel
state machine, including parent/child cascade. Package changes reuse M9's
audited interactive-package APIs rather than introducing a second installer.

No source editor, AI code generator, manifest editor, or executable status
renderer is included. Necessary Agents will be developed with Codex, tested in
Session sandboxes, audited, signed, and installed. Those concrete workflows
will become evidence for a later Coding plan and eventual Agent Studio design.

## 26. Deferred W9 Coding Harness plan

**Status: Deferred.** W9 must not begin until the current Shell, system Apps,
Chat, Agent Runtime, Agent Manager, Service/Tool control plane, and package
flows have completed a stabilization pass. The active development priority is
to reproduce, classify, fix, and regression-test current WebUI and system
issues. Stabilization fixes may refine existing contracts but must not
silently introduce Coding Studio or IDE scope.

### 26.1 W9A Project and Workspace contract

Build on the existing Session sandbox and Workspace Service. Add explicit
project identity, project-to-Session attachment, bounded file indexing,
working-directory rules, and project ResourceHandles. Do not introduce a
second filesystem abstraction.

### 26.2 W9B structured Git Service

Expose repository-aware read Tools such as status, diff, log, branch, and
blame, followed by capability-gated mutation Tools for stage, commit, branch
creation, and switching. Git mutations must retain exact repository, worktree,
path, caller, Session, Run, approval, and result evidence. Raw Process Tool
execution remains an escape hatch rather than the primary Git contract.

### 26.3 W9C diagnostics and test execution

Normalize test, build, Linter, type-checker, and compiler results into durable
structured diagnostics while preserving complete Process logs. Providers may
be language-specific, but the Agent-facing result contract must consistently
identify file, location, severity, code, message, command, exit status, and
related Artifact or log handles.

### 26.4 W9D first Coding Agent

**Status: Planned for later implementation with Codex; no Agent Studio UI.**
Create a signed installable Coding Agent package only after W9A-C and the
stabilization gate pass. Its first version must:

- inspect the attached project and relevant repository state;
- state and update a bounded execution plan;
- search, read, and apply exact file changes through Workspace Tools;
- run targeted diagnostics/tests and iterate from their structured results;
- use status-line phases for inspection, planning, editing, verification, and
  waiting for user input or approval;
- request capabilities before effects and preserve every Tool invocation in
  the Run audit trail;
- delegate bounded test or review work through child AgentRuns when useful;
- stop with a clear verified result, partial result, or actionable blocker;
- avoid committing, pushing, deleting, or escaping the Session sandbox unless
  explicitly authorized.

The initial Coding Agent will be authored and maintained in Codex so real
package structure, prompts, Tools, interactions, Evals, failure recovery, and
Patch experience can be collected. Those findings will inform a later Coding
App and Agent Studio rather than being prematurely encoded into either UI.

### 26.5 W9 entry gate

W9 may be resumed only after the current issue-fixing pass has:

1. recorded reproducible cases for the known WebUI/system problems;
2. added regression coverage for fixed lifecycle and navigation failures;
3. verified Shell/App iframe loading, authentication, refresh, and recovery;
4. verified Chat and AgentRun persistence, interaction, cancellation, and
   parent/child presentation against the real local server;
5. left no known data-loss, authorization-bypass, or unrecoverable lifecycle
   defect in the current milestone.
