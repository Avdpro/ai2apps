# AI2Apps desktop update distribution contract

This document is the deployment-side contract for the update client in this
repository. It does not require a new Cloud API: an object store plus HTTPS CDN
is sufficient. Cloud/CDN configuration is intentionally outside this repository.
The production handoff checklist is
`../../../docs/ai2apps-desktop-update-cloud-production-requirements.md`.

## Client behavior

- A release build defaults `AI2AppsUpdateManifestURL` to
  `https://coder.ai2apps.com/updates/stable.json`. Packaging may override it
  with `UPDATE_MANIFEST_URL`; the URL must use HTTPS.
- Helper checks 30 seconds after startup, every 24 hours, and when the user
  selects **检查更新**.
- The manifest is limited to 1 MiB and 32 releases. Only a newer Build Number
  matching bundle ID, instance ID, Runtime profile, architecture and minimum
  macOS version is eligible.
- Each installation keeps one random UUID in the private config directory.
  `SHA256(rollout.id + ":" + cohortID) mod 10000` gives a stable cohort bucket.
  A release is visible when the bucket is below `percentage_basis_points`.
- Each artifact has an ordered `urls` mirror list. Downloads use
  `<filename>.part`, request `Range: bytes=N-`, and require a matching
  `Content-Range` on `206`. A failed ModelScope request falls through to GitHub
  using the same partial file. A mirror that ignores Range and returns `200`
  safely restarts at zero. Exact byte size and SHA-256 are checked before the
  final filename is published.
- The existing DMG/release-record verifier remains authoritative. The online
  manifest does not weaken Developer ID, Hardened Runtime, notarization,
  instance, version, Runtime-manifest or health-check gates.

## Manifest schema v1

```json
{
  "schema_version": 1,
  "channel": "stable",
  "releases": [
    {
      "bundle_identifier": "com.ai2apps.desktop",
      "instance_id": "default",
      "product_version": "1.4.0",
      "bundle_version": "2301",
      "runtime_profile": "full",
      "minimum_system_version": "13.0",
      "architectures": ["arm64"],
      "rollout": {
        "id": "stable-2301-r1",
        "percentage_basis_points": 500
      },
      "dmg": {
        "url": "https://modelscope.cn/models/ai2apps/desktop-releases/resolve/v2301/AI2Apps-2301.dmg",
        "urls": [
          "https://modelscope.cn/models/ai2apps/desktop-releases/resolve/v2301/AI2Apps-2301.dmg",
          "https://github.com/ai2apps/desktop/releases/download/v2301/AI2Apps-2301.dmg"
        ],
        "filename": "AI2Apps-2301.dmg",
        "size": 237123456,
        "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
      },
      "metadata": {
        "url": "https://modelscope.cn/models/ai2apps/desktop-releases/resolve/v2301/AI2Apps-2301.release.json",
        "urls": [
          "https://modelscope.cn/models/ai2apps/desktop-releases/resolve/v2301/AI2Apps-2301.release.json",
          "https://github.com/ai2apps/desktop/releases/download/v2301/AI2Apps-2301.release.json"
        ],
        "filename": "AI2Apps-2301.release.json",
        "size": 4096,
        "sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
      }
    }
  ]
}
```

`percentage_basis_points` ranges from `0` (paused) through `10000` (all
eligible installations). Increase it without changing `rollout.id` to expand
the same cohort monotonically. Change the ID only when intentionally assigning
a fresh cohort, for example after replacing a bad candidate with a new build.

## CDN requirements

- Serve the manifest, release record and DMG only over TLS.
- Publish the manifest at
  `https://coder.ai2apps.com/updates/stable.json`; do not redirect it to either
  artifact host.
- Artifact URLs are immutable and content-addressed by release/build path.
- DMGs and release records support byte ranges and return
  `Accept-Ranges: bytes`, `206 Partial Content`, and an exact `Content-Range`.
- Do not transparently compress artifacts; honor `Accept-Encoding: identity`.
- Immutable artifacts may use long-lived cache headers. Give the manifest a
  short TTL appropriate to rollout control.
- Publish artifacts first and verify their public size/digest. Publish the
  manifest last with an atomic object replacement. Never point a manifest at an
  object that is still uploading.

### `coder.ai2apps.com` deployment requirement

The Cloud deployment owns only the small control document, not the DMG bytes:

- `GET /updates/stable.json` returns the generated manifest without login,
  cookies, redirects, or signed query parameters.
- Return `Content-Type: application/json`, a body no larger than 1 MiB, and a
  short cache lifetime (recommended `Cache-Control: public, max-age=60`).
- Replace the object atomically so clients see either the previous complete
  manifest or the next complete manifest.
- Keep ModelScope first and GitHub second in each `urls` array. Both URLs must
  identify immutable release revisions containing byte-identical artifacts.
- Publishing or pausing a rollout changes only this document. The Cloud service
  must not proxy the DMG or rewrite artifact URLs.

Generate a schema-valid single-release manifest from the final stapled release
record and its sibling DMG:

```bash
scripts/generate-update-manifest.py \
  --release-metadata /release/AI2Apps-2301.release.json \
  --base-url https://modelscope.cn/models/ai2apps/desktop-releases/resolve/v2301 \
  --base-url https://github.com/ai2apps/desktop/releases/download/v2301 \
  --runtime-profile full \
  --rollout-id stable-2301-r1 \
  --percentage-basis-points 500 \
  --output /release/stable.json
```

## Rollout and rollback procedure

1. Upload the notarized DMG and its generated release record to a new immutable
   build path.
2. Verify both objects through the CDN, including a nonzero Range request.
3. Publish the manifest at `0` basis points, then raise to the desired canary
   percentage while keeping the rollout ID fixed.
4. Observe install success and rollback telemetry outside this client before
   increasing the percentage.
5. To stop distribution, set the percentage to `0` or remove the release. Apps
   already installed are not downgraded. Publish a higher Build Number to fix a
   released defect.

The installer retains one authenticated previous App. On the next successful
upgrade, that older backup is authenticated and rotated so the immediately
preceding build becomes the new rollback generation. An unrecognized or
tampered backup is preserved and the update fails rather than deleting it.
