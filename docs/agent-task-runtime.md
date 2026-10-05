# Persistent Agent Task Runtime

AI2Apps represents a durable task as an `AgentRun`. Runs, steps, status lines,
interaction requests, outputs, and errors are committed to the platform SQLite
database before the scheduler advances.

## Lifecycle

`queued -> planning -> running` is the executable path. A Run can then:

- return to `queued` after a durable model or Tool checkpoint;
- enter `waiting_input` or `waiting_capability` for user action;
- enter `interrupted` after a manual pause or an uncertain Tool interruption;
- finish as `completed`, `failed`, or `cancelled`.

The single-user General Agent uses the `model:foreground` concurrency group
with a limit of one. Waiting and interrupted Runs release that slot. Delegated
Agents retain their independently declared concurrency group.

## Checkpoints and recovery

Each model or Tool invocation is a `RunStep` with a stable action key. Completed
steps are replayed from SQLite instead of being executed again. If the server
stops during a read-only Tool or model step, the step is abandoned and can be
retried. An interrupted effectful Tool becomes `uncertain`; the user must choose
`retry` or `assume_completed` before resuming.

Graceful shutdown marks queued work as suspended. Startup requeues safe work and
extends its deadline by the offline interval. Time spent waiting for user input,
approval, or a manual resume also does not consume the execution deadline.

## Budgets

Run creation accepts an optional `budget` object:

```json
{
  "max_steps": 12,
  "timeout_seconds": 600,
  "max_model_tokens": 50000
}
```

Run budgets can only lower the corresponding AgentDefinition limit. API
snapshots expose both the effective `budget` and current `usage`. Delegated Runs
are additionally bounded by their parent's deadline and delegation budget.

## Control API

- `POST /v1/platform/sessions/{session_id}/agent-runs`
- `POST /v1/platform/agent-runs/{run_id}/pause`
- `POST /v1/platform/agent-runs/{run_id}/resume`
- `POST /v1/platform/agent-runs/{run_id}/cancel`
- `POST /v1/platform/agent-runs/{run_id}/retry`
- `GET /v1/platform/agent-runs/{run_id}`
- `GET /v1/platform/agent-runs/{run_id}/events`

Retry creates a new auditable Run rather than mutating the terminal attempt.
The new input records `retry_of_run_id`, the root attempt, and the attempt
number. Retries are idempotent when given an idempotency key and are capped at
three attempts.

## Context admission and diagnostic evidence

The General Agent resolves generated inputs by their durable idempotency key
and reads recent Session history through the selected input's sequence. Later
messages are excluded. Delegation from a generated parent input records that
input's message ID, so the child uses the same boundary.

After optional checkpoint projection (described below), `max_context_bytes` in the Agent manifest
(default 524288) bounds the serialized UTF-8 request. It removes whole older
user turns while retaining system instructions, the current user input and the
entire current Run's model/Tool trace. It emits an omission notice and leaves
original Messages and RunSteps intact. If the required portion alone is too
large, the Run fails with `context_budget_exceeded` before invoking a model.
This byte guard does not measure model tokens or image-token costs; it is not
automatic summarization or a guarantee that a provider's context window fits.

`agent.model.context.prepared` records the policy version, byte counts, omitted
message count, request hash and RunStep ID under the Session's App identity.
The hash covers the canonical JSON request stored in RunStep.input, before
provider-specific transformations; it does not claim to represent wire bytes.

## Limited Tool input correction

General Agent read-only Tool calls may return pre-dispatch schema validation
errors to the model as paired Tool error messages. The rejected steps remain
FAILED in SQLite and are never presented as successful Tool executions. At
most three such corrections are allowed per Run; a fourth schema rejection
ends the Run. The model can fix arguments or select another allowed Tool.
Run step/token/deadline budgets continue to apply.

This does not recover malformed JSON, authorization denials, effectful Tools,
provider failures or cancellation automatically. Other executors retain their
existing failure behavior unless their ToolCallAction explicitly opts in.

## Hard process loss

Startup recovery abandons a RUNNING model step for restartable Runs, preserving
its cancelled attempt and releasing its action key before requeueing. This
mirrors the model-step cleanup normally performed during graceful shutdown.
Hard-loss Tool steps remain conservatively UNCERTAIN; the graceful-stop path
can classify known read-only Tools more precisely. Neither path guarantees
exactly-once execution or billing at an external provider.

## Large Tool result references

When `agent.read_tool_result` is available to the General Agent, completed Tool
outputs larger than 32768 UTF-8 bytes are represented in subsequent model
requests by a versioned JSON preview: first 2048 and last 1024 Unicode
characters, exact omitted-character count, original byte/character counts,
SHA-256, source RunStep ID and the actual reader Tool alias. The original JSON
output remains unchanged in SQLite. A preview is partial text, not a complete
semantic JSON value or a summary of omitted facts.

