---
name: ai2apps-test
description: Plan, run, resume, and report AI2Apps P0-P3 tests against the isolated AI2Apps-test App, including Codex Computer Use jobs. Use for AI2Apps smoke tests, QA, visual review, and release acceptance.
---

# AI2Apps Test

Use `/Users/avdpropang/sdk/omlx-moe-cache/ai2apps-test-system` as the Codex project and Harness root. The parent repository remains the product, Inventory, Test App, and `tests/ats` fact source.

## Workflow

1. Run `./bin/ai2apps-test doctor`.
2. For an explicit priority or unattended request, inspect `./bin/ai2apps-test plan --priority <P0-P3>` and run with `--driver codex --unattended`.
3. When the user wants to choose scope, start `./bin/ai2apps-test select --priority <P0-P3>` as a yielded process. The page remains available for live progress and cancellation; read the run ID from the process output after the user starts the run.
   On-demand Groups have no P level and must never be added by a priority preset. Include them only when explicitly selected in Test Center or named with `--group`; explicit `--case` selections are combined with the priority scope and recorded in the immutable Plan.
4. Before UI work requiring `test-account`, confirm `./bin/ai2apps-test account doctor` is healthy. The Harness leases and logs in the account automatically. Never read, print, request, type, or place the temporary password or lease token in a prompt, command, result, or evidence.
   For a UI case expected to run longer than one hour, invoke `./bin/ai2apps-test account heartbeat --run <run-id>` between material stages; normal queue reads and result recording heartbeat automatically when due.
5. Read each UI job with `./bin/ai2apps-test next --run <run-id>`. Recheck immediately before each material UI action and after the action finishes; if it returns `cancelled`, stop without starting another action.
6. Target only `com.ai2apps.desktop.test` and instance `test`. The privileged AI2Apps Shell chrome is not a WebDriver BiDi browsing context: use Computer Use for Shell navigation, App/Mini-Entry launching, native windows, visible-state checks, and cross-context or macOS drag operations. Use the protected AI2Apps WebDriver BiDi Gateway only when a Case explicitly targets an AI Browser webpage browsing context and the Harness has provided a validated, authenticated Test-bound context. Never substitute a generic Chrome/Firefox BiDi connection, and do not enumerate generic browser contexts while testing the Shell.
7. After each UI action, read fresh state and save evidence inside the run directory.
   For every Computer Use Shell connection, use `cua.getApp("com.ai2apps.desktop.test.shell")`. The outer `com.ai2apps.desktop.test` identity and `AI2Apps-test.app` path are for Harness launch/identity checks only; never pass them to `cua.getApp`. They select the launcher rather than the visible Shell.
   On timeout, check the actual target first. If it was the outer App, retry with the exact `.test.shell` ID before reporting a blocker. If the correct Shell still times out, record the target, call, error and retry outcome. Never switch to another instance.
8. Record a JSON result using `./bin/ai2apps-test record --run <run-id> --case <case-id> --result <file>`.
9. Repeat until `next` returns `done`. The live controller finalizes automatically after the last UI result and releases any test-account lease. Stop requesting or recording work immediately if `next` returns `cancelled`.
10. Report the conclusion, scope, exclusions, failures, account cleanup state, and clickable report path.

## Pipelines

- Use Test Center **Pipeline** or `pipeline list/plan/run` for a saved, strictly ordered trajectory of Cases and Test-only lifecycle actions.
- Preserve the order barrier: never execute or request a later step until the current UI Case has been recorded.
- Record the observed Case status only. A Pipeline's `expectedStatus` is compared by the Harness; never reinterpret an expected failure as an observed pass.
- Pipeline actions may target only `com.ai2apps.desktop.test` / instance `test`. Data reset must use the authenticated Helper `InstanceDataReset`, never direct directory deletion.
- The same Case may appear more than once. Use the compiled Pipeline step Case ID returned by `next`, not the source Case ID, when recording its result.

## Catalog management

- Use Test Center **管理测试** or `catalog list/validate/diagnostics` for Catalog work. Definitions live only under the parent repository's `tests/ats/catalog/`.
- Generated Cases are read-only. Copy them to a user-authored Group before customization.
- New Cases start from a natural-language test description. The Test Center may use
  Codex to generate a schema-constrained draft, but that draft must remain disabled
  and unsaved until the user reviews it through the normal validation and Diff flow.
- User-authored `codex-ui` Cases use structured instructions, expectations, and cleanup. Never place arbitrary shell commands or secrets in editable fields.
- After an isolated trial run, use the structured Codex review when the user wants to improve the Case. Separate Case edits, required user materials, and product/environment/Harness issues. State missing fixtures and human ground truth precisely; never find or invent substitute media. Managed fixtures must stay under `tests/ats/fixtures/<case-id>/` and must be reviewed through the normal Diff/save/retrial flow.
- Never weaken expectations to turn a real product failure into a pass. Trial review proposals preserve the stable Case ID, Group, and Executor, remain unsaved until user confirmation, and require another validation/trial cycle after material changes.
- Respect revision conflicts, preview diffs, prefer archive/restore to deletion, and trial-run changed Cases before enabling them.
- Use `catalog review-inventory --apply` only when intentionally accepting the current component contract baseline; diagnostics must remain visible in Plans and reports.

## Boundaries

- Never target production `default`, development `dev`, or `app-dev` instance data.
- Validate the fixed Test App identity before state-changing work.
- Do not treat pending, missing, or blocked cases as passed.
- Do not update visual baselines during a test run.
- Treat cancellation as terminal. Never convert skipped cancellation results into pass, fail, or blocked results.
- Treat a case failure, timeout, blocked dependency, or executor error as local to that case. Continue with independent cases; stop the whole run only for a Harness-level state or persistence failure.
- Record unexpected permission, account, payment, production-write, or identity conditions as blocked.
- Product changes are outside a test-only request. Report `testability_gap` when stable UI anchors are absent.
