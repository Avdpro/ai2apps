# Comic Studio Agent integration

The independent ai2apps/comic-studio Package owns its bilingual UI, character and
series editing, scene prompts, captions, prior-panel references and scheduling
recipes. Its signed imagine.create_comic export draws a supplied 2–6 panel episode;
it does not silently modify a saved series or enable a schedule.

The generic studio.image-sequence/v1 Host SDK works for any trusted mounted Package.
It reuses image.workflow admission, model validation, private assets, durable jobs
and shared Output. It contains no comic or character identity branches. References
are resolved under the caller principal. Mounted ownership is rechecked before
submission and after completion. Returned PNG artifacts must belong to the exact
Host before being exposed in the caller Session.

Invocation receipts prevent duplicate submission. Cancellation, uncertainty,
provider errors and missing outputs cannot trigger automatic retry or model/provider
substitution. Existing durable jobs retain their identifiers and errors.

Bots discover the signed bilingual capability catalog, resolve finalized appearances
through character.list/get/use, and pass the definition image and description with
scene prompts and captions. Explicit model choices are honored; omitted choices
follow the existing preferred drawing model.

ASCBot captures drawing model, default panel ratio, panel count and prior-reference
count. Stories, character materials, history and schedules are excluded. Restore
never starts generation; panel-count changes require a blank episode.

## Series-aware exports (0.1.1)

`imagine.comic_series` uses `studio.project-query/v1`: omit `series` to list
saved series, or supply an exact ID/name to read its settings, character IDs,
readiness, revision and latest 20 episode summaries. The response includes
`library_revision`. Reading never requires an image model or changes a series.

The Bot authors a fresh script using this context, then calls
`imagine.create_series_episode` with `series_id`, `series_revision`,
`library_revision`, `title` and 2–6 `panels`. Each panel contains `scene`,
`caption` and existing series character IDs. Optional `model_id`, `ratio`,
`previous` and `columns` override this episode only. Defaults inherit the
series model, ratio, style/world, finalized character materials and prior-panel
reference policy. No schedule or new character is implicitly created.

The Package's `web/agent.js` owns query/prepare/commit and reuses the UI's
`ComicCore`. The generic Host executes declared pure transforms in an isolated
browser context, validates the resulting plan and reuses the existing image
queue. Commit appends the completed episode to the latest library while
preserving the editor draft. Versioned draft writes reject stale pages rather
than overwriting a Bot's new episode. Duplicate invocations reuse durable receipts;
commit retries never resubmit image generation.

Both project SDK protocols and the opt-in versioned draft bridge require the
matching Desktop Host. Dev/App-Dev were activated for testing; publication of the
Package alone does not update an older production Desktop. Native browser
query/prepare/commit were verified with fixture data, without paid model calls.
