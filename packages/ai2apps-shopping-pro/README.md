# Shopping Pro / 购物达人

AI Browser Mini-App for Amazon.com replenishment. The first version reads up to six pages from
the recent-six-month order list, computes observed date intervals, merges new records with saved history, and uses the Privacy standard
Task model to rank suggestions. Generating a list first checks recent orders in the same durable Task;
entirely known pages stop pagination, while page-limit gaps are disclosed. Users select quantities, refine the list in conversation, search
new products, and confirm cart preparation. The user reviews and places the final order on Amazon.

Sign into Amazon.com in the selected browser Profile first. The fixed development Package appears
in AI Browser via the trusted Development Package loader. Production installation/publication uses
the standard signed App Package workflow; this source Package has not been published.

The host implementation in `ai2apps/browser/shopping.py` is required: declarations use standard IR
operations with host-owned shopping arguments. All browser work uses the shared background Task
system and native BiDi. Natural interaction mode is mandatory for this Package. Never solve
verification or replay uncertain cart additions. Unsupported layouts/quantities or subscriptions
require user assistance. Existing cart items are retained, and requested quantities are topped up.

Shopping state is stored through authenticated host drafts in the local platform database. Closing
and reopening the UI restores state and watches an existing pending Task without resubmission.
Configure a trusted Privacy standard Task model; there is no fallback to Normal. Counts use observed opaque order/product keys when available; intervals use
distinct observed purchase dates (median interval), not complete order history or current stock.

## Amazon store and delivery preferences

Observed order events retain explicit Amazon / Whole Foods / Fresh channel evidence separately from same-day / next-day delivery windows. Incremental history merge enriches existing events without counting an order twice. The catalog summarizes counts and the most frequent preference (latest observation breaks ties). Unknown channel stays unknown; product brand names do not establish a store. Privacy AI uses these observed preferences and the list displays them. When a historical product link carries an observed almBrandId storefront selector, the host preserves that selector in a bounded Amazon product URL. Cart preparation checks current store and delivery evidence before adding or changing quantity; channel mismatch, unconfirmed grocery channel, or an explicit delivery mismatch pauses for user review. It does not choose checkout, delivery slots, subscriptions, or place orders. Existing history remains readable; refresh history to collect available channel evidence.

## Clear local purchase history

Delete shopping data requires entering the exact text `DELETE`, with Cancel focused first. Active Shopping Pro tasks prevent deletion, including a second backend check. The authenticated, mount-scoped Local endpoint removes the draft (including legacy undo copies) and scrubs shopping payloads from owned task programs, runs, steps, interactions, tool evidence, message parts, task-tree results and related event payloads. Only empty task/audit metadata such as IDs, timestamps and status remain. No new recovery copy is created; stale task references and old clients cannot re-save deleted content. Existing legacy copies remain stored until this explicit confirmation, but there is no Restore UI. Amazon orders, carts, profiles and sign-in remain untouched. Database secure-delete is enabled for the mutation and obsolete WAL frames are checkpointed when possible; this does not erase independent OS backups or retract data already sent to the user-selected model service.


## Last purchase prices and estimates

The shared background history task follows observed, fixed-scope order-detail links to collect per-product unit prices, never average order totals. Fresh uses its observed View all items table; its individual product-line total is divided only by that line’s explicit quantity (weighted rows remain unknown). Native and ARIA grid cells are supported and nested layout-table cells are excluded. Prices are retained per order event as integer minor units plus USD/HKD currency; the latest purchase date determines the displayed unit price, and conflicting or missing latest values remain unknown. A price-check marker avoids repeating inaccessible-price detail reads on each sync. The confirmation table estimates requested product quantities from last purchase prices, totals each currency separately, and excludes unknown prices with a visible count. Shipping, tax and current discounts are excluded; current Amazon prices and final checkout remain user decisions.

Cart quantities are matched by product ID and preferred store. A same product in another store is retained and does not satisfy or block the preferred store list. Grocery preparation opens an observed storefront selector and follows its observed cart link before adding; selectors are discovered only from actual Amazon links. Missing storefront/cart or unverified store pauses with guidance to open the preferred store and verify delivery availability. Quantity increments and post-add verification count only the target store. Final checkout remains manual.

