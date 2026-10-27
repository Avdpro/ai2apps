# X post detail and media recovery

The phone's completed Task found eight media URLs but sent zero images to its
current model. The owner tried to reacquire each post using the timeline parser,
which requires a timestamp control; detail-page matching failures were silent.

The owner now has a detail-specific reader bound to the observed canonical post
URL, post ID and own author/status DOM. It excludes quoted-post links for identity
matching, reacquires fresh media references, and waits for known media to load
without requiring a timeline timestamp. The follow-up reply-context feature below additionally visits text-only post
details to discover originals.

If detail media or a screenshot target is unavailable, the X owner may open only
its already observed HTTPS `pbs.twimg.com` image URL in the same Default context.
Only `/media/`, `/amplify_video_thumb/`, `/ext_tw_video_thumb/` image paths are
eligible; credentials, alternate hosts and video URLs are rejected. Native image
document content type, exact origin/path and loaded image dimensions must read
back correctly before screenshot. No HTTP download, independent browser, invented
photo link or video-play action is used. The read capability's site scope includes
the observed image CDN; resolution scope remains unchanged. AS has no site rules.

X static video-cover images are marked `kind: video_cover`; photos remain `photo`.
Other platforms retain their existing player exclusion. Neither a cover nor a
video frame establishes the content of a video. All captures still go through
the current model and the existing 2-per-post default / 50-image / 10 MB bounds,
successful-cache reuse and unknown-model-attempt guards.

Every unseen record now has a reason, including detail identity/author mismatch,
missing detail/media, missing screenshot target, time/budget/default-selection
limits and model read/parse failure. Original detail failures remain separately
recorded when image-document recovery is attempted. Summary includes counts by
unseen reason. A successful cached review has no unseen reason.

Regression: 50 Python owner/media tests and 9 Chrome DOM tests pass. Coverage
includes timestamp-free detail identity, delayed readback, foreign post rejection,
static video covers, cross-platform exclusions, default/time reasons, strict CDN
recovery source validation and existing cache/model/JSON guards.

Initial live Dev Task `btask_70d24252b29908816b49395bfabcc10aef484ffbbb4e64e446c4d38a2bad5910`
used current `cloud/deepseek/deepseek-flash` and native Default user context
`3fff454d-4118-4ea1-8bbe-f2afb5e5ec27`. It successfully inspected one video-cover
image (43,900 bytes), reading “Government money is taxpayer money” and other
visible labels. Eight remaining records reported five `post_media_not_loaded`
and three `image_not_loaded_or_target_changed`; this exposed the need for the
native observed-image-document recovery above. Final continuation verification
is tracked separately below; initial partial evidence is not full acceptance.


Continuation Task `btask_38362f5894c4c607e6d9ad02a80da3a75a842a5b8a5de1aba3c6e53c61306648`
proved native image-document recovery for both named targets. Current DeepSeek
read “MV7” on the split-screen cover of post 2113288958738366650, and
“STARBASE / BOCA CHICA BEACH, TEXAS · SPACEX BROKE GROUND IN SEPTEMBER 2014”
on post 2113188655225618459. Three new model images consumed 177,361 bytes;
intersection with prior successful image inputs was zero. Two remaining records
were discovered to be player-overlay avatars; the final extractor explicitly
excludes X profile-image paths and preserves successful-cache media before
detail hydration. Text-only posts no longer falsely mark media coverage incomplete.

All 252 mandatory AaAT boundary tests passed, exit 0. The existing headless
Metal atexit warning did not affect successful completion.

## Final live acceptance

- Final Dev: PID24551 / port60059 / boot
  `bc272ac3-6293-4fa1-a463-82953c42da63`. App/Helper source roots, live Local
  `social_media.py`/`builtin_apps.py` paths and served mobile script bytes verified.
- Final Task `btask_c65f0354344711d1dc532473f3f2ae18daef2041a5d65316ca60d442da605122`
  / Run `run_f298b4ea273e409e8326d63b4df968b8` used the same native Default
  user context and current DeepSeek model. All **9 observed media records**
  (1 photo, 8 static video covers) were seen; unseen=0, partial_images=0,
  media complete=true. Both named targets retain their successful visual evidence.
