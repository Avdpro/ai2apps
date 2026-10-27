# Intelligence incremental editorial composition v2

Owner implementation: `intelligence/article_merge.py`, `service.digest_event`,
`manual_import.compose_backbone`. No General Agent or Cloud policy changes.

## Source and backbone selection

Generation classifies incoming evidence as dedicated, mention or uncertain for
one exact subject/version/variant/event. Dedicated requires an exact quote from
supplied original title/text, a reason and factual-detail score 0..5. A more detailed
dedicated source may become the editorial basis; ties preserve the existing basis.
Roundups and incidental mentions supplement appropriate sections with attribution.
These are model editorial judgments, not guarantees of source authority.

Cover selection is independent of backbone score: an incoming dedicated cited
source with a usable cover replaces the old cover; mention/uncertain/no usable
cover preserves the old cover. With multiple dedicated incoming sources, choose
the most detailed. Legacy new-generation responses remain compatible with primary
source cover selection. A manual import forces its selected source's cover.

## Incremental updates and evidence

The planner still determines the single permitted update target. Only that target's
full body/blocks are supplied to generation, never all candidate old bodies.
Historical sources are appended to the evidence registry with scoped cached raw
text (60k characters per target; basis up to20k, others up to6k). Missing original
text is marked retained_only: it permits retention/provenance, never new assertions.
Canonical citations are remapped into one supplied evidence-ID space before the
call and compacted to article-local numbers on save.

New articles support bodies up to40,000 characters, compared with the previous
1,800-character prompt target. Existing updates omit body and return bounded
add/replace/remove/move operations, reasons and original-evidence proof quotes.
Unchanged paragraphs are retained verbatim. Add/replace paragraphs must cite their
proof sources; exact normalized proof quotes must occur in supplied original text.
Remove also requires proof; move retains the paragraph's images. Each existing
paragraph can be touched once; repeated additions after an anchor preserve response
order. The merged body cannot exceed40k or128 blocks; validation rejects overflow
instead of truncating old content. Existing source, citation, section and webpage
checks remain mandatory. Semantic factual fidelity still depends on model judgment;
exact quote checks alone cannot establish entailment.

## Stable presentation

`body` remains canonical plain text. `ai2apps.article-content/v2` adds:

- `editorial_sections`: stable ID/title records.
- Paragraph blocks: type, id, section_id, text.
- Image blocks: type, image_id, paragraph_id.
- `editorial_basis`, source focus records and bounded merge audit.

Paragraph identity survives correction/movement. Unchanged paragraphs retain their
images; replacing one removes attached images whose source is no longer cited.
Removed paragraph images remain in the source-bound gallery. New images must
reference supplied IDs and follow paragraphs citing their source. Up to24 original source-positioned inline images and48 gallery records are retained;
new optional editorial model placements remain limited to6 per response. Inline cover duplication is removed.
Storage validates canonical parity, source/image identities and attachments inside
its transaction. History retains editorial metadata and image bindings.
Desktop/Mobile share section/paragraph/figure rendering; malformed data falls back
to complete escaped body text. v1 and plain legacy articles remain readable and
are upgraded lazily on generation; no batch rewriting occurs.

## Manual import

A manually selected webpage creates a new channel article even when automatic
articles already cite its URL. Repeated manual import remains idempotent. Translation explicitly uses low reasoning when declared by the selected model;
otherwise it retains provider defaults. Article text is not shortened. Full
translated selected content becomes the fixed initial backbone, with per-paragraph
source attribution; classification happens before composition. Up to three relevant
same-channel articles can supply up to four cached original references (or retained original_content of a previous manual
webpage, never its generated translation; 24k total,
6k/source). Existing generated article text is never substituted for missing raw
source evidence. Supplemental generation uses add only: replacing, removing or
moving initial manual paragraphs is rejected. Selected cover, source/profile and
original translation metadata remain intact. No supporting references/images means
no extra composition model call. File attachment import retains its existing
original-content and opt-in image-summary behavior; it is already a separate manual
article, not an automatic merge target.

## Source paragraph/image adjacency

`browser_article_document.js` is a generic shared client SDK helper, locally bound
inside native BiDi script calls. It parses inert Readability content or the already
sanitized learned article region into bounded ordered source_blocks. Generic
HTTP(S) src/lazy-src/srcset resolution ignores data-URI placeholders. It does not
change Readability itself or extraction priority, add an alternate control protocol,
render raw HTML, or read hidden payloads. Page evidence/cache retains this structure.
Only nearby original paragraph text (up to300 chars per matching collected image)
is added to compact image candidates; full source_blocks are excluded from the
model's evidence payload to avoid duplicate token cost. Existing image collection
and source membership remain authoritative. Old cache entries need no migration.

