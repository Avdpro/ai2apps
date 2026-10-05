# Native AI2Apps App development

Coder's **AI2Apps Agent** develops, modifies and tests AI2Apps source Projects
without an external coding CLI. Select an AI2Apps Project, open the button,
choose an available AI2Apps model and enter a task. Empty Projects can be used
to create an App or Mini-App. General software Projects retain the CLI workflow.

## Workflow

1. The task copies eligible source files into an independent Session workspace.
2. The model inspects the project contract, reads/searches files, edits the draft,
   runs commands, validates manifests and requests a static preview.
3. Continue adds a follow-up to the same durable task and conversation. Closing
   the panel does not cancel the task. Stop cancels its active Agent Run.
4. **Review & Preview** displays the source diff and validation results.
5. **Apply changes** writes the reviewed revision back only after the task stops
   and the source baseline still matches. After applying, start a new draft.

The task inherits General Agent planning, user questions, context memory and
tool-error continuation. Failed test commands return their exit status and logs
as normal results, allowing diagnosis and repair. Long commands return a process
ID; subsequent reads continue the same process rather than rerunning it.

## Independent core and host adapter

`ai2apps/app_development/core.py` uses only Python's standard library. It owns
source copying, path boundaries, observed-file SHA-256 checks, exact text edits,
diff revisions, source conflict detection and write-back backups/journals.
`service.py` adapts this core to existing AI2Apps accounts, Sessions, Agent Runs,
process sandbox, source validators, event storage and tools. Coder API/UI are
thin entry points; existing external CLI Threads remain available.

Eleven tools cover inspect, list, read, search, write, edit, validate, preview,
changes, command and command_status. Model tool calls only operate on the draft.
The authenticated user controls write-back through the Coder API.

## DeepSeek source reference

Reviewed upstream: [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness),
MIT, pinned commit `5badb15009ae1756c3afe0ae0cef1faafc290ccc`.
The implementation follows mechanisms from `packages/fs/tool-fs/src/read.ts`,
`edit.ts` and `packages/shell/tool-bash/src/index.ts`: bounded line reads,
read-before-edit observations, unique literal replacements, explicit command
working directories, normal nonzero exit results and continued background reads.

This is a Python adaptation for AI2Apps, rather than a wholesale runtime port.
It adds an isolated draft and reviewed write-back and reuses existing host
services. It does not import DeepSeek runtime modules or introduce its complete
shell/tool surface or sub-Agent system.

## Boundaries and current limitations

- Eligible source is bounded to 512 files, 32 MiB total and 8 MiB per file;
  UTF-8 edits are limited to 2 MiB. Symlinks, dependency/build directories and
  common credential files are excluded. Exclusions are visible in review.
- Commands use the existing process service with networking disabled. Managed
  Runtime Python is explicitly readable/executable inside its sandbox; the
  original project and protected draft state are outside command write access.
- Preview is a restrictive static HTML iframe with no network access. It is not
  full host Bridge execution, automated browser debugging or visual acceptance.
  Use the existing component development/TestFlight workflow after applying for
  host integration checks. No packaging, installation or publication tool is
  exposed to this Agent.
- File deletions cannot be applied in this version. An App/Mini-App component
  must pass source validation before write-back. Validation is not a substitute
  for functional tests, mobile acceptance or Studio integration checks.
- Each file replacement is atomic; a multi-file apply is not a transaction.
  Original files are backed up and a progress journal is persisted outside the
  command workspace. If an I/O failure interrupts write-back, inspect that
  receipt and backups before manual recovery; source conflicts prevent blind
  replay. Do not run simultaneous external edits during Apply.
- Voice Studio output producers must follow the host-owned Quick Read Preview &
  Output contract; this is also included in the Agent's authoring instructions.

## Acceptance

The isolated standard-library core suite, simulated-model repair/generation
loops, owner-bound APIs, restart continuation, UI behavior and actual macOS
Seatbelt tests passed. Tests cover a failing command followed by model repair
and a passing command, background process reads, App and Mini-App validation,
preview, stale edits, source conflicts, reviewed write-back and foreign-project
read denial. These establish mechanics, not a benchmark of real model quality.
See [acceptance receipt](native-app-development-acceptance-2026-10-05.json).

Live App-Dev displayed the enabled native entry and model/task/review panel on
an isolated acceptance Project. Dev/Test bundles were not rebuilt for this
feature in this turn; Test needs a new source snapshot to include it.
