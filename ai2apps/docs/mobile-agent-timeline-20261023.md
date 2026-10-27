# Mobile Agent conversation ordering

Mobile Chat previously rendered persisted messages first and appended one separate
Agent-run container after all messages. This grouped historical failures and live
process cards below the final answers rather than within each conversation turn.

The message renderer now preserves `metadata.agent_run_id` as a DOM association.
Each run card is placed after its matching user input, or before its matching
answer if the input is absent. Timestamp ordering is only a fallback for legacy
messages without the run association. It never matches by prompt text. Submitted
Agent inputs appear immediately and acquire the actual returned Run ID.

The run presenter keeps card-node references independently of the fallback
container. Message rebuilds detach and reinsert the same nodes, preserving live
forms and their drafts; stopping or changing the selected conversation removes
all of its cards. This affects presentation only, without resubmitting tasks or
changing Agent execution, authorization, or business interpretation.

Validation: 24 Node/Chrome tests passed, including reversed server Run order,
two conversation turns, page reload and visibility-triggered recovery, no duplicate
cards, existing parameter-draft recovery, rich results and normal Chat behavior.
These are browser fixtures, not a phone-device acceptance claim. Dev PID8696 /
port52765 serves both changed scripts byte-for-byte from the live checkout;
App and Helper source-root metadata were verified. The frontend-only change
requires a phone page refresh and does not require a Local restart.

Mandatory AaAT boundary gate: all 252 tests passed, exit 0. The existing headless
Metal atexit warning did not affect the result.
