# Intelligence article content blocks v1

Current incremental generation uses [v2](intelligence-incremental-editorial-v2.md).
This document describes the retained v1 compatibility format.

This owner format extends existing article JSON without changing the plain-text
body contract. No raw source/model HTML is rendered. Desktop and Mobile use the
same article renderer and existing authorized image delivery/viewer.

## Stored article

`body` remains canonical plain text for search, knowledge export, chat and old
clients. Optional `content_schema: ai2apps.article-content/v1` and `content_blocks`
provide an ordered presentation:

```json
[
  {"type":"paragraph","text":"First paragraph.[1]"},
  {"type":"image","image_id":"img_<24 hex characters>"},
  {"type":"paragraph","text":"Second paragraph.[2]"}
]
```

Image records in the existing `images` pool carry stable `id`, `url`, `alt` and
`source_url`. Identity hashes the exact source URL and image URL. The block does
not contain a model-provided URL or caption. Source and alt are server-resolved
from supplied collected image evidence. Figure source links use the article's
local citation numbering; original alt text is escaped rather than rewritten.

## Generation and validation

No extra model call. The existing event generation receives at most48 compact
image candidates (ID, source evidence ID, alt), with duplicate image URL payloads
removed from the evidence sent to the model. Its optional `image_placements`
contains `image_id` and zero-based `after_paragraph`; at most6 placements.

The owner validator rejects unknown IDs, unreferenced-source images, repeated
images/URLs and out-of-range paragraph positions. The receiving paragraph must
cite the image source evidence ID; merely appearing elsewhere in the article
is insufficient. Schema forbids extra placement
fields such as arbitrary URLs. Existing fact/citation/merge/source and webpage
checks stay unchanged. Uncertain/redundant images may be omitted; labels are not
independent visual proof. Do not infer new claims from an alt label.

After citation renumbering, the server builds blocks from the exact canonical
body paragraphs. Storage checks their exact parity, image identity and membership
in current article sources, inside its existing transaction. Referenced images
are kept within the48-image pool, including during manual gallery refresh.

## Compatibility

Old model responses/old articles without placements remain plain text. No batch
rewrite of user articles or migration is required. New generated updates build a
fresh block set; an update without blocks drops the old placements. Existing
manual translation/image-summary body replacement explicitly clears stale
placements. History snapshots retain block/schema/image data along with the old
body and sources; the existing historical text display remains available.

The reader validates the block set against canonical text/current image pool and
falls back to the complete escaped plain body on unknown schema, mismatch or bad
references. Mixed figures use existing image indices, carousel, origin link and
image import controls. The trailing gallery lists all article images, including those placed inline,
with the same deduplicated order and viewer indices. The cover is independent. No schema changes to
channel cards/progressive list payloads: full blocks arrive with article detail.

## Scope

This upgrade supports source-bound editorial placement in synthesized articles.
It does not yet preserve Readability paragraph/image adjacency as source blocks,
perform image understanding, or change extraction priority to Readability-first.
Old article summaries are not automatically regenerated.

## Tests

Owner Python generation/storage fixtures cover multi-source selection and citation
renumbering, invented/wrong-source/duplicate/out-of-bounds references, legacy
responses, history, gallery refresh and owner isolation. Browser fixtures at390
and1440px cover paragraph/figure order, escaped captions, source links, no repeated
gallery entries per unique URL, click-through to the existing image viewer and complete fallback.
These are fixture model outputs, not a live paid model acceptance run.