The reader accepts `step_id`, `offset` (default 0) and `limit` (default 4096,
maximum 8192). It returns a JSON-text fragment and `next_offset`; null means
EOF. Offsets count Unicode code points, not UTF-8 bytes. Each page carries the
original text's SHA-256. The Run comes from trusted invocation context, and
must belong to the invocation's Session; only completed Tool steps belonging
to that Run can be read. No filesystem path or other Run ID is accepted.

If the reader is filtered out by Agent or per-Run Tool selection, outputs stay
inline and the request byte guard still applies. Reader pages themselves are
not recursively abbreviated. Every read consumes ordinary Tool/Run budgets.
This avoids adding a second output store or an independent retention policy;
the normal Run lifecycle owns the source. It does not reduce SQLite storage,
avoid loading the source JSON, or implement a multimodal artifact reader.

## Repeated Tool cycles

In addition to the existing consecutive-identical-call limit, General Agent
detects periods of two to four completed Tool calls repeated three times with
identical names, canonical arguments and outputs. It stops with
`repeated_tool_cycle` before dispatching the next matching call. A different
argument or result breaks this detection; result-reader offsets therefore
allow forward pagination. This bounded guard complements existing Run budgets
and does not infer that unchanged polling is useful work.

## Structured questions and Run plans

`agent.ask_user` accepts a unique `question_id`, a question and optional two to
eight suggested options. General Agent converts it into a durable text/menu
Interaction and waits without another model call. Both forms allow free text;
a submitted answer becomes the paired Tool result on resume. Reusing an ID
for different arguments is rejected. Answers never grant capabilities. Existing
interaction ownership, cancellation, expiry and restart recovery apply.

`agent.read_plan` returns revision 0 and an empty list initially.
`agent.update_plan` replaces the full list using `expected_revision`; up to 50
items have stable IDs, titles and pending/in_progress/completed status. IDs are
unique and at most one item is in progress. Identical writes are idempotent;
conflicting writes fail. Plans persist as `agent.plan.updated` events, scoped to
the current Run/Session. Run snapshots expose the plan and Chat renders it for
parent and child Runs using escaped text. Completing a plan does not complete
the Run or modify Todo projects. Updates require a running Run.

## Bounded workspace discovery

`workspace.glob` discovers files by relative patterns. `workspace.search`
retains literal search by default and adds `mode=regex`, `include` glob,
`case_sensitive`, `context_lines` (0–5) and `include_hidden` (default false).
Bare patterns such as `*.py` match basenames at any depth; slash patterns are
workspace-relative and `**` matches zero or more directories. Regex operates
per line. Results use one-based line numbers and up to 500 characters per line.

Search stays within the Session workspace and walks without following symbolic
links. UTF-8 text only is searched; NUL-containing binary files are skipped.
Bounds are 1 MiB per file, 16 MiB total input, 10,000 directory entries, 2,000
matching files, depth 64, three seconds scan time and 20 ms per regex match.
Filesystem calls can still wait on the underlying filesystem. Output reports
scan counts, skipped files, `truncated` and `incomplete_reasons`; callers must
not interpret a partial result as proof of absence. Result caps are 1–1000.

## Replayable context checkpoints

When `agent.read_context_checkpoint` is available, the General Agent may summarize
older text context before the byte guard rejects an oversized request. At 75% of
`max_context_bytes`, it groups history by user turns and active execution by
complete model/tool rounds. System messages, the current user input and the two
newest groups remain verbatim. Pending/unpaired Tool calls and multimodal content
are not compacted by this policy. Existing message-count and byte admission
limits remain in force; this does not recover history already excluded by them.

A checkpoint is a separate model RunStep with an action key derived from the
policy, pinned-context hash and covered-source hash. Its request contains the
previous memory and only newly covered groups, capped at 85% of the byte budget.
It uses the same model with no Tools, asks for six JSON fields (facts, decisions,
constraints, pending, uncertainties, references), and requests up to 2048 output
tokens. Host-only checkpoint metadata is saved in RunStep.input and stripped
before provider dispatch. Normal Run step, token and deadline budgets apply;
there are at most eight checkpoint attempts per Run. Summarization adds latency
and model cost; it is not a free background operation.

Only completed, non-truncated, non-tool responses with a valid nonempty structure
and at most 8192 UTF-8 bytes can be used. The rendered memory must save more than
512 bytes over its covered source. On every replay the current pinned context
and source hashes are checked again. Cancelled/running/stale/invalid checkpoints
never replace source records. Invalid output does not immediately trigger another
summary attempt without normal-model progress. A provider exception still follows
the existing retryable Run failure path; this is not automatic provider failover.

