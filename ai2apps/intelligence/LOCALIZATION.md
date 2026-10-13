# Intelligence Center localization

The interface follows the host UI language. Simplified Chinese and English
translations are provided in `web/i18n/zh.json` and `web/i18n/en.json`; other
locales currently use the host's English fallback for Intelligence Center keys.

`web/static/js/intelligence_i18n.js` resolves authored strings through the host
catalog. Its template tag translates static template segments only: interpolated
article text, entity names and user input are preserved. Add matching catalog
entries and a source-key mapping when introducing new authored UI strings.
Dates use the active interface locale.

Each channel can persist an independent `output_language` for AI-generated
content. Supported choices are Simplified Chinese, Traditional Chinese, English,
Japanese, Korean, French, German, Spanish, Brazilian Portuguese and Russian.
Background collection uses the saved choice. Older channels without a choice
fall back to the request language or host UI language, then English. Changing
language does not rewrite previously collected content.

Checks: `tests/intelligence_i18n.test.cjs` and
`tests/test_intelligence_language.py` cover static localization, preservation of
user content, template rendering, fallback and persisted language precedence.

## Activity and recent UI additions (2026-10-13)

The current host display-language setting provides Chinese and English. Recent
collection, manuscript, image and entity controls now have full authored-string
translations rather than relying only on fragment replacement. Known backend
activity and result messages are rendered through catalog templates, including
source statistics, cooldown messages and partial editorial failures. Captured
source names are interpolated unchanged; unknown diagnostics remain unchanged.
Both Desktop and Mobile use the same resolver. Regional interface locales are
normalized before selecting the default AI output language for a new channel.
Existing channel output languages and previously generated content are preserved.
Other interface locales continue to use the host English fallback; this change
does not claim complete native catalogs for those locales.

Regression checks additionally cover new authored `lt()` strings, message
placeholder parity, source-name preservation, regional language normalization,
and English Mobile/Desktop rendering with Chinese user content.
