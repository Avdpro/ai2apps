# Local health and Task completion

## Failure mechanism

An `async def` coroutine runs synchronous Python/SQLite work on the same event
loop until it reaches an actual suspension point. SQLite's busy handler can wait
up to five seconds for another writer. That wait releases the Python GIL but
does not release the event-loop thread. WAL and connection pooling do not make
this call asynchronous. HTTP requests, including the two-second Helper bootstrap
probe, can consequently time out while the Local process is alive.

Observed stacks included System Task admission/progress, periodic owner schedule
publication, Local/Admin/Shell Session authorization, Todo's system schedule
sync, idle worker eviction, Agent schedule reconciliation, and Local installation
identity projection.

## Changes

- Run bounded synchronous database work in worker threads: task admission and
  settlement, AppChat progress, periodic schedule publication, model history
  freezing/projection, and per-request identity resolution. Keep transaction
  ownership inside each synchronous work unit. Never keep a transaction open
  across a coroutine suspension.
- Background Agent schedule passes and local identity projection writes also
  wait off the loop. The projection is still validated and committed before
  returning; no Cloud-side API or authorization policy is changed. Agent wake
  signals from worker threads are posted to the owning event loop.
- Serve bootstrap through FastAPI's synchronous endpoint worker pool. Its
  status, instance/boot identity, device label, and authorization rules remain
  unchanged. This is not an unconditional liveness endpoint or a cached login.
- A single transient probe failure triggers rechecking without a gray icon.
  Two consecutive failures show degraded status; three preserve the configured
  automatic restart. A dead process or mismatched bootstrap identity is a
  definite failure immediately. A successful probe resets the counter.
- Cancelled monitors cannot publish after returning from an outstanding probe.
  A response for an obsolete boot cannot mutate the new supervisor state.
- Agent and Todo completion callbacks carry the exact completed asyncio Task.
  A stale callback cannot remove a replacement execution under the same durable
  Run ID. Agent terminal inspection is performed off the loop; notifications
  return to the loop and tracked cleanup is drained during shutdown.
- System Task settlement checks the current attempt and cancellation in the
  same transaction as the Task/attempt terminal updates. Waiting for a worker
  or database lock cannot let a late success/failure overwrite cancellation.

Task permissions, revocation/version checks, cancellation, and protection against
replaying operations with unknown outcomes are unchanged. No business capability
names or App identities participate in the shared execution decisions.

## Verification

- Real SQLite writer contention tests cover System Task admission/progress and
  Todo schedule publication while checking event-loop responsiveness.
- Callback tests cover requeued executions, completed/failed/cancelled results,
  replacement during the terminal read, and Todo watcher replacement.
- Native tests cover one timeout, separated timeouts, sustained failure,
  recovery, and definite failure. Existing bootstrap identity tests remain.
- Additional core Agent tests exposed an unrelated invalid `trace_id` keyword
  passed to `MessageRepository.get`; the valid Session restriction is retained
  after removing that unsupported keyword. Five older execution/permission
  fixtures now explicitly select their tested Tool rather than assuming that
  lazy discovery exposes every schema in the first model request. Their
  durability, restart, loop and permission assertions remain.
- Live Dev runs and fault-injection evidence are recorded separately from
  fixture tests in the acceptance receipt. The first live pass exposed Todo's
  remaining blocking path; it is retained as diagnostic evidence, not described
  as a zero-timeout result.

Acceptance: `acceptance/helper-health-task-responsiveness-20261118.json`.
