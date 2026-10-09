# AI2Apps system Codex integration

`PlatformRuntime.codex` owns the local App Server integration. It does not import
Todo or require Todo plugin pairing. Todo is its first consumer; Chat, Coder and
other trusted services can use the same manager.

Responsibilities:
- `transport.py`: App Server process, protocol handshake and message transport.
- `manager.py`: directory/session discovery, one active turn per conversation
  across AI2Apps consumers, output and status notifications, owner-scoped approvals
  and structured replies, cancellation and shutdown cleanup.
- `api/codex.py`: `/v1/platform/codex/status`, `/projects`, `/threads?cwd=&cursor=`,
  and `POST /requests/{token}`. All require `APP_CODER_USE`; replies additionally
  require the request owner's identity and a live single-use token.

Trusted Python callers authorize their principal and await `execute(run_id, owner,
...)`, providing cwd, title, prompt, optional thread_id/model/writable_roots,
`on_update(status, **fields)` and async `on_thread(thread_id)` callbacks. The new
thread callback completes before the first turn starts. Cancel the awaiting task
to interrupt. Runtime shutdown cancels and awaits active callers. The caller owns
its queue, persisted run records, timeout and UI; this service does not impose
Todo's three-slot queue on other applications. Callbacks must not block.

Todo retains task bindings, revisions, its queue and execution records. The reverse
Codex-to-Todo MCP plugin remains a separate optional integration. General queries
and replies no longer go through Todo routes.

Project discovery first reads only saved local project names and primary roots from
Desktop's `.codex-global-state.json` under CODEX_HOME (or ~/.codex). This is a
read-only compatibility adapter, not a documented App Server project API; it never
writes Desktop settings or returns unrelated state. Modern local-projects metadata
and legacy saved roots are supported. When unavailable/empty, discovery falls back
to conversation working directories (up to 1,000 sessions with truncation marked).
Multi-root projects use their primary root for execution and conversation filtering.
The Todo selector displays explicit project choices and loads conversations on change.
The lock covers this AI2Apps runtime, not independent
Desktop turns or another Local instance. Do not concurrently operate the same
conversation there. Live approvals are in memory; service restart interrupts
owned runs and does not silently replay or approve them.

Validation: transport execution was previously verified with an ephemeral read-only
turn. Extraction tests verify standalone APIs without Todo, cross-consumer session
exclusion, ownership, cancellation, shutdown and Todo binding persistence. Native
App-Dev end-to-end verification still requires restarting its Local service.

## Native Desktop delivery (2026-10-06)

Existing conversations now use `codex queue --thread ... --message ...`, without
resume, turn/start, unsubscribe or interrupt against the Desktop-owned conversation.
The prompt includes a unique `[AI2Apps run:<id>]` receipt marker. Todo persists
send intent before delivery, then stores the queue message ID and follows the
matching user-message turn via read-only `thread/turns/list` pagination. Assistant
output and the latest visible item update the execution panel. A terminal status
requires `completedAt`; unloaded history may report an active turn as interrupted.
Successful completion remains `ended`, requiring task-result confirmation.

Native runs retain a Todo slot while queued or executing in Desktop. Restart only
resumes observation, never resubmits. Ambiguous delivery is kept pending for receipt
rather than automatically retried; an explicit CLI rejection is failed. Monitoring
reconnects without sending another message. If the Desktop queue is manually cleared
before execution, no turn receipt is available: this version cannot automatically
reconcile that removal and the run remains pending. This is an outstanding boundary.

Approvals, replies and stopping occur in Desktop under that session's own permission
policy. Todo links to Desktop and rejects local cancellation of these runs; stopping
an observer must not pretend to stop Desktop. No local writable-root or approval
settings override the Desktop-owned session. Attachments are listed as local paths
in the queued prompt and may require Desktop approval to read. New conversations
still use the direct App Server path; later runs use native delivery.

Verification: real native queue message consumed by Desktop; the new observer read
its exact final reply and terminal turn. Regression coverage includes restart without
resending, owner-session routing without resume, uncertain receipt, terminal timestamp
requirements, marker matching, and rejection of false cancellation. App-Dev activation
requires Local restart and is separately verified from these protocol tests.

## Structured results

Both execution paths ask for a version-1 `ai2apps-result` JSON fence in the final
assistant reply, bound to the Todo run ID. Valid outcomes are completed, partial,
waiting_user and failed; summary, completed work, verification, remaining work and
an optional user question are required fields. Only terminal assistant replies are
parsed, never tool output. Native observation uses the matching turn's final reply.
Missing, malformed, contradictory completed reports, and wrong-run results are
marked unavailable and retain the original output. Reports are stored on the run,
shown in current/history views and explicitly labelled agent self-assessment.
Neither task status nor progress is automatically changed. A waiting_user result
means the turn has ended asking for input, not that an active process is still running.
