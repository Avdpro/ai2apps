# AI Browser Mini-App library

The application list uses a scrollable card area and a fixed bottom **More Mini-Apps** menu. It offers **Install Mini-App** and **Customize Mini-App**.

Installation opens the shared ACPF Package chooser. It reads the existing Registry catalog and displays only Packages whose `miniApps` metadata explicitly includes `ai2apps.ai-browser` in `placements`. Missing placement metadata does not qualify. Pagination is bounded per request; unavailable or empty catalogs are explicit. Development source mounts do not count as published Registry Packages.

User-selected installation uses the existing Registry `install-operations` endpoints, retaining their signature, dependency, authorization and audit checks. The UI never sets `approve_review=true`. Review or dependency errors remain visible rather than being bypassed. Completion refreshes the installed Mini-App library.

Customization collects a name and requirements, creates an owner-scoped local AI2Apps Coder project with a generated relative directory, and passes a one-time same-origin `sessionStorage` handoff to Coder. Coder resolves the project only within the current owner's project list, clears the handoff and opens the existing Native Coder draft workflow. With an available tool-capable model it starts development; without one it asks the user to configure a model. Applying the resulting draft remains in Coder's normal review flow.

The generation brief requires a private local Web-Agent Mini-App Package, fixed UI, declared capabilities and AI Browser placement; all WebAgent execution must use the common background Task system and authenticated host SDK. Publishing or uploading is excluded from that brief. This is private project ownership, not a guarantee that the selected coding model is local: Coder retains its existing configured model selection.

No Cloud API or native browser-control protocol is added by this UI.

## Shared Studio entry points

Imagine Studio (`ai2apps.imagine-studio`), Video Studio (`ai2apps.video-studio`) and Voice Studio (`ai2apps.readaloud`) use the same fixed-bottom menu. Their templates include `_mini_app_more.html`; `studio_mini_apps.css` gives the cards their own scroll region while the footer stays outside it. The nine host locales provide the menu and customization form labels.

The ACPF chooser accepts only the four known host IDs and filters explicit manifest placements for the current host. Studio customization uses `createPrivateMiniAppProject` and the existing Coder handoff. Each brief binds the generated Package to the selected Studio and its host SDK/output contract. Voice Studio explicitly requires the shared Quick Read Preview & Output and preserves private Line caches. Studio generation does not inherit AI Browser's WebAgent execution requirements. Installation refreshes the host catalog/readiness without replacing the current working draft or output.

## Built-in browser research and goal fallback (2026-10-29)

Search All and Web Reader ship inside the AI Browser App, with exact resource
allowlists and native AaAT declarations. They require no registry Package install.
Their former Package source snapshots are retained only as historical regression
fixtures under `docs/retired-package-sources/`; they are not development Package
roots or publication candidates. Shopping Pro and Trip Planner remain Packages.
Product-owned Mini-App identities take precedence over obsolete installed copies;
foreign Package declarations cannot override built-in identities. All resource,
mount, Session, Profile and current declaration checks remain enforced.

`web.search` prefers built-in Search All, defaulting to fast mode. Search source
selection and paid-route consent retain the same preparation/confirmation receipts.
`web.fetch` prefers built-in Web Reader for reading text from a single known final page.
Use `browser.complete_goal` to navigate from an observed entry URL, filter a site,
open detail pages, or expand controls. When Search All finds links but verifies
no article bodies, its Tool result reports partial coverage and returns candidate
URLs for further investigation. Those links carry no factual evidence by themselves.
HTTP alternatives are not screenshot
readers and should not silently replace browser tasks.

`browser.complete_goal` uses the existing durable browser queue to investigate
from a public starting URL. Choose it for navigation from a landing page to
evidence, including site search, opening detail pages and expanding sections.
Search All finds a starting URL. Web Reader reads a known final page. When a
read returns a timeout or yields insufficient evidence, the Bot can investigate
from a reliable starting URL. A specialized Mini-App remains appropriate when it
covers the whole task.

The initial navigation has a 10-second budget from the native BiDi request
until the main document is interactive and has a rendered body. Browser startup,
blocker handling, article extraction, and model calls use separate budgets.
Web Reader reports which phase timed out. If a page opens but yields no
article body, its observed URL can be handed to website investigation when the
remaining work requires interaction. Normal access checks still apply.

If website investigation reaches its action limit, it stops taking actions and
summarizes the available in-scope observations. The result identifies partial
coverage and names any requested facts that the observations did not establish.

The scope is read-only. Login, CAPTCHA, consent, cancellation, uncertain-action
and Profile guards still apply. `visual=true` adds a native BiDi screenshot
observation through the declared vision route. Functional Mini-Chat scope stays
limited to its selected Mini-App.
