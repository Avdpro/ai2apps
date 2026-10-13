# News discovery WebAgent

News sources use the shared Local Browser Task and native BiDi SDK. Users enter
a URL; discovery, region learning, validation and recovery remain internal.

## Execution

`extract_list` with `news_scan: true` discovers links across rendered regions,
scrolls in bounded increments, and follows explicit same-origin News/Next links.
Only specifically labeled article/news Load More buttons outside forms/dialogs
are clicked, through native pointer actions. There is no guessed URL navigation,
generic Continue click or automatic login/consent approval.

Bounds: three list documents, eight scan rounds per document, two Load More
clicks, and at most 100 candidate links (Intelligence requests 40). Repeated URLs,
end of document, limits and no growth after Load More stop expansion. Articles
with clear detail paths are prioritized; unfamiliar URL schemes are preserved,
while obvious media, directory and category paths are excluded when a clear
article collection exists. These heuristics do not prove full-site coverage.

AI can choose up to six observed regions rather than a single region. Compiled
selectors apply only to the initial document; observed subsequent list documents
use generic discovery. Activation requires at least three baseline articles and
80% URL coverage, measured against baseline URLs rather than extracted URLs.
The normal collection path rechecks automatically learned rules against current
generic discovery and falls back when coverage drops. Explicit user-selected
Agents remain under user control.

Discovery metrics (documents, rounds, counts, termination reason) are kept in
collection `agent_stats.list_discovery`. No extra setup UI is required.

## F1 experiment — 2026-10-10

Used the fixed App Dev native BiDi host with a disposable userContext and window,
without user cookies or channel mutations. Started at https://www.formula1.com/.
The rendered News link contains duplicate text `NewsNews`; discovery handles it
and follows the observed https://www.formula1.com/en/latest link.

- Homepage generic extraction: 32 mixed links, including 17 article links.
- Enhanced discovery across homepage and News: 22 article links.
- Compiled `main` region plus bounded discovery: 100% coverage of those 22 URLs.
- 13 scan rounds, no Load More clicks required in this live sample.
- Test window/container removed at completion.

The compiled `main` region in this experiment was selected for the test; live
AI model selection was not exercised. This validates browser execution and
coverage comparison, not all historical F1 articles or the user's channel's
full digestion pipeline. Load More bounds have deterministic regression tests.

Repeat with `AI2APPS_F1_ACCEPTANCE=1`, the app-dev
`AI2APPS_SHELL_AUTOMATION_PATH`, and
`pytest ai2apps/tests/test_news_discovery_native.py` from repository root.
