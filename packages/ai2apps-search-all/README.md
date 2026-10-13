# 一搜到底 / Search All

AI Browser fixed-UI Mini-App. Select Google, Bing, DuckDuckGo, Brave, Wikipedia, Xiaohongshu, X, Weibo, Bilibili and YouTube; each source is a compiled shared background Task. Merge links and provenance, show the top three webpage/post/video cards per category with expandable results, and export JSON. A separate shared AI Task ranks results and translates webpage summaries to the app language; missing observed metadata is never invented.

See `ai2apps/docs/search-all-mini-app.md` for execution, scopes, limits, validation and development installation. Uses the normal trusted development Package loader; no separate installer. This source Package has not been signed or published.


Search options: `exclude_ads` defaults on (observed placement filtering plus AI
ad classification); `retain_pages` defaults off. Retained Task pages can be
activated from result origin buttons and closed together. The next search asks
whether to keep or close existing pages. Source errors show diagnostic codes
and bilingual recovery suggestions. Task page lifecycle remains owned by Local;
Mini-App channels serialize calls to the authenticated host. See
`ai2apps/docs/search-all-mini-app.md` for isolation and error contracts.

X search loads successive virtualized result screens within bounded scrolling. Foreign-language posts are translated into the app locale with a translation badge and expandable originals. Result links open through the authenticated host and native BiDi in the task’s browser Profile, even after the search page is closed.

## Interface languages

The UI follows the host `locale`: Simplified Chinese, Traditional Chinese (including zh-Hant/zh-HK), English, Japanese, Korean, French, Spanish, Brazilian Portuguese, and Russian. Unsupported locales fall back to English. The package-owned static `i18n.js` catalog loads before initialization and covers labels, dynamic counts, diagnostics, and dialogs without runtime translation requests. User content, product names, saved conversations and source quotations are not rewritten; new AI analysis continues to receive the normalized current locale.
