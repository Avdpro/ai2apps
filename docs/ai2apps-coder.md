# AI2Apps Coder

Coder is the singleton development App for terminal-based coding Agents. A
Project binds a user-visible name to one host directory. A Thread selects one
CLI (`codex`, `opencode`, or `claude`), a model source, and an independently
owned Terminal session.

## Runtime boundaries

- `CoderManager` stores Projects and Threads in the platform SQLite database.
- `TerminalManager` owns the PTY and child process independently from browser
  WebSocket attachments.
- Selecting `Agent CLI default` executes the installed CLI without changing its
  model configuration.
- Selecting `AI2Apps model` executes `ai2apps launch <agent> --model <id>` and
  therefore reuses the existing Codex, OpenCode, and Claude integration logic.
- Closing or backgrounding the App disconnects the browser only. `Stop Thread`
  terminates the PTY process group.

## AI2Apps source Projects

When bootstrap is selected, Coder creates files only when they do not already
exist:

```text
.ai2apps/project.json
AGENTS.md
docs/AI2APPS.md
```

The generated instructions tell coding CLIs about the real current package
contracts: `.ai2app`/`app.yaml`, `.ai2agent`/`agent.yaml`, and
`.ai2service`/`service.yaml`. Archive validators remain the source of truth, so
the instructions do not duplicate volatile implementation details.

The generated guide also contains the Mobile-ready authoring contract. Coder
must treat `mobile.ready: true` as a verified compatibility assertion. It tells
coding Agents to use package-relative indexed assets, comply with the Mobile
CSP, avoid desktop/admin routes, use only the constrained Mobile Bridge and
Mobile APIs, and complete phone-viewport plus authenticated remote-session
testing before opting an App into the Mobile Catalog.

One Project Bundle may contain multiple source components. The v1 descriptor is:

```json
{
  "schema": "ai2apps.project/v1",
  "id": "example.product",
  "name": "Example Product",
  "version": "0.1.0-dev",
  "components": [
    {"type": "app", "manifest": "app/app.yaml"},
    {"type": "mini-app", "manifest": "mini-app/mini-app.yaml"},
    {"type": "agent", "manifest": "agent/agent.yaml"},
    {"type": "service", "manifest": "service/service.yaml"}
  ]
}
```

An App's `mini_entry` is discovered as a Mini-App component. A standalone
Mini-App may instead use `mini-app.yaml` and `type: "mini-app"`. The older
`{"kind": "app", "path": "."}` descriptor remains accepted.

A Mini-App is a user-facing interactive component with its own UI entry. It is
not a headless Pipeline and not an Agent Tool. A Studio may mount Mini-Apps,
but does not own them: one canonical Mini-App installation may declare explicit
placements in multiple Studios while retaining one package identity and
version. `mini_entry` is an embeddable App surface; it becomes a synthetic
Mini-App component during discovery, but the two terms are not synonyms.

### Recommended Help and Mini-App Chat capabilities

Help and conversational control are recommended authoring capabilities, not
requirements of the Mini-App definition. A Mini-App remains valid and can be
installed, discovered, mounted, and run without either capability.

Authors should nevertheless provide at least a concise, task-oriented
`help.md` when practical. It should explain the Mini-App's purpose, required
inputs, normal workflow, important settings, and common failure recovery. Help
must not contain secrets or grant authority. The current Studio Package
integration declares this bounded Markdown resource inside the optional
`ai2apps.mini-app-chat/v1` contract so the host loads it only when the user asks
for help; the Markdown is not included in normal model Context.

There are two recommended adoption levels:

- **Help-only:** declare `help.md`, return an empty or minimal current Context,
  and expose no operation Tools (`tools: []`). The shared Chat-Mini-Entry can
  answer usage questions but cannot change or run the Mini-App.
- **Chat-control:** additionally provide useful current-state Context and an
  explicit allowlist of operation Tools. Effectful Tools remain subject to
  host validation, capability checks, and confirmation policy.

`Mini-App-Chat` must never be inferred merely because a component is a
Mini-App. Studio displays the Chat entry only when the selected Mini-App
explicitly declares the capability. The versioned Package form and security
rules are defined in `docs/ai2apps-studio-mini-app-package-contract-v1.md` and
`docs/ai2apps-mini-app-chat-architecture.md`.

If an App Package is only a container/provider for Studio Mini-Apps and has no
coherent standalone App surface, its `app.yaml` should declare
`navigation.launcher: false`. This hides only the provider Package from App
Launcher and Dock; it does not hide its Mini-App placements. Mixed Packages
that intentionally provide both an App and Mini-Apps remain launcher-visible.

## Shared capability target

The target Studio authoring model allows one Project/Package to contain
multiple Mini-Apps plus shared headless Pipeline and Service components. A
Mini-App consumes a versioned Capability contract; it does not call another
Mini-App or import another component's private implementation. Providers use
`provides`, consumers use `requirements.capabilities`, and runtime invocation
goes through the Host-owned Capability Broker with Resource Handles and
Artifacts rather than private paths or endpoints.

The future descriptor may therefore include components such as:

