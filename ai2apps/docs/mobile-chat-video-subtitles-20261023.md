# Mobile Chat video uploads and translated subtitles

Implementation: 2026-10-23. Business workflow belongs to Video Studio's
`video.subtitles` AaAT and the installed `ai2apps.media-voice.video-subtitles`
Mini-App. Shared AS receives declarations and resource IDs; it contains no video,
subtitle or Mobile routing special case.

## Input and transfer

Mobile Chat's single attachment picker accepts video/audio and documents.
It retains the File/Blob instead of reading a whole video or producing Base64.
Each transfer starts an actor/Session-owned upload; sequential binary chunks are
at most 4 MiB and fit the existing signed Mobile transport. Progress shows
acknowledged bytes and percentage. There is no automatic write retry or promise
of cross-client resume. Failed transfers attempt cancellation; completed
attachments are reused on retry in the same Session.

Uploads support up to 8 GiB per file. Completion requires the exact declared
length. Gallery adopts the staged file into its content-addressed storage by
rename, with bounded streaming hashing and no second input copy. Chat persists
only a Session attachment ID, Gallery asset ID and public metadata. Native paths
remain private. Gallery ownership, Session checks, fingerprints and deleted
asset checks apply before processing. Completed uploads are managed/reused/
deleted in Gallery. Small image vision inputs remain bounded and compatible.

## Subtitle workflow

The owner form accepts a Session attachment, owned Gallery material, or existing
Session artifact; it collects source/target language, SRT/VTT/ASS, bilingual and
optional burn-in. It uses the existing durable Video Studio queue, detailed
transcription, translation policy and subtitle renderer. Source video is opened
by Path for validation, audio decode and optional burn-in; output ZIP contains
subtitle and transcript, and optional rendered video. Existing transcription
currently has a one-hour duration limit. Model inference still needs decoded
bounded audio; an original-path reference does not mean zero processing memory.

Missing transcription or standard-task model configuration keeps the form and
materials pending. Desktop opens the owning Video Studio ACPF; Mobile explains
Desktop configuration and allows recheck. No installation, licence agreement,
model switching or task retry is implied. Upload needs a live client until
completion; submitted jobs run on Desktop independently of the phone.

Generated Chat files are explicit successful Tool outputs in the same Run's
Session. Mobile download verifies both recorded output and Session ownership,
then streams a FileResponse. Arbitrary URLs, raw paths, other Sessions and failed
Tool outputs cannot authorize a download. The UI presents download controls from
this generic file-result contract, regardless of provider identity.

## Evidence

- Backend/media/background/owner/Gallery regression: 126 passed.
- Bounded-upload/forms/Chat unit regression: 29 passed.
- Existing Mobile browser suite: 5 passed; combined with the new upload fixture: 6 passed.
- New Mobile browser fixture: 30 MiB Chat upload + 26 MiB form replacement, progress,
  reference-only message, Desktop guidance and reload persistence: 1 passed.
- Mandatory AaAT gate: 255 passed in the final rerun (118.67 seconds).
- Real queue fixture verifies source Path, no staged source copy, detached worker
  completion and translated SRT ZIP publication. ASR/translation responses in this
  test are fixtures, not live model evidence.

App-Dev live acceptance is recorded below after verification. The ordinary
browser Mobile page correctly requires a Mobile session; no authentication or
Cloud boundary was bypassed to simulate a phone. No actual iPhone test is claimed.

## App-Dev live result

Fixed App-Dev Shell `com.ai2apps.desktop.appdev.shell`, instance `app-dev`,
Local endpoint `127.0.0.1:62859`. App and Helper metadata both point to the live
checkout `/Users/avdpropang/sdk/omlx-moe-cache`. Current Local import logs show
`ai2apps/services/builtin_apps.py` from this checkout; served Mobile Chat,
Mobile task UI, signed connection and parameter-form assets match checkout.
No App rebuild was necessary (changes are all in hot-mounted ai2apps source).

Imported a real synthetic English speech MP4 through the actual native Gallery
picker (3.914 seconds, 43579 bytes). The normal Agent opened Video Studio's
subtitle form with the real Gallery ID, Chinese target, bilingual SRT and no
burn-in. After explicit form confirmation, actual installed model inference and
translation completed Studio Job `stjob_b9ccd3fdbee94828ac87877f412cb670` and Run
`strun_7ec2c640407f4815b85adee98be6a206`. No model was installed.

Private persisted job input references the existing Gallery blob; no staged
`source` input copy exists. Published ZIP contains `subtitles.srt` and
`transcript.json`. Read-back verified cues 0.000–0.400 and 0.720–3.920 seconds,
English "Hello." / "This is a test of translated video subtitles." and Chinese
"你好。" / "这是一段翻译视频字幕的测试。". Output was also imported into the original
Chat Session for authenticated Mobile download.

The live test is Desktop App-Dev UI + real model/queue execution. Signed Mobile
route authorization, uploads, progress, form replacement (30 MiB then 26 MiB),
missing-model guidance and reload persistence are covered by backend and browser
fixtures. A real phone/Cloud transport session was unavailable; that end-to-end
portion is not claimed. Upload completion still requires the phone's connection.
The existing Agent deadline and runtime availability policies remain in force;
the durable Studio job is the execution/status source, independent of the phone.

Final UI checks additionally cover reference-enabled form uploads using the same
bounded uploader, an explicit captured Session binding, and no authenticated
media preload for Mobile reference cards. No business names were added to AS.

Final static-source verification was repeated after App-Dev Local moved to port
65185; all four changed client assets still match the live checkout, and App/Helper
source roots remain correct. The published test result remains durable.
