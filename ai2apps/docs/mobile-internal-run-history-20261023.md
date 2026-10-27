# Internal executor Runs in conversation history

The reported phone conversation contained three user-facing General Agent Runs
and two internal execution roots. The session history endpoint filtered child
Runs but did not honor the executors' existing `discoverable: false` declarations,
so the internal roots appeared as extra completed conversation cards.

The conversation-specific Session history projection now uses the same trusted
Agent-definition discovery declaration as the Agent catalog. No display-name,
executor-prefix, App or site filter was introduced. Owned internal Run detail,
status, execution and diagnostic records remain unchanged, as do the parent
Agent's existing progress, interaction and final-result channels. This projection
does not grant authority or change task lifecycle/delegation.

Ten mobile transport/history tests passed. They cover two arbitrary internal
identities, a user-visible Agent deliberately named Browser Builder Runtime,
unchanged internal detail access, cross-Session isolation and no history-read
execution. These are API fixtures, not a phone-device screenshot acceptance.

Read-only verification on the actual phone Session found five root Runs and three
conversation-visible Runs, excluding exactly the two internal executors. Idle Dev
Local was restarted through its Helper: PID13997 / port54871 / boot
`8d334b25-e5a1-4bd4-93c5-56169b7d96b0`. App/Helper live source-root metadata,
Local adapter import path and both mobile served script bytes were verified.
Refreshing the phone page reloads existing history through the repaired endpoint.

Mandatory AaAT boundary gate: 252 passed, exit 0; the existing headless Metal
atexit warning did not affect the successful result.
