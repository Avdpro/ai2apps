# Studio Mini-App Package Contract v1

Studio Mini-App discovery is an optional extension of the existing App Package contract. It does not
introduce a new Cloud Package type or replace `ai2apps.package-manifest.v1`.

## Mini-App workspace header

Every Studio-hosted Mini-App uses one workspace title: its display name. Do not add a second
`CREATE`, `CURRENT MINI-APP`, or synonymous action heading at the top of the UI Entry. Begin the
content with the actual inputs, project selector, or task controls. Keep guidance next to the relevant
control, and show empty-state instructions only when empty.

The host title bar has a 56px minimum height, 20px horizontal content padding, a 16px semibold title,
white background, and a subtle bottom border. It scrolls with the middle column. Its information
disclosure contains provider/source, version, and description; these are not permanently expanded.
Expose a localized accessible name and keyboard-operable disclosure; reset it when switching Mini-Apps.

Do not show permanent `Model ready` or `Dependencies ready` header badges. Readiness is already
represented in the Mini-App list. Keep actionable setup near model/dependency controls; the host
details also retain setup access for an unready Mini-App. Do not remove configuration or Run actions
while simplifying headings. Package UI must follow the same rule and not repeat the host identity.
See [Studio design standard](ai2apps-studio-app-ui-design-standard-v1.md) for shared column behavior.

## Required accessible names and UI test contract

