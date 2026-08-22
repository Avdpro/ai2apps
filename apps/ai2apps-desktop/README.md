# AI2Apps Desktop

This directory contains the D1 Electron client described in
[`docs/ai2apps-electron-desktop-development-plan.md`](../../docs/ai2apps-electron-desktop-development-plan.md).

This application is deliberately a client-only shell. It does not install Python,
start a Local Runtime, or replace the existing AI2Apps backend. It verifies an
already-running AI2Apps node and loads that node's Web Shell in a sandboxed
`BrowserWindow`.

## Requirements

- Node.js 22.12+
- An AI2Apps server, normally at `http://127.0.0.1:8000`

## Run

```bash
cd apps/ai2apps-desktop
npm install
npm test
npm start
```

Run a self-contained Electron launch smoke without starting the Python model
runtime:

```bash
npm run smoke
```

The smoke fixture implements only the existing public `/health`, authenticated
platform-health shape, and a minimal Shell page. It verifies that the real
Electron binary reaches a compatible node and loads its origin; it is not a
replacement for the AI2Apps Web feature smoke matrix.

Use another node during development with either:

```bash
npm start -- --node-url=http://127.0.0.1:9000
```

or:

```bash
AI2APPS_DESKTOP_NODE_URL=https://node.example.test npm start
```

Plain HTTP is accepted only for loopback hosts. Remote nodes must use HTTPS.
The environment override is a development input and is not persisted. In the
application, use **Node > Manage Nodes** to add or switch nodes. Remote nodes
must use HTTPS; authentication continues in the selected node's normal login
page. The connection store contains node names and URLs only—never passwords or
session tokens.

## Package for macOS

```bash
npm run package:mac
```

This produces a `.app` and `.dmg` in `out/`. The script automatically uses the
first available `Developer ID Application` identity, or the identity named by
`AI2APPS_CODESIGN_IDENTITY`. If none is available, it falls back to an ad-hoc
development signature. Public distribution also requires Apple notarization.

To smoke-test the packaged binary against the isolated fixture:

```bash
AI2APPS_DESKTOP_EXECUTABLE="$PWD/out/AI2Apps-darwin-arm64/AI2Apps.app/Contents/MacOS/AI2Apps" npm run smoke
```

On macOS, client metadata and logs are kept under
`~/Library/Application Support/AI2Apps/`. They are independent of the Local
server's data directory.

## Security boundary

- Renderer Node.js integration is disabled.
- Context isolation and Chromium sandboxing are enabled.
- The preload exposes a narrow API for bootstrap state, node selection, and
  user-mediated native file dialogs.
- Navigation is restricted to the configured node origin.
- External HTTP(S) and `mailto:` links open in the system browser.
- All web permissions are denied.
- Downloads are accepted only from the configured node origin.
- TLS/certificate errors are never bypassed.

The current authenticated server protects `/v1/platform/health`. When that
endpoint returns `401`, the client first requires the public `/health`
endpoint to be ready and then loads the normal AI2Apps login flow. A dedicated
public, non-sensitive Desktop bootstrap descriptor remains a future backend
enhancement. Cryptographic device pairing is intentionally deferred to D4.