Amazon grocery product navigation retains the `fpw=alm` grocery rendering flag with the bounded observed `almBrandId` selector. A URL selector alone is not channel evidence: the purchase button must be in a buybox with an explicit Fresh / Whole Foods badge. Fresh quantity popups use observed numeric options and native input. Empty and populated local-market carts are read separately from recommendation cards. The final report remains on the selected store cart rather than returning to ordinary Amazon.

Fresh local-market subtotal headings may contain screen-reader text such as “No items selected”; normalize whitespace and read semantic headings before identifying active product rows. Product links plus native quantity selects support rows that lack the standard Amazon cart wrapper. Exclude recommendation sections, wait for asynchronous add completion before navigating, and never repeat an add when the target cart quantity cannot be verified. The user completes checkout and selects any delivery slot.

## Multi-store cart preparation

Supported store channels are ordinary Amazon, Amazon Fresh and Whole Foods Market. Whole Foods links may identify the store as `WFMO` and may contain bounded Base64 padding; preserve only the observed selector and the grocery rendering flag. Never invent a store selector or use a Fresh buybox for a Whole Foods request. A mixed-store shopping list verifies each store cart independently and returns per-store links and quantities, including when the same ASIN occurs in several stores.

Same Day and Tomorrow are delivery preferences, not separate store channels. They remain separate from the preferred store and are checked against explicit current delivery evidence. Other unrecognized store channels require user review instead of silently substituting Fresh or ordinary Amazon. New channel adapters must cover history evidence, bounded observed product routes, buybox identity, native quantity controls, isolated cart reads and final verification. Whole Foods routing has automated coverage; no Whole Foods checkout or online cart addition was performed for this change.

## Conservative default replenishment selection

A default list requires at least two distinct valid purchase dates and elapsed time of at least 80% of the median observed purchase interval. The backend applies this gate after Privacy AI recommendation, using observed dates rather than the model's claimed urgency. Unknown cycles, single-date purchases and earlier-cycle products remain visible as unselected candidates, with a reason and lower score. Being a daily consumable alone does not justify selection. Eligible products still require the AI's consumable/utility recommendation; repeated purchases do not automatically select durable goods. Selected defaults sort by cycle urgency first. Explicit user chat revisions and manual selections retain user control. This is a purchase-cycle estimate, not a claim about actual household stock.

## Feature and website entry

Shopping Pro starts with a feature chooser. Everyday replenishment is available; Gift Recommendations is available; Food & Delivery, Trending Now and Seasonal Picks remain disabled with an In development badge. Replenishment then asks for the shopping website. Only Amazon.com is enabled; JD.com, Taobao/Tmall and Walmart are placeholders. Opening or returning between chooser views does not submit a task, clear history or rewrite the saved list. A restored active task opens the replenishment workspace for progress and assistance. Existing Amazon capabilities continue through the shared background Task system and Privacy model profile.

Keep this entry as a Web Mini-App while the feature workflows are being developed. A future independent Shopping App can reuse these capabilities, per-profile local storage and the platform Task/browser/model contracts. Do not enable a newly AI-generated site adapter for cart changes immediately: validate history extraction, product identity, quantity, store/cart scoping and user checkout boundaries before enabling it. Unsupported website cards cannot launch tasks.

## Interface languages

The UI follows the host `locale`: Simplified Chinese, Traditional Chinese (including zh-Hant/zh-HK), English, Japanese, Korean, French, Spanish, Brazilian Portuguese, and Russian. Unsupported locales fall back to English. The package-owned static `i18n.js` catalog loads before initialization and covers labels, dynamic counts, diagnostics, and dialogs without runtime translation requests. User content, product names, saved conversations and source quotations are not rewritten; new AI analysis continues to receive the normalized current locale.

## Gift recommendations

Gift recommendations use recipient, occasion, preferences and a USD budget. Three bounded Amazon.com searches feed standard-model ranking using Normal by default or Privacy when selected; only observed product IDs and prices can survive verification. Unknown prices remain marked unverified; known products above budget are excluded. Revisions are new durable background Tasks and may update an explicitly changed budget. Gift drafts and conversation are separate from replenishment state in the same host-owned local database; no purchase history is sent. Selection starts unchecked. Cart preparation requires a separate confirmation, validates product provenance and browser profile, and never checks out. All nine host languages are supported. Packaging, gift wrapping and guaranteed delivery dates are outside this first version.

Gift recommendations default to the Normal model profile. Users may opt into Privacy models for recommendation, revision, and cart preparation. Replenishment remains Privacy-only. The selected profile is passed through the shared background Task system; Privacy never falls back to Normal.
