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
