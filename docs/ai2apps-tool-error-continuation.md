# Python Tool error continuation

Reference: official `deepseek-ai/deepseek-harness`, commit
`5badb15009ae1756c3afe0ae0cef1faafc290ccc` (MIT), reviewed from the local reference
checkout. Relevant source: `packages/core/tools/src/index.ts` (`prepare`,
`dispatchToolBody`, `dispatchScheduledExecution`) and
`packages/core/agent-loop/src/tool-calls.ts` (`executeToolCalls`, `appendToolResult`).

DeepSeek represents ordinary execution exceptions and unknown-tool errors as
`isError` results, appends them in model call order, and allows another model
step. Cancellation and scheduler invariant failures have separate control paths.
This Python implementation adopts the paired-result behavior; it is not a literal
TypeScript port or a claim of complete upstream parity.

## Module and host boundary

`ai2apps/agents/tool_recovery.py` has only Python standard-library dependencies.
It classifies stable error codes, limits recovery and builds bounded error
results. `models.py` adds the explicit `ToolErrorAction` for rejected model calls
that must never dispatch. General Agent opts into `recover_tool_errors`; other
executors retain their prior terminal behavior unless explicitly enabled.

`runtime.py` records a FAILED tool step before requeuing. `general.py` rebuilds a
paired tool response using the original `tool_call_id` and proceeds through the
remaining calls in the same batch. It then asks the model for a new decision.
Completed calls and rejected calls are not automatically replayed. Original raw
model calls remain in the durable model output, including malformed arguments.
`session_memory.py` includes these paired failures in historical tool rounds and
continues to recognize legacy `recoverable_input_error` records.

## Current recovery policy

| Failure | Behavior |
| --- | --- |
| Invalid JSON/non-object tool arguments, unavailable alias, invalid question arguments | Record a rejected call without dispatch, then ask the model to correct it |
| Schema rejection, timeout, provider exception, invalid output, provider/service unavailable, disabled tool | Continue only when the tool declares no effects |
| Capability denial, provider identity mismatch, missing Session, unknown error codes | Preserve terminal behavior |
| User cancellation | Preserve cancellation, no new model decision |
| Execution failure for a tool declaring effects | Preserve terminal/uncertain-state protection; no new recovery or replay |
| Entire tool call missing its function structure | Preserve malformed-call terminal behavior |

Recovery is a new model decision, not a promise to retry or to finish the task.
There are at most three model-visible failures per run, shared across preparation
and execution failures and legacy input errors. The next failure ends the run
with its original error code. Existing step, deadline, model token and tool-loop
budgets still apply. This conservative limit is deliberately tighter than a full
upstream error-as-result policy. Tool effects metadata must be accurate.
Existing gateway retry policy remains separate and unchanged; effect replay
already requires its explicit `allow_effect_replay` contract.

The gateway redacts injected secret values from provider exceptions and now also
from output-schema validation errors. The model envelope includes code, bounded
message (2048 characters), phase, retryable hint and an explicit instruction not
to assume success. It excludes exception details, stack traces and injected
arguments. `retryable` is informational; it does not authorize replay.

## Validation and activation

Tests use temporary databases and simulated local providers. Coverage includes
paired mixed-result batches, JSON/alias rejection, actual deadline timeout,
provider/output failures, legacy schema correction, bounded recovery, write
protection, cancellation, fresh transcript reconstruction, historical memory,
secret redaction, non-opted-in executors, and host restart between the failed
batch and the next model response. The standalone policy also imports and runs
under `python3 -I` without host dependencies.

Acceptance results are recorded in `docs/tool-error-continuation-acceptance-2026-10-05.json`.
No real-model success-rate evaluation or complete DeepSeek parity suite has been
run. All three fixed Dev/App-Dev/Test Apps were subsequently rebuilt and restarted.
Fresh instance identity/health checks, strict code signatures, source equality and
App-Dev native-title verification passed. Activation evidence is recorded in
`docs/tool-recovery-instance-activation-2026-10-05.json`.
