# AI2Apps oMLX Runtime 1.5.6 release receipt

Date: 2026-08-29 (Asia/Shanghai)

## Release identity

- Package: `ai2apps/runtime-omlx`
- Version: `1.5.6`
- Package type: `service`
- Source commit: `66736ccaed462e6f366b03d15c10aec5b43213ff`
- Build source: the current working tree, including the Runtime 1.5.6 metadata and the accepted Ornith/Qwen3.6 VLM Runtime changes
- Platform: `darwin-arm64`
- Minimum macOS version: `26.2`
- AI2Apps compatibility: `>=0.1.0 <2.0.0`

## Apple-signed Runtime DMG

- Final DMG: `packages/ai2apps-runtime-omlx/dist/AI2AppsOmlxRuntime-1.5.6.dmg`
- SHA-256: `f932c5dda80a86d459cbc77d5dfd716d8f7ab372daadd908baccea031cbff5ae`
- Size: `457606653` bytes
- Developer ID team: `84XL5V265N`
- Notary submission: `2ed2da3f-433d-48a7-ba25-492ab8ff6e26`
- Notary result: `Accepted`
- Staple validation: passed
- Gatekeeper result: `accepted`, source `Notarized Developer ID`

The mounted DMG was checked before Package construction. Its bundle version is
1.5.6, its packaged oMLX source contains the visual-boundary scheduler fix and
VLM scope-block binding, and its bundled CPython imports `omlx 0.5.8.dev1`.

## Signed AI2Apps Package

- Artifact: `packages/ai2apps-runtime-omlx/dist/ai2apps-runtime-omlx-1.5.6-production.ai2service`
- Envelope: `packages/ai2apps-runtime-omlx/dist/ai2apps-runtime-omlx-1.5.6-production.ai2service.envelope.json`
- SHA-256: `a757d5a6ea59f37150861ead9c7d8768645a280946703d52a1aedf8f01f38c25`
- Size: `455147040` bytes
- Media type: `application/vnd.ai2apps.service+zip`
- Publisher ID: `229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Publisher public-key fingerprint: `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`

The Publisher key was loaded only from the single, explicitly identified
Keychain record. Signing proceeded only after the derived public-key
fingerprint matched the registered Cloud fingerprint above. No private-key or
Cookie material was printed, copied, or stored in this receipt.

Package inspection found eight archive members and no checkpoint,
`.safetensors`, `.gguf`, `.ckpt`, or expert-store payload.

## Verification

- Focused release suite: `586 passed`
- `git diff --check`: passed
- Package Contract inspection: passed; Package ID/version/digest/size match
- Real signed-Package installation: passed
- Installed Runtime resolution: `ai2apps.runtime.omlx` 1.5.6 with digest
  `sha256:a757d5a6ea59f37150861ead9c7d8768645a280946703d52a1aedf8f01f38c25`
- Model dependency lock: resolved exactly to Runtime 1.5.6
- Worker smoke: `ai2apps.model.qwen36-35b` 0.3.1 reached `running`

The first smoke invocation exposed an unrelated current-worktree mismatch:
there are 59 database migrations while `PLATFORM_DATABASE_SCHEMA_VERSION` is
still 58. No user-owned database files or source changes were overwritten. The
release smoke was rerun with a process-local expected-version override only;
the installed Runtime and Model Package bytes were unchanged.

## Cloud publication

- Submission ID: `11400f87-05a7-4a0c-9020-d00b0bea05e6`
- Review ID: `4b57c846-4dc4-4c31-9af7-335ef08bc97e`
- Review decision: `approved`
- Release status: `published`
- Published at: `2026-08-28T21:26:15.639Z`
- Repository metadata version: `91`

Publication used `scripts/publish_signed_registry_artifact.py` and the exact
authorized current AI2Apps dev browser profile. That one-release Cookie grant
expired when publication completed.

## Anonymous public read-back

The public Registry was read with an empty in-memory session store and its
repository signature was checked against the pinned repository key.

- Trusted metadata version: `91`
- Public release status: `published`
- Public artifact SHA-256 and size: exact local match
- Public Publisher/key/fingerprint: exact expected match
- Discover catalog latest version: `1.5.6`
- Installability: `true`
- Blockers: none

The public artifact endpoint is:
`https://coder.ai2apps.com/v1/registry/packages/ai2apps/runtime-omlx/versions/1.5.6/artifact`.
