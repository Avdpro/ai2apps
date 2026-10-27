# Bilibili subtitle reader

The native BiDi Web Reader discovers subtitle tracks for the bound video and
selected part instead of treating player duration labels as article text.

## Identity and discovery

- Bind the article's `url` and `subtitle_video_url` to the observed original video
  URL, including its part query. Subtitle CDN URLs never replace this citation.
- Read the current video identity from `__INITIAL_STATE__`, or resolve the exact
  URL's BV/AV identifier through `https://api.bilibili.com/x/web-interface/view`.
  Reject a different returned video; select CID from the requested part.
- Query only `https://api.bilibili.com/x/player/wbi/v2` with the verified video
  identity and CID. Reject any returned identity mismatch. The browser performs
  these normal requests in the existing actor/Profile; no Cookie values are
  read, exported or copied.
- Distinguish `login_required`, `no_tracks`, `api_error`, `discovery_failed` and
  `subtitles_loaded`. An empty track list after `need_login_subtitle=true` does
  not mean that the video has no captions.

The protocol is independently implemented by yt-dlp's Bilibili extractor:
https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/bilibili.py
(`_get_subtitles` and `json2srt`). This is research reference material, not a
runtime dependency or copied implementation.

## Files and output

Discover `subtitle_url` only through the bound player response, matching page
state or native text tracks. Prefer Chinese tracks and human captions when
available. Accept HTTPS resources only on the exact subtitle hosts, or the
subtitle paths of the three explicitly listed image CDN hosts. Omit credentials
for subtitle downloads, reject redirects, bound each response to 1 MiB and
8 seconds, and try at most four tracks. No video/audio download or automatic
speech recognition is performed by this path.

Parse JSON `body[].from/to/content`, VTT and SRT into validated cues:
`{start_ms, end_ms, text}`. Invalid, non-finite, negative or reversed timings
fail explicitly. Keep full `subtitle_cues` and timecoded `subtitle_text` in the
stored Web Reader result. Bound the ordinary `text` preview using `max_chars`
and mark truncation; preview limits do not discard the complete cue data.
Retain selected track language, identity, provenance and file URL separately
from the citation URL.

Search All preserves this structured result through its durable read steps and
article records. The summarizer sees timecoded evidence and content kind.
Description-only reads do not satisfy subtitle coverage during bounded source
replacement reading. The parent Agent can cite only the server-bound original
video URL, using the shared source-ID citation contract.

## Acceptance

Fixture tests cover discovery, selected-part CID, complete timed text, original
video binding, metadata fallback, login denial, malformed/foreign tracks,
subtitle hosts, credential/redirect policy, JSON/VTT/SRT parsing and preserved
cue data beyond preview limits. A successful fixture is not real subtitle
acceptance. Live acceptance must record actual track identity, language, cue
count/time span and a summary point grounded in those captions, with a final
citation exactly matching the read video's URL. A description fallback does
not pass this acceptance.

Live App-Dev acceptance on 2026-10-19, after Default Profile login:
General Run `run_78f1ff2df7204576aa5480c4fbcda0db` and Search All child
`run_791a45b0f7594edba600d2a43e046651` completed. Player API discovery and
actual `ai-zh` subtitle-file downloads yielded 277 cues for `BV1K2HJzuEob`
(00:00:00.040–00:11:24.260) and 240 cues for `BV1gZty6JEW6`
(00:00:00.120–00:05:43.620). Recipe points used these captions alongside
Google-discovered Xiachufang and two Xiaohongshu articles. All 35 final citation
occurrences across five URLs match successful read originals. The citation
guard used the verified report fallback because the parent omitted source-ID
markers; native Chat shows the grounded report and both original video links.
The live run exposed missing `ai_type` on `ai-zh` tracks; a subsequent small
provenance correction infers automatic captions from `ai-*` language codes,
covered by the thirteenth JavaScript test. The 90 affected Python cases pass.
