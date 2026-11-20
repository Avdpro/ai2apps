# Cookie handling for read-only WebAgent work

The shared Local/frontend access inspector recognizes explicit necessary-only or
essential-only choices, including Accept necessary, Accept only essential cookies,
and equivalent Chinese labels. Accept all or combined marketing choices do not
qualify. Selection still uses the existing visible, enabled, hit-tested native
pointer path; this is not a preference grant to broader consent.

After safe dismissal candidates have been considered, a read-only page inspection
may ignore an unresolved consent banner without clicking it only when:

- Its visible area is at most35% of viewport and does not cover viewport centre.
- It has no modal ancestor or large positioned ancestor covering the centre.
- Outside forms/navigation/consent, at least two rendered headings/paragraphs,
  totalling160characters, pass actual hit tests as unobstructed readable content.

This applies to a corner consent iframe as well as DOM panels. A consent iframe's
own isolated inspection cannot infer readability of a parent page and remains
strict. Interactive checks remain strict by default. Full overlays, aria-modal,
hidden/sparse material, authentication, CAPTCHA and paywalls retain their guards.
No site/provider identity is used. The final generic optional-dialog loop must not
reclassify a banner already proven non-blocking for this read.

Validation2026-11-01:10 Node/browser tests passed including two unrelated origins,
necessary-only labels, untouched accept-all corner banner, modal/full-screen/
parent-overlay protection, missing content, iframe geometry, strict mode and
Local/frontend source equality; extended iframe fixture rerun passed.48 Python
access/input/lease regressions passed. Shared boundary gate recorded in release
ledger. These fixture checks do not execute external preference choices.

Live Dev AceFox SDK: SJX Accept necessary recognized as safe_dismiss; existing
native pointer path used once for only-necessary choice. Two repeated hidden-window
list scans each read17links using the saved rule; independent detail read returned
success with11364text characters and22images. No AI generation or Intelligence DB
writes, no login/captcha bypass. Native lease counts returned to0 and owned test
contexts closed. Uses a clean standard test container, not the user's managed
Profile; existing account/Profile preferences remain unchanged.
