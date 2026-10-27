# AaAT local attachment references and model setup

Implemented 2026-10-23. Desktop Chat has one attachment picker for images and
files. Large native selections register a Session-owned opaque attachment ID
backed by the original selected path. Registration does not read, hash or copy
source content. Private stat fingerprints detect removal, mutation and
replacement. Public records and conversation persistence exclude native paths.
Small vision images retain their existing bounded image-input behavior.

Reference-enabled owner material slots accept original Desktop paths or stream
uploads to Desktop storage once. Ordinary Chat can explicitly extract bounded
previews from supported small documents; large/media attachments remain
references for compatible Apps. Detailed transcription decodes the original
Path through PyAV, and video media jobs retain source references rather than
staging copies. Both check source fingerprints around processing. Legacy
Package workflows must explicitly opt in before receiving references.

Missing-model forms preserve drafts/materials. Desktop opens the declared
owning App and its existing ACPF flow, then returns to the original conversation
for recheck. Mobile shows Desktop configuration instructions. This neither
accepts licences nor submits business jobs nor switches models automatically.
Full ACPF embedding into Chat remains deferred.

## Regression evidence

- Python attachment/setup/owner/forms/documents/Studio suite: 46 passed.
- JavaScript unified picker/forms/send-mode suite: 28 passed.
- Mandatory AaAT boundary gate: 255 passed (105.10 seconds).
- Sparse 3 GiB fixture: no content read/hash/copy at registration, source mutation
  and cross-Session denial covered. Stream upload and Path audio decode covered.
- Setup tests use two arbitrary provider identities, assert trusted owner,
  version guards, unchanged pending draft and zero submitted Studio jobs.

## App-Dev activation and live evidence

Fixed App-Dev, instance app-dev, source checkout
`/Users/avdpropang/sdk/omlx-moe-cache`; standard Helper Local restart only.
App/Helper source-root metadata verified; live import logs show current
`ai2apps/services/builtin_apps.py`. Native title after restart:
`AI2Apps-App-Dev: App-Dev 127.0.0.1:57896`, Local PID 59214.
Served parameter forms, provisioning and Shell JavaScript match checkout bytes.

Actual Desktop picker selected `aaat-large-reference-fixture.mp4` (3 GiB sparse
fixture). Chat displayed 本地引用 and its moved/modified-file hint; send registered
3221225472 bytes with storage=reference/content_status=not_loaded. Conversation
returned attachment ID without reading content. Fixture remained zero allocated
blocks. No media decode/generation was attempted for this invalid test fixture.

Legacy Mobile Chat's separate upload limits/transport are unchanged; the new
streaming path applies to Session upload APIs and opted-in parameter material
slots. No real iPhone installation test or production release is claimed.

Live model-configuration round trip also verified: Agent opened Quick Read's
parameter form with text 测试配置入口; Configure model in App opened Voice Studio
and the existing ACPF profile chooser. Cancelled before download/installation,
returned to the originating conversation, and verified the same text and
configuration/recheck controls. No speech job submitted. Fixed a stale mount
registry issue observed on first return; release the previous form mount before
restoring the Session. Added regression; final UI suite is 29 passed.