The immutable summary step is the durable checkpoint; no original Messages or
RunSteps are deleted. Checkpoint steps never become normal assistant task replies
or Tool decisions. An adopted summary is an assistant-level derived-memory block,
not a system instruction or permission grant. Its `step_id` and reader alias allow
`agent.read_context_checkpoint` to page through the exact JSON source supplied to
the summary call (4096 characters by default, at most 8192). Earlier checkpoints
are linked by `previous_checkpoint_step_id`. Existing large-result previews still
require `agent.read_tool_result` for their omitted data. Both readers enforce the
current Run/Session boundary. Context audit records identify adopted/rejected
checkpoints; request hashes cover durable requests before provider transformation.

Limitations: pressure is still measured in serialized UTF-8 bytes, not the actual
routed model token window. Structured validation does not prove semantic fidelity;
older user constraints can still be omitted by a poor summary, while the current
input and system instructions are pinned verbatim. Multi-modal summarization,
accurate routed token admission, automatic recovery after provider failure and
real-model long-task success/cost benchmarks remain outstanding. Byte limits and
Run budgets can still stop a task; this is bounded continuation, not indefinite
execution or a guarantee against forgetting.

## Checkpoint v2: exact user evidence and durable execution state

`context-checkpoint/v2` is a local extension, not an assertion that upstream
DeepSeek has an equivalent semantic-coverage verifier. For every covered history
group, user messages are copied verbatim into `verbatim_user_records`, with their
source group/message positions and content hashes. These are ordered evidence,
not automatically extracted current constraints: later corrections do not erase
older records, and contradictory requirements still require interpretation.
The current input remains pinned separately. Model-generated summaries cannot
edit these records. The source list is persisted in the checkpoint request and
its hash in host metadata, validated during replay. Projection verifies that the
emitted user evidence matches the covered source and audits its count and hash.
This checks exact text coverage, not semantic accuracy of generated summary facts.

After adopting a checkpoint, each normal model request includes an assistant-level
execution-state block rebuilt from the current Run snapshot and stored plan.
It contains plan revision/items, Tool step IDs/status/error codes, and interaction
IDs/revisions/status. Text/menu question prompts and answers are retained exactly;
approval response bodies are excluded. A completed Tool step is not proof of a
successful task, and this state block cannot grant Tool permissions. State is
refreshed independently of the summary and its hash is included in context audit;
its exact content is durable in the following model request. Artifact validity
and final acceptance criteria are not independently verified by this version.

When the checkpoint reader is available, byte admission no longer drops old
history as a fallback. Protected text and rebuilt state consume real budget;
if they cannot fit, the Run reports context_budget_exceeded instead of deleting
those records. Existing v1 checkpoints are not adopted under v2; v2 regeneration
may run within the existing step/attempt budgets. Multimodal transcripts continue
to skip compaction and are subject to the same protected admission when the reader
is enabled. Disabling the reader retains the previous byte-admission behavior.

Scope remains the transcript loaded for this Run. The existing history message
count limit and 1000-message repository query can exclude older Session messages
before this policy sees them. This version is not a full-session requirements
registry, does not prove that every important fact is retained, and does not add
an autonomous second-model semantic judge. Actual routed token accounting and
real-model long-task benchmarks remain outstanding.

## Independent Python context engine

Checkpoint selection and replacement validation now pass through
`agents/context_engine_adapter.py` into the standard-library-only
`ai2apps/context_engine` package. The engine can be copied out and tested without
importing AI2Apps. Its public Surface/Route/Meter/Summarizer/Store contracts isolate
upstream policy updates from business Tools. Independent acceptance runs in a new
venv before host regression; see `docs/ai2apps-context-engine-python-port.md`.

The host bridge currently aggregates already-balanced rounds, retains the two
newest rounds, and uses explicit `utf8_bytes` measurement. Context audit identifies
`deepseek-context-python/1` and `token_count_exact=false`. Independent token-budget
and transactional overflow APIs do not imply the host has routed-token counting
or provider-overflow recovery enabled. RunStep persistence and recovery still own
host summary calls. Full Session surface/overflow integration remains pending.


Session conversation memory now projects original Message IDs and complete old Run tool rounds across Runs. Summary steps are excluded from decisions, atomically journaled with source CAS, and retain exact user records. `agent.read_session_memory` reads only same-Session sources; `POST /sessions/{session_id}/memory/compact` queues one maintenance compaction with no task answer. Native text token/window measurement is injected through `AgentRuntime.bind_context_provider`; unsupported routes explicitly fall back to bytes. Confirmed context overflow has one bounded recovery, including logged old input-image omissions, with no tool replay. See `ai2apps-context-engine-python-port.md` for compatibility and activation limits.