**Accessible control names are a mandatory development acceptance requirement for every Mini-App.**
Follow the [App control naming and automation test contract](ai2apps-app-development-guide.md#控件命名与自动化测试规范必选)
and [Studio accessibility standard](ai2apps-studio-app-ui-design-standard-v1.md#16-可访问性与交互一致性).
This applies to schema/safe-html/sandbox Entries, shared UI renderers, and dynamically created controls.

Use native control semantics and visible button text or associated labels wherever possible. Icon-only
or symbol-only buttons and inputs without visible labels MUST expose a meaningful, localized
`aria-label` or valid `aria-labelledby`. Placeholder, tooltip title, internal IDs, and `data-testid`
are not substitutes. Do not override an existing visible name with an unrelated ARIA name.

Before declaring a Mini-App ready, verify rendered accessible names and state in its real Studio mount,
including dynamic rows, errors, running/stopped states, remounting, and keyboard interaction. Give the
iframe a descriptive title and verify controls inside it separately. Tests should locate the correct
browsing context and scope, then use role plus accessible name or an associated label; pin the locale.
Stable test IDs may supplement this contract but never replace accessibility assertions. Use the existing
authorized WebDriver BiDi Gateway; do not add a parallel browser-control protocol.

## Package shape

The Registry artifact remains an ordinary Package whose top-level type is `app`. Its signed and indexed
`app.yaml` may contain a `mini_apps` list:

```yaml
schema: ai2apps.app/v1
id: ai2apps.audio-studio-suite
name: Audio Studio Suite
version: 1.0.0
publisher:
  id: ai2apps
instances:
  mode: singleton
  scope: user
entry:
  kind: sandbox
  resource: web/home.html
navigation:
  launcher: false

mini_apps:
  - schema: ai2apps.mini-app/v1
    id: ai2apps.audio.transcription
    name: Detailed Transcription
    version: 1.0.0
    kind: project
    icon: captions
    entry:
      kind: sandbox
      resource: web/transcription.html
      placements: [inline, sidebar]
    placements:
      - studio: ai2apps.readaloud
        category: transcription
        order: 60
      - studio: ai2apps.video-studio
        category: audio
        order: 60
    requirements:
      capabilities: [audio.speech_recognition]
```

Every Package Mini-App Entry must use `schema`, `safe-html`, or `sandbox`; installed Packages cannot
declare a privileged `host-adapter`. The Entry resource must be present in the signed file index. A
Mini-App must declare at least one Studio placement, and its mount placement is limited to `inline` or
`sidebar`.

Multiple Mini-Apps can share one App Package, Package version, resource tree, and App instance. The
Mini-App ID remains its canonical component identity; installation, activation, disable, rollback, and
access control continue to use the containing App Package.

### App Launcher visibility

A Package that exists only to provide Studio Mini-Apps should declare `navigation.launcher: false`.
It remains an ordinary signed App Package internally because its Mini-Apps share one provider App instance,
resources, permissions, and lifecycle, but it is omitted from App Launcher, Dock, App suggestions, and the
Mobile App list. Its Mini-Apps remain discoverable and mountable exclusively through their declared Studio
placements.

A mixed Package that also provides a coherent, independently usable top-level App should omit the field or
set `navigation.launcher: true`. The top-level `entry` is still required by the current App Package contract
even for a launcher-hidden Mini-App provider; it is an internal provider fallback and must not be treated as
a user-facing suite landing page.

## Standard local development workflow for non-built-in Mini-Apps

Every new non-built-in Studio Mini-App MUST be developed as an App Package source tree before it is
built or installed. Installing a newly built `.ai2app` after every UI or manifest edit is a release
acceptance step, not the normal authoring loop.

The minimum source layout is:

```text
packages/<package>/
├── ai2apps.json
├── app.yaml
├── web/
│   ├── home.html
│   ├── <mini-app>.html
│   ├── shared.css
│   └── shared.js
├── help/                 # when Mini-App Chat is declared
└── tests/
```

`ai2apps.json.package.type` MUST remain `app`. Its first App entrypoint MUST match
`app.yaml.entry.resource`. All Mini-Apps are declared once in `app.yaml.mini_apps`; authors MUST NOT
maintain a separate development-only Mini-App registry. It is valid for the source `ai2apps.json.files`
array to be empty because the development loader constructs an ephemeral index from the source tree.
The signed builder remains responsible for generating the immutable release index.

### Development source mount

The fixed `AI2Apps-App-Dev` environment and a current `AI2Apps-dev.app` discover direct child
directories below the trusted repository `packages/` root. A candidate is mounted only when it contains
both `ai2apps.json` and `app.yaml` and passes the normal App and Mini-App manifest validators.

The source-mounted App participates in the normal runtime path:

```text
app.yaml.mini_apps
  -> enabled development App definition
  -> unified Studio Mini-App registry
  -> provider AppInstance
  -> app_mounts record
  -> constrained/sandbox Entry
  -> Host Capability Broker
```

This is not a second Mini-App implementation and is not a loose HTML preview. Studio placement,
AppInstance ownership, mount provenance, capability allowlists, actor access and Host Broker checks
use the same path as an installed Package. The catalog reports the provider distribution as
`development` so source identity is never mistaken for a signed installation. The explicit Development
Runtime is the sole CSP exception: a source-mounted sandbox receives `allow-same-origin` and may connect
only to its current Local origin so authenticated CSS/JavaScript resources and the mount-scoped Host
Capability Broker can support hot development. An installed or release Package never receives this
exception and retains the opaque-origin, `connect-src 'none'` production policy.

Development source mount deliberately does not:

- build, sign, copy or install a Package artifact;
- create an `interactive_packages` or Package Store installation record;
- grant a capability, install a Runtime/model/checkpoint, or bypass ACPF;
- make the source identity trusted or publishable;
- enable source loading in a production Bundle.

The relaxed source policy is an authoring facility, not release evidence. Before publication, the same
Package MUST pass installed-artifact acceptance under the strict sandbox contract; workflows that need
Host capabilities MUST use the production Mini-App bridge/broker contract rather than depend on the
Development-only same-origin exception.

If the isolated development instance already has the same App Package installed, the source definition
overrides it only inside that development instance. Removing the source restores an available non-source
definition. Production and another AI2Apps instance are unaffected.

### Feedback loop

Use the smallest loop that matches the change:

| Change | Required action |
| --- | --- |
| Package HTML, CSS, JavaScript, image, or help content | Refresh or reopen the Mini-App |
| `app.yaml` name, placement, Entry, Chat, or requirement declaration | Refresh the Studio/App catalog; remount an already open Mini-App when its Entry changed |
| Host API, validator, Registry, mount, Broker, or other `ai2apps/` Python | Restart the exact Development Local process |
| `omlx/`, Swift/AceFox, embedded Runtime, dependencies, or Bundle contract | Rebuild the appropriate fixed Development App |

Resource responses are `no-store` and are read from the source file on each request. Manifest changes are
revalidated when the App or Studio catalog is read. Invalid manifests, missing declared resources,
symbolic links, path traversal, source files outside the Package root and Package size/file-count limit
violations fail closed.

Ordinary App-Shell and Package work SHOULD use the permanent
`apps/ai2apps-acefox/.build/AI2Apps-app-dev.app`. Lower-level integration work MAY use
`apps/ai2apps-acefox/.build/AI2Apps-dev.app`; that App must have been built by `build-dev-app.sh` after
source-mount support was introduced. Full environment behavior is defined in
[AI2Apps App-Shell App development environment](ai2apps-app-dev-environment.md).

### Required development and release gates

A non-built-in Mini-App is not ready for release until all of these phases pass:

1. **Source contract:** validate `ai2apps.json`, `app.yaml`, every Mini-App Entry/help resource,
   canonical ID uniqueness, placement, input/output and declared capability requirements.
2. **Source-mounted Studio smoke:** discover it in every declared Studio, create a real mount, load its
   constrained Entry, exercise its Host Broker operations, and verify a source edit after refresh.
3. **Isolation regression:** prove the source mount created no Package Store installation record and that
   the same source root is ignored when the Development Runtime marker is absent.
4. **Signed artifact:** build through the standard Package builder, verify the generated file index,
   signature/envelope, SBOM, Mini-App projection and deterministic rebuild behavior.
5. **Installed-package regression:** install the signed candidate into a clean compatible development
   instance and repeat discovery, mount, capability, upgrade/disable/rollback as applicable. Source-mount
   success MUST NOT replace this installed-state release test.
6. **Publication:** follow `docs/ai2apps-package-publication-runbook.md`; Cloud publication is never
   performed by the source-mount mechanism.

Tests for a new Package SHOULD include manifest validation, all Studio placements, sandbox resource
resolution, mount-bound capability authorization, refresh behavior, production fail-closed behavior and
at least one signed installed-package test. A multi-Mini-App Package is tested as one atomic Package and
also once per component workflow.

## Discover catalog projection

Mini-App is a first-class Discover surface, but it is not a new Cloud Package type. Discover presents
`All | Apps | Mini-Apps | Agents | Models | Services`; an App Package can therefore contribute one App
card and one component card for every declared Mini-App. Installing, upgrading, or removing any component
card still operates on the containing App Package.

The Package builder derives a bounded top-level `miniApps` projection in signed `ai2apps.json` from
`app.yaml.mini_apps`. Authors must not maintain a second hand-written index. Each projection contains the
canonical component ID, display name, component version, lifecycle kind, catalog categories, Studio
placements, and optional description/icon. If a hand-written projection is present, the builder rejects it
unless it exactly matches the App definition; installation performs the same cross-check.

A Mini-App can explicitly provide Discover categories without coupling them to Studio placement:

```yaml
mini_apps:
  - schema: ai2apps.mini-app/v1
    id: ai2apps.audio.transcription
    name: Detailed Transcription
    version: 1.0.0
    kind: project
    catalog:
      categories: [audio, document]
    placements:
      - studio: ai2apps.video-studio
        category: audio
        order: 60
```

Categories are lower-kebab identifiers and are intentionally extensible. The current standard labels are
`productivity`, `image`, `video`, `audio`, `document`, `automation`, `developer`, and `utility`. When an
older App definition has no explicit `catalog.categories`, the builder derives one conservative fallback
from its declared Studio placements. Already-installed Packages are projected from their verified local
App definition, so they do not need reinstalling merely to appear under Installed → Mini-Apps.

## Platform API

- `GET /v1/platform/studios/{studioId}/mini-apps` merges built-in Mini-Apps with declarations from enabled,
  accessible, installed App Packages and, in a Development Bundle only, validated source-mounted Apps.
- Existing `GET /v1/platform/video-studio/mini-apps`, `/readaloud/mini-apps`, and
  `/imagine-studio/mini-apps` remain available and are compatibility views of the same Registry.
- `POST /v1/platform/studios/{studioId}/mini-app-mounts` launches the provider App when needed and creates
  a normal `app_mounts` record. It requires `X-AI2Apps-App-Instance` for the matching Studio instance.
- `GET /v1/platform/studios/{studioId}/mini-app-mounts/{mountId}/capabilities` is the canonical readiness
  source for the mounted Mini-App. Every Studio host must render an unmet dependency state as a button,
  and that button must invoke the shared Studio Mini-App Client to start ACPF for the first declared
  (primary) capability. A successful mount never implies that model dependencies are ready.
- Studio startup must call the shared Package setup recovery path before its built-in capability recovery.
  The client durably retains only the Mini-App ID, semantic capability and opaque resume token, resumes
  `actionId: setup-mini-app` after a Local/Runtime restart, remounts the originating Mini-App, and probes
  readiness again before showing `Dependencies ready`.
- Recovery must also discover retryable failed Sessions from durable Host storage when browser-local
  recovery metadata is absent. A failed provider/checkpoint step must reopen the ACPF sheet with its error
  and Retry action; it must not silently fall back to the Studio landing state.

The Package declares semantic capabilities only. The trusted Host ACPF Profile Registry selects exact
Runtime, Service Package, Checkpoint, version and verification targets; Package HTML and `app.yaml` cannot
inject download URLs or installation plans. One trusted profile may be registered for multiple Studio App
IDs so the same Mini-App setup behavior is reused across hosts. A capability declaration may use
`{capability: ..., optional: true}` when an optional feature (for example subtitle translation) must not
block the main workflow readiness badge. Unknown, failed or unimplemented required capabilities remain
fail-closed as setup-required.

The mount response contains a `content_url`. Constrained views continue through `/admin/app-view`; sandbox
views continue through the digest-verified App resource route with its existing CSP. The mount context
records Studio, Mini-App, provider App, version, and effective digest provenance.

Package Mini-App content SHOULD send
`{type: "ai2apps:mini-app-resize", version: 1, height: <CSS pixels>}` whenever its rendered height changes.
The Studio Shell accepts the event only when `event.source` exactly matches the currently mounted Package
iframe `contentWindow`, the version is 1, and the height is finite and clamped to platform bounds. The Host
then expands the iframe so its current Mini-App header and content share the Studio page scroll. Older
Packages that do not implement this event retain a bounded compatibility height with iframe scrolling.

## Compatibility and conflicts

- An old App Package without `mini_apps` is validated, installed, launched, upgraded, and rolled back
  exactly as before.
- Development source discovery is additive and is disabled unless the Helper supplies both the
  Development Runtime marker and its Bundle-pinned absolute source root.
- The Cloud Registry continues to publish and deliver the existing signed App artifact; no Cloud schema or
  API change is required for this extension.
- Built-in Mini-App IDs are reserved. An installed declaration cannot replace one.
- If multiple installed Packages expose the same Mini-App ID to one Studio, the conflicting ID is omitted
  from discovery and cannot be mounted until the conflict is resolved.
- Disabled or inaccessible provider Apps disappear from discovery automatically.

This foundation standardizes discovery and trusted WebUI mounting. Shared Run/Step/Artifact, Asset-drop,
the general Capability Broker, and Coder authoring bridges remain separate contracts and must not be
inferred from the mount API. The Local media Broker extension below implements only the six explicitly
listed MVP operations; it does not make arbitrary declared capabilities executable.

## Local media MVP Broker extension

### Opaque-frame transport

Installed sandbox HTML is served with unchanged opaque-origin and `connect-src 'none'`
policy. The resource route inlines package-relative classic JavaScript and stylesheets
only after resolving each through the existing digest verifier. Deferred classic
scripts execute after the body; module imports are not supported by this delivery
path. Remote/root-relative/traversal assets and HTML closing-tag injection fail closed.
The combined document is limited to 4 MiB.

After the frame load, a Package sends `ai2apps:studio-connect` version 1 to its parent.
The Studio accepts only the exact iframe whose URL came from its authenticated mount
response and transfers a private MessageChannel. A navigation revokes that mount's
channel; reopening through the Studio creates a fresh mount. Requests expose only
`probe`, `invoke`, `setup`, `characters.list`, `voice-clone-models.list`, `draft.get`, `draft.set`, and `draft.remove`; no URL, mount ID,
credential or arbitrary storage key is accepted from the Package. The Host determines
the endpoint from its recorded mount. Every request first revalidates the actor and
mount through the Broker. Invocation additionally runs the existing server-side signed
capability allowlist and media validation. For capabilities with progress support, the
Host may send unsolicited `ai2apps:studio-progress` messages on the same private channel;
the Package cannot choose a progress URL or invocation identity. Uploads are bounded to
1 GiB for primary media and 100 MiB for reference media.

Drafts are limited to 4 MiB (including saved transcript results), schema/miniApp checked, and namespaced by the user-scoped
Studio instance, provider instance and entry resource. They are stored by the Host,
not opaque-frame localStorage. Binary input and output remain live Blob objects, not
durable drafts. This transport does not provide arbitrary fetch, direct Worker access,
unprompted model installation, or durable media jobs. `setup` may open the Host-owned ACPF only for
a capability declared by the exact mount; an explicit `installMore` request keeps the previous model
selection and opens the chooser even when another compatible model is already ready.

The first executable Package Mini-App path is mount-bound and Local-only:

- `GET /v1/platform/studios/{studioId}/mini-app-mounts/{mountId}/capabilities` probes the exact mounted
  declaration and currently installed providers.
- `POST /v1/platform/studios/{studioId}/mini-app-mounts/{mountId}/capabilities/audio.detailed_transcription/invoke`
  accepts bounded multipart media plus the `compact|quality`, language, timestamp, and diarization options.
- `POST /v1/platform/studios/{studioId}/mini-app-mounts/{mountId}/capabilities/audio.source_separation/invoke`
  accepts bounded multipart media plus a provider-declared separation profile. It returns the provider's ZIP
  artifact containing timeline-aligned WAV stems and `separation.json`.
- `POST .../capabilities/media.video_subtitles/invoke` composes Detailed Transcription, optional translation
  through the configured Standard model, SRT/WebVTT/ASS serialization, and optional PyAV subtitle burn-in.
  It returns one ZIP containing the subtitle, transcript JSON, and optional MP4.
- `POST .../invocations` creates a short-lived, actor- and mount-bound progress identity for an allowlisted
  capability. `GET .../invocations/{invocationId}/events` emits no-store SSE updates. The immediate Studio
  Host creates and subscribes to this stream, forwards only validated progress payloads over the private
  MessageChannel, and supplies the invocation ID to the capability request; the opaque Package frame never
  receives session credentials or direct network authority.
- `GET .../characters` returns only the current owner's safe Character identities, labels, bound model labels,
  and readiness flags. The Package never receives Character training material, reference paths, model
  endpoints, or another user's profiles.
- `GET .../voice-clone-models` returns only TTS providers whose signed audio contract supports one executable
  reference-audio cloning request. It exposes safe labels, readiness, transcript policy, and reference-duration
  limits; checkpoint paths and Worker endpoints remain Host-owned.
- `POST .../capabilities/media.video_audio_translation/invoke` handles the single-narrator Phase 1 workflow.
  It transcribes without diarization, restores punctuation, splits sentence-sized cues, translates through
  the configured Standard model, and synthesizes every translated cue with either one selected ready Voice
  Studio Character or a request-scoped clone of the original narrator. Original-voice mode selects a clear,
  speech-dense window near ten seconds from the source timeline, pairs it with the matching ASR text, and sends
  both only as the current TTS request's reference; it never creates or updates a Character. The workflow omits
  the source dialogue stem, mixes the generated narration over the Demucs background stem,
  and replaces the video's audio in a new MP4. Multiple speakers, lip sync, and per-speaker voice mapping are
  deliberately outside this operation.
- `POST .../capabilities/audio.speaker_voice_replacement/invoke` first supports an `analyze` action that
  returns diarized transcript JSON. Its `replace` action requires explicit rights confirmation, a selected
  anonymous speaker ID, and reference audio. It composes Detailed Transcription, Demucs
  `dialogue_background`, a reference-audio voice conversion provider, and timeline-aware mixing.
- `POST .../capabilities/media.video_speaker_voice_replacement/invoke` applies the same two-stage speaker
  workflow to a video's extracted audio and replaces the audio stream in a new MP4.

Before invocation the Host re-reads the active mount, actor access, Studio ID, canonical Mini-App ID,
provider App identity, effective Package digest, and signed `requirements.capabilities`. It rejects a stale
mount or undeclared capability. For transcription the Host chooses only the allowlisted Detailed
Transcription model IDs. For separation it considers only installed `audio_processing` providers whose
validated audio capability contract advertises `audio_process`, supported separation, and the exact requested
profile. The Host normalizes media to bounded PCM WAV, constructs the model scheduling identity from the
authenticated actor and mount, and invokes the model without exposing a Worker endpoint or checkpoint path.
Reference-based voice conversion considers only installed providers whose validated capability contract
advertises `reference_audio` and the exact requested profile. The current MVP therefore selects Seed-VC and
does not silently reinterpret a named RVC voice as a user-supplied reference.

These MVP operations are awaited Host requests, while CPU-heavy decoding, mixing, subtitle rendering, and
remuxing run off the server event loop. Video Studio persists final video outputs as host-owned Runs and
Artifacts; opaque Package frames never own output history. Video processing uses the bundled PyAV/FFmpeg
libraries and does not launch an external executable. Video Subtitles exposes coarse, real stage progress
for extraction, transcription, translation, layout, and export through the bounded SSE bridge. Cancellation,
provider-native fine-grained percentages, reconnectable durable Jobs, and progress coverage for the remaining
media workflows remain follow-up contracts.

## Optional Mini-App Chat capability

A Mini-App can opt in to conversational control with a signed `chat` declaration. Studio shows its Chat
tab only when the selected Mini-App exposes this capability. Built-in `host-adapter` Mini-Apps receive the
same capability from the platform registry and provide their live contract from the Studio process.
This capability is recommended but never required for Mini-App validation, installation, discovery, or
mounting. Authors are encouraged to implement at least the Help-only profile described below.

```yaml
chat:
  schema: ai2apps.mini-app-chat/v1
  enabled: true
  system_prompt: Help the user operate this Mini-App using only declared operations.
  context:
    transport: studio-bridge
  help:
    resource: docs/help.md
    max_bytes: 32768
  tools:
    - name: run
      description: Run with the current visible draft.
      confirmation: always
      input_schema:
        type: object
        properties: {}
        additionalProperties: false
```

The declared `help.resource` must be a safe Package-relative path ending in `help.md`, must be present in the
signed file index, and is limited to 32 KiB. Its contents are not included in the normal model Context. The
Chat model receives a reserved `read_mini_app_help` Tool and can request the current Mini-App's help when the
user asks about usage, inputs, settings, or troubleshooting. The provider handles the corresponding `help`
request and returns the declared Markdown; the Chat frame cannot choose a path.

The optional contract has two supported profiles:

- **Help-only:** use a concise System Prompt, return an empty or minimal Context, declare `tools: []`, and
  serve `help.md` through the provider bridge. Chat can explain the Mini-App but cannot operate it.
- **Chat-control:** add live state and one or more allowlisted operation Tools. This is the preferred profile
  for Mini-Apps whose actions can be represented safely.

Omitting `chat` entirely remains valid and hides the Chat entry. Within a declared v1 `chat` capability,
`help.md` is required so every visible Chat entry can at least answer how to use its current Mini-App; the
operation Tool list may contain zero to 64 entries.

The Package declaration is only the signed static allowlist. Current state is requested immediately before
each model turn, and Tool execution returns to the mounted Mini-App through the channel-bound Studio bridge.
The Chat frame cannot invoke an undeclared Tool. Studio revalidates the selected Mini-App and Tool on every
call, and `confirmation: always` is enforced by the Studio host rather than trusted to model output.

Context is model input, not authority. Mini-Apps must omit secrets, native paths, bearer credentials, hidden
DOM, and unrelated App state. Tool handlers must validate arguments again and use the normal Capability
Broker for operations that require capabilities outside the App's existing grant.

## Voice Studio output ownership (mandatory)

All built-in and Package Mini-Apps mounted in `ai2apps.readaloud` MUST use the host-owned
Preview & Output. Quick Read is the shared UI baseline, not a separate output implementation.
The host owns selection, playback, the common 20-result feed, format export, native Shell Save As,
and audio Artifact drag payloads. Switching Mini-App MUST NOT reset or filter this feed or selection.
Do not branch the output panel on `pipelineMode` or a Package Mini-App ID.

Producers persist final results in the owner's Voice Studio Artifact session with `studioId`
and `miniAppId` metadata. `/v1/platform/readaloud/outputs` is the sole visible history endpoint.
Package capability invocation is the publication boundary: the authenticated host saves the
result and emits `ai2apps:studio-output`; frames never implement their own history or media player.
Audio/video results use durable Artifact download URLs; transcription JSON also appears in the feed.
Transcript review and speaker naming remain input/editing tools, not a second output workspace.
Separation publishes each WAV and retains a host-issued ZIP download handled by the bridge.

Output retention/deletion MUST NOT remove private Line cache files, character reference materials,
or Gallery assets. Intermediate Lines generated for full-dialogue output stay private; only the
merged dialogue is published. Playing an existing private Line cache does not republish it.
New Mini-Apps must pass the shared output regression tests; private blob media results inside a
Voice Studio frame are not an acceptable implementation. Other Studios retain their own contracts.


Voice Studio text export uses the `export.text` bridge operation. The host validates the live mount,
allows only JSON/Markdown/SRT filenames, bounds UTF-8 content to 4 MiB, validates JSON, and stores
an owner-scoped Artifact before invoking Shell Save As. Never create iframe blob downloads for
Voice Studio text exports. The export also enters the shared Preview & Output feed.
Transcript correction edits segments and speaker assignments; saved drafts include the result.
Changing text invalidates word alignment but preserves segment start/end times.


Voice Studio built-in speech producers must use `ai2apps.readaloud.speech.invoke_speech` for
bounded sentence-aware synthesis. Preserve original text and per-request voice/expression/reference
settings; only publish the final concatenated WAV. Do not expose intermediate chunks in output
history or bypass segmentation for a new character/preview entry point. Long-Line cache keys
include the segmentation policy version.
