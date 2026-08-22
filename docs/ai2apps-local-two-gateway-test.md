# Local two-gateway acceptance setup

The normal Local at `127.0.0.1:8000` is the upstream gateway. A second,
fully isolated Local runs at `127.0.0.1:8100` as the downstream client.

The downstream instance uses `/tmp/ai2apps-downstream` by default. Its
database, Chat sessions, account binding, secure credential vault, settings,
logs and artifacts do not overlap the normal Local. It deliberately starts
with an empty model directory: upstream model discovery and invocation must
not accidentally fall back to a local model.

Start it from the repository root:

```bash
scripts/run-local-downstream.sh
```

Automated mutual Bonjour discovery check (with both instances already
running):

```bash
python scripts/acceptance_gateway_discovery.py
```

The script temporarily enables ports `8011` and `8111`, verifies both
directions, and restores each instance's prior visibility setting.

Optional isolation overrides:

```bash
AI2APPS_DOWNSTREAM_BASE_PATH=/tmp/ai2apps-downstream-2 \
AI2APPS_DOWNSTREAM_PORT=8200 \
AI2APPS_DOWNSTREAM_API_KEY=replace-for-manual-testing \
scripts/run-local-downstream.sh
```

Expected ports:

- upstream main Local: `8000`
- upstream LAN sharing Listener: `8011`
- downstream main Local: `8100`
- downstream LAN Listener, if later enabled manually: `8111`

Acceptance flow:

1. On the upstream Sharing App, publish `system.echo` and one local model.
2. Enable `Shared capabilities only` on port `8011`.
3. Create one client credential and copy its connection JSON.
4. Open the downstream Sharing App on port `8100`.
5. Select **Scan LAN** and confirm the upstream is shown as a nearby gateway.
6. Scan the connection QR (or upload its image/paste JSON), then add it under
   **Upstream gateways**. Discovery alone must not create access.
7. Confirm the projection contains exactly the shared model and Tool.
8. Invoke the projected Tool and model from the downstream and confirm the
   metadata-only activity rows update.
9. Stop the upstream listener and verify the failed call marks the gateway
   offline and removes/degrades its projections until a successful test.
10. Revoke the upstream credential and verify both downstream calls fail.