- Five newly reviewed image inputs consumed 385,812 bytes; four prior successful
  records were reused. Intersection of prior successful image keys with this
  Task's model-image inputs was **zero**. Profile avatars were excluded. The Task
  completed and closed its owned pages with cleanup readback.
- The account timeline is still partial (`loading_stalled`, 19 observed posts),
  rather than a complete two-day archive. “All media seen” applies only to those
  nine observed records. Video content was not reviewed. Dev Chat visibly reports
  the Starbase image, each media result, cache reuse and the remaining timeline
  limitation. No social write, model switch or independent browser was used.
- One intermediate final-check form with a multi-hop old read-task reference
  could not resolve confirmation. It was cancelled before execution; fresh
  account resolution supplied the final confirmation. This existing continuation
  reference issue was not bypassed or represented as successful execution.

## One-hop reply and quote context (2026-10-23)

The social owner now visits selected X details even for text-only posts, because
short replies may depend on another author's original. `related_posts` separates
quoted/replied-to originals (author, observed canonical URL, text, timestamp,
images and review) from the selected account's own content. An original's date is
not filtered by the reply's date window and it does not count as another post by
the selected account. Quotes without an observed status identity and replies
without a verified nearest parent retain an explicit unavailable reason.

Only one hop is read. Reply-parent matching requires a reply marker and a matching
observed account on the nearest preceding conversation article; arbitrary earlier
articles and later recommendations cannot become a parent. Quoted text and media
are excluded from the current author's own fields. Original details use the same
native Profile, model, two-image default, 50-image task budget and durable review
cache. Shared originals are hydrated/reviewed once; total media coverage includes
deduplicated originals. AS has no site-specific changes.

Fixture acceptance: 53 Python owner/media tests, 11 Chrome DOM tests; 253 AaAT
boundary tests pass. Live
acceptance of this added context behavior is separate from the earlier image
recovery acceptance above.

Live follow-up found X quote cards without status hrefs. The owner now marks the
observed card, reacquires a fresh non-action text target on its source page,
clicks through native BiDi, then verifies the resulting HTTPS X status URL and
post identity. The source URL itself, foreign hosts, profile-only destinations,
stale targets and action-button hit points are rejected. Only the verified
one-hop original is hydrated, with no ancestor recursion. Missing safe targets
and unverifiable navigation have distinct reasons.

### Reply/quote live acceptance

Dev Task `btask_f98d147a39b3c57785504136de596aeaf9342bed038a16e1e7391b42a1f5b518`
/ Run `run_59af9f4f60234714babb02abffc4a02c` completed in Default with current
`cloud/deepseek/deepseek-flash`. All six selected quote originals resolved:
`america`, `realDonaldTrump`, `liam_fallen`, `WesternLensman`, `XFreeze`,
`TheCaptainEli`, with observed canonical URLs and original text. The Chat result
visibly separates Musk's short comments from each original author's content.
The Starbase original is `TheCaptainEli/status/2113179505862881395`; the “Yup”
original is `WesternLensman/status/2113223237375267146`.

Three observed original media (one photo, two static covers) were reviewed,
seen=3/unseen=0, 163410 input bytes. No video was played. XFreeze's embedded
video link was reported as not enumerated/reviewed; this is not full video
coverage. The live set exercised quoted posts; direct reply-parent linkage is
covered by DOM fixtures, not claimed as a live direct-reply acceptance.
The subsequent final guard retains already observed quote-card media if its
original detail has not loaded it, clearing stale refs for native image-document
recovery. This guard and fixed non-action click point have regression coverage;
they are separate from the above live observation.

Final guard activation: Dev PID48460 / port49573 / boot
`2fca58a4-c32f-4735-8ba8-aa80db6ae567`. Standard Helper restart occurred only
when Browser Tasks and running/queued Agent Runs were idle. App/Helper trusted
source-root metadata points to this checkout; live Local import log paths for
`social_media.py` and `builtin_apps.py` confirm the checkout. No static assets
changed in this feature. Native Dev Shell reconnected and the validation Chat
is restored. No App-Dev, Test, release snapshot or browser Profile data changed.
