# AI2Apps Todo × Codex Desktop MVP

Local-only plugin with five MCP tools: `todo_list`, `todo_read`, `todo_create`,
`todo_bind`, `todo_update`. It stores project/chat bindings and the last 30
progress summaries on each Todo task. The UI displays the latest five summaries.

## Connect

1. Start the intended AI2Apps Local instance and open Todo.
2. Select the link icon (Codex) in the Todo header. Click **连接 Codex**.
   This authorizes task read/create/update for the current account on this
   instance, including task descriptions and attachment metadata.
3. Copy the **path**, never the contents, of the displayed connection file.
4. In a terminal run:

   ```sh
   python3 install.py --connection '/absolute/path/from/Todo.json'
   ```

   This prepares a dedicated `ai2apps-local` marketplace in
   `~/.codex/ai2apps-todo-local`, then uses `codex plugin marketplace add` and
   `codex plugin add` to install `ai2apps-todo`. Other plugins are untouched.
   Installation may be prepared before connecting; tools then remain unavailable
   until the connection file exists. Open a new Codex chat to load tools/skills.
   Restart Codex Desktop if its plugin catalog has not refreshed.
5. Try: “用 AI2Apps Todo 查找视频项目”, then “把当前对话绑定到这个待办”.

For another Local/another account rerun the installer with its explicit path.
The plugin never scans for another instance or falls back to Production.
Disconnect in Todo revokes access immediately; reconnect rotates the credential
at the same path. No public marketplace publication or Cloud service is involved.

## Behavior

- A task has one explicit primary Codex project and one explicit primary chat.
- Descendants inherit project fields; they never inherit the parent's chat.
- `inherit_project=false` stops project inheritance. Empty binding clears explicit
  associations and restores inheritance. `todo_bind` replaces the whole binding;
  read first and preserve desired fields.
- Project IDs and thread IDs must come from trusted Codex context/tools. A path
  is allowed without a registered Desktop project ID. The plugin's `--context`
  helper can read CODEX_THREAD_ID when invoked by the shell in the calling chat.
- Mutations require a current task revision. Summaries append independently of
  completion; binding does not start a run or consume Todo queue slots.
- Associations and summaries travel with existing Todo backups. Connection
  credentials do not. Imported Codex IDs/paths may refer to the original host.
- This MVP does not control Desktop sessions, send messages, auto-track turn
  events, download attachment contents, or mark a task complete when a turn ends.
  These are explicit future extensions, not implied by the connection.

## Local transport and testing

The stdio adapter uses Python's standard library and talks only to the paired
loopback listener. The bridge validates a random token bound to the authenticated
Todo owner and checks current App access on each request. Config files are 0600,
inside a 0700 directory; tokens never enter MCP output. There is no shared main
API key, cookie/profile inspection, or direct Codex/Todo database modification
from the plugin. Service restart refreshes the endpoint in the same config file.
Connection failure leaves the rest of Todo available.

`server.py --config PATH --call todo_list` reads JSON arguments on stdin, useful
for a deterministic diagnostic without starting a model. Do not print config
file contents. Tests exercise real MCP subprocess/loopback traffic with temporary
accounts and stores, revocation/restart, revision conflicts, owner isolation,
inheritance, and backup round-trips.

## Todo → Codex Desktop (App Server)

Todo's **Execution → Codex Desktop → Choose project / conversation** connects through
an installed local Codex App Server. It reads saved Desktop project names and primary directories through the shared
read-only metadata adapter, with conversation-directory fallback. Choosing a project
automatically loads its conversations. Users can bind an existing conversation or
choose to create one when executing.
A local directory can also be entered for a project with no previous conversations.
Saving a binding validates the conversation's directory, uses optimistic revisions,
and selects the `codex_desktop` executor without sending a prompt.

Execution uses Todo's FIFO queue (default three slots). New conversations are
created via App Server and saved before the first turn. Existing conversations are
sent through the native `codex queue` command, so Desktop retains writer ownership.
Unique run markers correlate queued messages with read-only turn history; output
and terminal timestamps update Todo. Restart resumes observation without resending.
Desktop-owned approvals, replies and stopping are handled in Desktop; Todo provides
an open-conversation link. New App Server conversations retain in-panel approvals.
Turn completion is `ended` pending user confirmation, never automatic task completion.

The feature uses the system Codex service and requires Coder permission. Todo MCP
pairing is independent and is not required for outbound Desktop integration. Only local
paths/hosts are supported. It does not open Cloud tunnels, read Desktop private
SQLite files, or silently approve actions. API calls are made by Local, not by
borrowing private Codex Desktop tool credentials. App Server `notLoaded` is not a
Desktop-wide idle indication; Todo does not use it to infer external activity.
Native messages wait in Desktop’s queue; Todo does not seize its writer.

Validation on 2026-10-05: the transport listed the current AI2Apps conversation and
completed an ephemeral, read-only, no-tools fixed-reply turn. Automated tests cover
binding revisions/directory matching, new/resumed runs, approvals, cancellation,
connection loss, and slot cleanup. Native App-Dev selector rendering was checked;
its running Local still requires a restart to load the new Python routes.

System architecture and API contract: [Codex service](../../codex/README.md).
