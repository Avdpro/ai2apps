# Shared character appearances: UI, ASCBot and AaAT

Character Design is a built-in Imagine Studio Mini-App. Its editor and shared chooser
use the existing Chinese/English locale. ASCBot registers the Character Design target
with the standard image-settings contract: model, visual style, canvas dimensions,
quality and format. Private identity editing, images and permissions are excluded from
portable shortcut packets. Selecting an identity for a business task uses AaAT below.

## Consumers

Sticker Workshop has a read-only character/appearance chooser with definition-image
and prose preview. Using it loads the definition into the primary standard resource
Slot and carries its summary into both single and batch sticker prompts. Replacing
the primary image invalidates that prose association. Drafts preserve the association.
Comic Studio loads the shared library at startup and imports a selected definition
and summary into a series character. Existing series entries remain intact. Both
consumers use finalized appearances only and refresh availability before selection.
Source reference photos and generated history are never substituted for a definition.

## Gallery-owned AaAT operations

| Capability | Purpose |
| --- | --- |
| `character.list` | Compact listing and search by name, alias or appearance name; optional finalized-only filter. |
| `character.get` | Read editable identity and appearance settings with exact revisions. |
| `character.create` | Create a named identity, without image generation. |
| `character.update` | Patch identity name, description and aliases using its current revision. |
| `character.appearance.create` | Add an independent named appearance to an identity. |
| `character.appearance.update` | Patch one appearance, including source references, definition image and reusable summary. |
| `character.use` | Import one finalized definition image into the caller Session and return its summary and pinned versions. |

Existing `gallery.character_definitions`, `gallery.import_materials` and
`gallery.save_artifact` remain compatible. UI and AaAT share `Characters` owner
validation and Gallery ownership checks; no General Agent business branches were added.

A Bot looking for a sticker should search first, read the selected identity if needed,
then call `character.use` with returned IDs and character revision. Pass the actual
returned image artifact and summary together to the appropriate drawing capability.
A request such as “use Lao Huang's chibi look” must resolve to an existing named look;
ambiguity requires clarification, rather than silently choosing another appearance.

For authoring, create the identity if requested and absent, create/patch its appearance,
and use existing drawing capabilities if an image must be generated. Save an actual
result to Gallery, set `definition_image_id` and `summary`, then request finalization.
A final appearance needs both image and prose. Editing saved content clears finalization;
returned `approved` is authoritative. Do not report generation after only editing settings.

Every write after creation and every `character.use` checks the current character
revision. On a conflict, reread and reconcile; do not blindly retry writes, regenerate,
or change model/provider. Owner authorization is supplied by existing tool access
checks; declarations and returned IDs do not grant new permissions.

## Verification (2026-11-20)

- Actual App-Dev: Comic Studio automatically listed four finalized looks belonging to
  the user's two characters. Sticker chooser showed a definition image and guide;
  using it loaded the primary Slot and appended the guide to the submitted Prompt.
  No drawing request was submitted.
- Owner tool gateway fixture: identity creation, independent appearance creation,
  revision conflict, missing-definition finalization rejection, definition assignment,
  finalization, alias search, single-image handoff, identity edit, and owner isolation.
- ASCBot contract validation and JS registration/capture tested; shortcut packets exclude
  character materials. No live Bot conversation or paid model call used for acceptance.
- Focused Node suite: 24 passed. Character persistence and App-State Python suites: 26
  passed; new owner tool test also passed. Provider form translations: 2 passed.
- Canonical scoped AaAT gate has unrelated existing shared-AS dependency violations
  in cloud_gateway imports of images.background and images.byok_capabilities; see receipt.
