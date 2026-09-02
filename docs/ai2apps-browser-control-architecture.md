# AI2Apps Browser Control Architecture

## Decision

WebDriver BiDi is the single browser-control protocol for AI2Apps. Main App,
trusted Mini-Entries, Knowledge, Chat, and WebAgent use the same protocol for
page inspection and browser automation.

AI2Apps must not create a second semantic browser API that mirrors BiDi. The
AI2Apps BiDi Gateway is a protocol-transparent security and lifecycle boundary:
it forwards BiDi commands, responses, and events without renaming methods or
changing their payload shapes.

## Topology

```text
AceFox WebDriver BiDi
        |
        | authenticated loopback WebSocket
        v
AI2Apps BiDi Gateway
        |-- Main App host bridge
        |-- trusted Sidebar Mini-Entries
        |-- Chat and Knowledge
        `-- WebAgent runtimes
```

AceFox starts BiDi by default for the authenticated AI2Apps user Profile. The
raw listener remains loopback-only and requires the per-launch 256-bit bearer
credential. The credential and raw endpoint are never exposed to Local HTML.
The Helper owns them and issues revocable, actor-bound Gateway sessions.

## Gateway contract

The Gateway exposes the complete BiDi command and event surface. It may:

- authenticate the AI2Apps instance, actor, App, and Mini-Entry mount;
- enforce declared browser capabilities;
- bind a caller to an AceFox Profile, window, or browsing context;
- multiplex request IDs and events;
- apply message-size, rate, and lifetime limits;
- audit method names and outcomes without logging page data or credentials;
- reconnect or revoke sessions when AceFox restarts.

It must not replace methods such as `script.evaluate`,
`browsingContext.captureScreenshot`, or `input.performActions` with an
AI2Apps-specific copy. Convenience behavior belongs in a shared client SDK
built on the raw protocol.

## Capability model

- `browser.read`: context tree, URL/title, DOM evaluation, selection, and
  screenshots.
- `browser.interact`: navigation, input actions, dialogs, and scrolling.
- `browser.automation`: tabs, windows, downloads, network events, and
  interception.
- `browser.webdriver-bidi`: the complete protocol for trusted system Apps and
  WebAgent runtimes.

The Main App host may request the full capability. A Mini-Entry receives a
mount-bound session through the host bridge and never receives the underlying
bearer credential.

## Current-page binding

AceFox publishes the active top-level BiDi browsing-context ID whenever the
selected tab changes. A Sidebar mount is bound to that ID and window. Commands
that omit a target may use the binding; commands with an explicit target must
remain inside the granted Profile scope.

Firefox may rotate its generated top-level navigable UUID after a BiDi session
disconnects. The shared client therefore keeps its session alive for the
Mini-Entry lifetime. When reconnecting, it accepts a replacement ID only if a
fresh `browsingContext.getTree` has exactly one top-level context with the
Sidebar-bound URL; an ambiguous match fails closed and asks for a context
refresh.

This small privileged binding is the only browser-window responsibility that
may remain in Firefox UI code. It must not extract DOM, run Readability,
capture screenshots, or implement interaction commands.

## Shared client SDK

AI2Apps provides optional helpers on top of the full BiDi connection:

- wait for render and page stability;
- run Readability, then fall back to cleaned rendered HTML;
- remove hidden consent, advertisement, navigation, and dialog nodes;
- read the current selection;
- capture the visible viewport for a multimodal model;
- detect and handle cookie declarations under PageAccess policy;
- serialize common input actions.

These helpers are clients of BiDi, not a replacement protocol. Callers may use
any native BiDi method directly.

## Product flows

### Chat Sidebar

Before every request, Chat evaluates the current rendered page through BiDi.
If the chosen model declares image input and the user enables it, Chat also
captures the visible viewport through `browsingContext.captureScreenshot`.
The page and screenshot are treated as untrusted model input.

Local and AI2Apps-managed Cloud image-capable models receive the screenshot as
an OpenAI-compatible PNG Data URL. Cloud support was deployed with OpenAPI
1.26.0 and passed the first client production acceptance request on 2026-08-28.
The contract and limits are recorded in
`docs/ai2apps-cloud-browser-screenshot-input-requirements.md`. Local must not
publish a private screenshot to an arbitrary public URL.

### Knowledge webpage import

Static HTTP plus Readability remains an optimization when explicitly selected
or when Auto determines it is sufficient. AceFox mode, dynamic fallback, and
user-assisted login all use the same Profile-bound BiDi session. Import tabs
are closed after extraction unless the user is actively controlling them.

### WebAgent

WebAgent receives the full protocol according to its capability grant. Complex
automation must compose native BiDi commands and events rather than request
new server-side wrapper endpoints.

### Agent Sidebar and Builder

The Browser Sidebar exposes Agent beside Chat and Knowledge. Its trusted
Mini-Entry can run page-scoped Agents and author natural-language Agent Source.
Direct step testing still compiles an ephemeral structured plan, passes it
through deterministic policy, and executes approved actions through native
BiDi. The product behavior and staged implementation are defined in
`docs/ai2apps-browser-agent-sidebar-builder-plan.md`.

## Prohibited designs

- A JSWindowActor request/response protocol for DOM extraction, screenshots,
  or browser interaction.
- A REST or WebSocket API that redefines the BiDi method catalog.
- Exposing the raw AceFox debugging port or bearer credential to Local HTML.
- Selecting a browser window by focus, title, enumeration order, or inferred
  embedding structure instead of an explicit BiDi browsing-context binding.
- Launching a second temporary Profile when the operation is intended to use
  the authenticated user's AceFox Profile.

## Migration

1. Publish authenticated full-protocol Gateway sessions to the Main App host.
2. Bind Sidebar mounts to the selected BiDi browsing context.
3. Move Chat current-page extraction and screenshots to the shared BiDi SDK.
4. Move Knowledge user-assisted completion from Managed Browser extraction to
   the same BiDi session.
5. Delete the legacy Actor extraction messages after all consumers migrate.