## Validation evidence

Python tests exercise deterministic patches, proof refusal, source renumbering,
cover scope, stable images and manual-new-article behavior using model fixtures.
Browser fixtures exercise Readability-shaped/scoped extraction and v1/v2 rendering
at390/1440px. These are fixtures, not live paid-model or phone acceptance. The
repository AaAT gate remains mandatory. No existing channel articles are regenerated
or paid collection jobs triggered as part of activation.

## Committed manual-import result reconciliation

`GET /channels/{id}/import-result?url=...` reads only a committed manual article
owned by the current actor/channel with exact import identity/requested URL.
It returns null for no saved result (not success), enforces existing channel
access, and uses Cache-Control:no-store. Requested redirect identity survives
source composition. No browser, model, import or knowledge synchronization is
started by this lookup.

Desktop/Mobile URL imports check existing results before doing work. An uncertain
transport outcome after POST triggers read-only reconciliation for at most180s;
there is no automatic POST/browser/model replay. Confirmed saved results close
the dialog, invalidate relevant list caches and open the article. If not found,
the dialog explicitly says the outcome is unconfirmed. Existing synchronous import
endpoints and file-import semantics remain. This handles a lost HTTP result; it
does not make an in-flight HTTP import durable across Local process termination.

## Manual source layout and translation identity

Manual webpage translation consumes ordered source paragraph IDs and returns one
translated paragraph per ID, in the exact original order. Batches contain whole
paragraphs (target6k characters); a long paragraph is not cut at an arbitrary
character or word. Missing/reordered/merged paragraphs fail validation. Legacy
body-only model adapters are accepted only when paragraph counts match. Plain
source clients still work with server-generated source paragraph IDs.

The owner constructs initial image blocks from observed source positions before
any optional supplemental composition. Original HTTP(S) source-block image URLs
are authoritative extracted records, resolved server-side with original alt and
source attribution; uncertain/missing bindings are omitted. Source layout is no
longer optional model output. Up to24 images,128 blocks and48 gallery records;
cover duplicates are omitted. Images alone do not cause a second model call.
Translation/source maps survive later automatic updates. The same shared Desktop/
Mobile renderer handles this layout.

Legacy repair uses reviewed source-to-existing-paragraph correspondence, an exact
original-source/body comparison, owner access and a concurrent-content signature
guard. Store save preserves title/body/sources and snapshots the prior layout.
No translation or editorial model is called for this repair.

The article gallery is a complete image index, including the cover and images
already placed in the body. Unique URLs appear once in the gallery, sharing the
same viewer indices as inline figures. Desktop/Mobile use the same renderer.

## Automatic synthesized article photo decisions

Automatic generation uses original nearby paragraph text in available_images to
map relevant extracted photos onto synthesized paragraphs. For a cited source with
paragraph-bound noncover images, the result must include a source-validated image
placement, retain an existing binding, or provide a concrete image_omission_reason
(at least20 characters). Silent pure-text output fails the existing bounded model
validation/repair path. This is an explicit editorial decision, not a guarantee
that every source photo is relevant. Uncertain images remain omittable; no visual
facts may be inferred from filenames. Legacy sources without positions still work.
No normal extra model pass is added; six new model placements per response remain.

The owner source-layout repair method accepts an explicit source URL belonging to
the article and uses the same owner/revision/source/citation/block validation for
automatic and manual records. The manual-only wrapper remains compatible. Layout
repair never regenerates or changes canonical article text.


## Bounded parallel authoring (2026-10-26)

After the event plan passes existing source coverage and unique update-target
validation, up to three independent events generate concurrently per digest.
Post filtering and event planning remain separate stages; generation retains all
citation, image placement, backbone and merge checks. All workers read the same
frozen evidence numbering and previous-article snapshot. A plan that repeats an
existing update target is rejected before any worker starts.

Completed articles save synchronously through the existing owner callback and
checkpoint using their original plan indexes. Completion order does not change
article identity or final result order. Restart/partial retry skips saved indexes
and retries only unfinished events. A per-event502 failure does not discard
siblings; fatal errors/cancellation cancel and await all remaining workers before
returning. The UI shares active_articles, article_concurrency, events_completed
and events_failed progress fields across Desktop/Mobile; legacy single-article
progress remains readable. Concurrency changes latency, not prompts, validation
strictness, per-article token budget or number of planned articles.
