# Video Studio direct BYOK video API

## Scope

Video Studio's built-in text-to-video Mini-App offers direct API models in addition to local Model Packages. MiniMax H3 models also appear in the image-to-video and reference-to-video Mini-Apps:

- MiniMax Open Platform `MiniMax-H3`, `MiniMax-H3-Highspeed`, `MiniMax-H3-Lite`, and `MiniMax-H3-Max`, using `/v2/video_generation` and `/v2/query/video_generation/{task_id}`.
- Volcano Ark Seedance 2.5 `doubao-seedance-2-5-260628`, using `/api/v3/contents/generations/tasks`.
- Volcano Ark Seedance 2.5 Flash `doubao-seedance-2-5-flash-261115`, using the same task API and actor-scoped Ark key.

Ark's current video model catalog lists Seedance 2.5 and Seedance 2.5 Flash; it does not list a separate Seedance 2.5 Pro API Model ID. Do not invent a Pro ID or silently map a Pro selection to another model. This is distinct from the older Seedance 1.0 Pro family.

Both Seedance 2.5 variants and MiniMax H3 support prompts alone, first/last frames, and reference images, videos, and audio through the built-in Video Studio modes. Seedance requires a first frame when keyframes are used. Its reference mode also offers explicit reference generation, video editing, and video extension. The existing Local Package catalog remains available for all modes. No AI2Apps Cloud generation request or Cloud billing fallback is present. Every vendor request uses the user's key directly from the current Local instance.

## Credential and task ownership

The Models App's **Video API (BYOK)** section stores each provider key in the instance SecretBackend under an actor-scoped identifier. Video Studio only selects a model and links to Models when its key is missing. Provider discovery returns only a configured/ready boolean. A queued task stores the vendor model ID and prompt, never the key. The queue rechecks key ownership immediately before submitting the task.

The existing Video Task queue remains responsible for output Artifact creation, shared Output selection, history, and local cancellation. The adapter submits the task asynchronously, polls every ten seconds, and downloads the resulting MP4 over public HTTPS with bounded redirects and a 2 GiB limit. Vendor APIs currently do not report a reliable percentage, so the task remains in an active generation phase until the result is ready.

## Request mapping

Only prompt, whole-second duration, portrait/landscape ratio, the documented resolution tier and generated audio are sent. Local-only sampling steps, seed and presets are not forwarded. H3 accepts a prompt up to 7,000 characters. `MiniMax-H3` offers 768P/2K at 4–15 seconds; Highspeed and Lite offer 480P/768P at 4–15 seconds; Max offers 480P/768P at 5–15 seconds. The UI uses representative landscape and portrait dimensions to select each API tier; these are tier selectors, not a pixel-exact output guarantee. Image-to-video sends `ratio=adaptive` as required by MiniMax. The current UI offers concrete 16:9 and 9:16 ratios for text and reference modes. All variants share the user's MiniMax key. Seedance 2.5 exposes 480p, 720p, 1080p and 4K; Seedance 2.5 Flash exposes only 480p and 720p. Both list landscape and portrait sizes, default to 720p, and expose 4–30 seconds. The selected size maps to the corresponding Ark `resolution` tier in the actual request. Provider-specific details are owned by `video/byok.py` rather than shared model invocation code.

Frozen MiniMax inputs are read from the private Video Task directory and sent as data URIs directly to the official endpoint; they are never copied into a public asset URL. The adapter checks each file against the official 30 MiB image, 50 MiB video, and 15 MiB audio limits, then rejects a JSON request exceeding 64 MiB. The Host currently accepts PNG/JPEG/WebP images, MP4/MOV reference video, and WAV/MP3 reference audio for this path. Large media may exceed the request-body limit after Base64 expansion. Official documentation recommends public URLs for large inputs, but this local-only implementation does not publish user files. These data-URI paths still require paid provider acceptance testing.

For Seedance, first/last-frame and reference images plus reference audio are likewise sent directly as data URIs, with a 64 MiB JSON request cap. Reference videos may be supplied as public HTTPS URLs, one per line, or as local video files. The Host fetches and validates a supplied URL, retaining a private snapshot before forwarding the URL to Ark. For a local video, the existing Remote Access FRPC device host serves only the task's frozen file through a random, short-lived capability URL; the link is revoked when the video task ends. Issuance requires an active matching Remote Access connector. The public device boundary exposes no general file or artifact route. The file remains on the user's device; Seedance fetches it through the AI2Apps Cloud FRPC relay, which transiently carries the input bytes and may log request metadata. AI2Apps Cloud does not run the generation or store this video as a Cloud artifact. The shared Host caps local/downloaded inputs at 100 MiB, below Ark's documented 200 MB per-video ceiling. The exact FRPC ingress path and provider fetch must be verified on a live device; fixture tests do not prove Cloud edge routing.

Ark's Files API can upload a video using the existing API key, but the documented `file_id` use is for Chat/Responses video understanding; the Video Generation API documents a video URL or Asset ID. `CreateAsset` uses a separate AK/SK authenticated private asset workflow. We do not treat those identifiers as interchangeable or require an extra credential for this path.

Seedance image-to-video sends `ratio=adaptive`. Reference generation sends `omni_reference_task_type=reference`; editing sends `edit`, `ratio=adaptive`, `duration=-1`; extension sends `extend`, `ratio=adaptive`, and the selected duration. Editing and extension require a reference video. The current UI limits reference counts to 9 images, 3 videos, 3 audio clips, below the larger Seedance 2.5 provider limits, and requires a prompt. The Host accepts reference audio/video clips up to 30 seconds for these variants. Provider task classification can still reject a prompt whose intention conflicts with the selected type.

## Acceptance and limits

Fixture-backed direct HTTP tests cover key isolation, exact request fields, submit/poll/download, and normal Video Task regressions. Real paid generation remains unverified until each provider key is configured on the intended Dev instance. A provider task may keep running and incur charges after the local user cancels it, because stopping the local wait does not guarantee remote cancellation. If Local restarts while a remote task is running, the existing queue marks that task interrupted; automatic remote resume is not yet implemented.

Official API references: [MiniMax H3 task API](https://platform.minimax.io/docs/api-reference/video-generation-v2-create), [MiniMax video guide](https://platform.minimax.io/docs/guides/video-generation), [Seedance 2.5 guide](https://docs.volcengine.com/docs/ark/seedance-2-5?lang=en), [Ark Files API](https://docs.volcengine.com/docs/ark/file-api?lang=en), [Ark private asset guide](https://docs.volcengine.com/docs/ark/guide-preview?lang=en).
