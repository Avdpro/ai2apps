# AI2Apps managed browser baseline

> Legacy note (2026-08-29): this document describes the original managed-Chrome
> baseline. New AceFox, Sidebar, Knowledge import, and Web Agent work must follow
> `ai2apps-browser-control-architecture.md`, where native WebDriver BiDi through
> the authenticated protocol-transparent Gateway is the only browser-control
> protocol. Do not extend the semantic `browser.*` API catalog below for new
> AceFox functionality.

AI2Apps provides a visible, user-authorized Chrome runtime for Agent-assisted
web tasks. The first implementation creates a standard WebDriver session with
`webSocketUrl` enabled and subscribes to navigation lifecycle events over
WebDriver BiDi. Chrome runs with a dedicated persistent profile under the
AI2Apps platform data root.

## Safety boundary

- AI2Apps disables Chrome password-manager storage in the managed profile.
- `browser.type` refuses password and one-time-code fields.
- Passwords, CAPTCHA challenges, 2FA, and equivalent authentication controls
  always transition the browser to `user_required`.
- Once user control begins, Agent page reads, screenshots, and interactions are
  blocked. Navigation event details are cleared from the exposed status.
- The user types credentials directly into visible Chrome. Credentials never
  become Tool arguments, model context, or AI2Apps audit data.
- The user explicitly returns control through the platform API after completing
  authentication. AI2Apps checks that sensitive controls are no longer present
  before resuming Agent operation.
- Publish, send, purchase, delete, and similar controls require `commit=true`
  and the separate `browser.commit` capability.

The browser is owned by one AI2Apps Session until it is closed. This matches the
current single-user, serialized Agent execution model and prevents one Session
from observing another Session's browser state.

## Agent Tools

| Tool | Capability | Purpose |
| --- | --- | --- |
| `browser.status` | none | Read control state without page content |
| `browser.open` | `browser.read` | Start visible Chrome, optionally navigate |
| `browser.navigate` | `browser.read` | Navigate to an HTTP(S) URL |
| `browser.snapshot` | `browser.read` | Read bounded page text and element refs |
| `browser.click` | `browser.interact` | Click an element; consequential clicks also require `browser.commit` |
| `browser.type` | `browser.interact` | Type non-secret text |
| `browser.scroll` | `browser.interact` | Scroll the page |
| `browser.screenshot` | `browser.read` | Capture a page only outside authentication handoff |

`browser.snapshot` defaults to `html_mode="visible"` and returns rendered text
plus a visibility-pruned HTML representation. CSS-hidden,
transparent, `hidden`, `aria-hidden`, `inert`, script, style, and template
content is excluded. Text belonging to links, buttons, and form controls is
represented once in the structured element list instead of being duplicated in
the page-text field. Besides reducing model context, this prevents invisible
page content from silently becoming Agent instructions.

Every retained element includes `data-ai2apps-rect="x,y,width,height"` and
interactive elements also carry a stable `data-ai2apps-ref`. Set
`html_mode="full"` to request the complete document HTML. Full mode requires
the separate `browser.read_full_html` capability, has a 2,000,000-character
safety ceiling, and still removes password and one-time-code values.

## User handoff API

```text
GET  /v1/platform/browser/status
POST /v1/platform/browser/user-control/begin
POST /v1/platform/browser/user-control/complete
POST /v1/platform/browser/close
```

These endpoints are user-facing control-plane operations and are deliberately
not Agent Tools.

## Installation and smoke test

Wheel users install the optional browser runtime with:

```bash
pip install 'ai2apps[browser]'
```

The macOS bundle includes the same dependency. A real visible-Chrome smoke test
that uses only local pages is available as:

```bash
.venv/bin/python scripts/smoke_browser_chrome.py
```

The smoke test verifies a real BiDi connection, page snapshotting, and the
password-field transition to `user_required`; it performs no model inference.