```json
{
  "components": [
    {"type": "pipeline", "manifest": "pipelines/extract-audio.yaml"},
    {"type": "mini-app", "manifest": "mini-apps/video-subtitles.yaml"},
    {"type": "mini-app", "manifest": "mini-apps/voice-replacement.yaml"},
    {"type": "mini-app", "manifest": "mini-apps/multilingual-dubbing.yaml"}
  ]
}
```

This is a target contract, not current Coder behavior. The current source
validator accepts only `app`, `mini-app`, `agent`, and `service`; it does not
yet accept `pipeline`, resolve Capability providers, or validate atomic
multi-component installation graphs. Those features require versioned schemas,
validators, Package lifecycle support, and the Host Capability Broker before
Coder may advertise them as runnable.

## Source development runtime

Coder provides four Project actions without installing anything:

- **Validate** uses the platform's App, Agent, and Service manifest validators.
- **Test** discovers `tests/` (pytest) or `package.json` (npm test) and captures
  bounded output.
- **Run** opens App and Mini-App `sandbox`/`safe-html` entries directly from the
  source tree in an isolated preview frame. Relative CSS, scripts, images, and
  other resources resolve from the entry file's real source path.
- **Build** creates `dist/<id>-<version>.ai2package`. This unified Project
  Bundle contains all components but is marked `development: true` and
  `installable: false`; it is not a replacement for signed release packages.
- **Submit to TestFlight** builds that development Bundle, verifies every
  indexed resource, and registers each App under an isolated
  `testflight.<original-id>` identity. TestFlight Apps appear only in the
  Launcher's permanent **TestFlight** category and execute from a read-only
  local store through the normal Shell runtime.

TestFlight is deliberately separate from formal installation. It accepts
unsigned development Bundles only, does not overwrite an installed App with the
same original id, and re-verifies resources when serving them. Formal App
installation requires a trusted publisher signature whose authority is either
the local owner or AI2Apps Root; other or unsigned packages cannot escape the
TestFlight channel.

The first version intentionally limits direct preview to browser-renderable App
and Mini-App entries. Agent invocation debugging, managed Service processes,
hot reload, and conversion of a development Bundle into signed component
archives are subsequent runtime layers.

## Mobile development gate

For an App that declares `mobile.ready: true`, Coder validation and review must
apply these rules:

- entry resolution remains `mobile_entry`, `mini_entry`, then `entry`;
- ordinary packaged Apps load CSS, JavaScript, fonts, and images through
  indexed package-relative URLs, never `/admin/static/*`, `/mobile/static/*`,
  localhost, or a CDN;
- the selected entry does not require inline CSS, inline JavaScript, inline
  event handlers, `eval`, or other behavior rejected by the restrictive CSP;
- phone code uses only the Mobile Bridge and documented `/v1/mobile/*` routes,
  and does not contain credentials, local API keys, unrestricted
  `/v1/platform/*` calls, or `/admin/*` calls;
- layout is tested at a narrow portrait viewport, handles safe areas and the
  virtual keyboard, remains scrollable, and ignores Enter submission during
  IME composition;
- authenticated Mobile testing shows no CSP, iframe, missing-resource,
  MIME-type, or forbidden-route errors.

Built-in host-rendered system Apps may use the runtime's exact Mobile static
allowlist instead of package-relative assets. They must extend the Mobile App
base template, enumerate every asset, and still produce no `/admin/static/*`
references or CSP-dependent inline CSS/JavaScript.

## Workspace controls and file editing

- The Project sidebar can be collapsed from the main toolbar. The preference is
  device-local and leaves the preview area at full Coder width.
- Projects, components, and Threads expose a context menu. Project removal only
  removes the database entry and always preserves its directory. Thread deletion
  stops the owned PTY before removing the Thread record. Components are derived
  from source manifests, so they are edited through Project Files rather than
  destructively deleted from the component list.
- Project Files is a host-directory browser with path traversal, symlink, hidden
  VCS/dependency directory, UTF-8, and 2 MiB file limits. Saves use an atomic
  same-directory replacement.
- The bundled Ace editor works without a CDN and provides language-aware syntax
  highlighting, code folding, find/replace, undo/redo, gutter line numbers, and
  Command/Ctrl-S saving. YAML, JSON, JavaScript/TypeScript, Python, HTML, CSS,
  Markdown, Shell, Go, Rust, Java, C/C++, XML, and plain text are included.

## Dock reveal control

The floating **Show AI2Apps Dock** button is presentation chrome, not an App
contract requirement. Host-rendered Apps may opt out with:

```yaml
presentation:
  dock_reveal: false
```

Coder opts out because its own toolbar occupies that corner. The Shell Bridge
still exposes `window.ai2appsShell.showDock()`, so an App may provide a Dock
action in a location that fits its own interface. App validation, registration,
mounting, and readiness never depend on the floating reveal button.

## Fork semantics

The initial implementation provides a durable structural fork: the child
Thread records `parent_thread_id` and inherits CLI/model selection. It starts a
fresh CLI process in the same Project directory. Native conversation forks and
isolated Git worktrees are intentionally separate future capabilities because
their resume flags and filesystem semantics differ between CLIs.
