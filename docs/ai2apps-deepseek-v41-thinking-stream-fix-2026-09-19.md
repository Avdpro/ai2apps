# DeepSeek V4.1 thinking stream separation fix

Date: 2026-09-19 (Asia/Shanghai)

Status: fixed, App-Dev verified, and published in Runtime 1.7.6

## Incident

With DeepSeek V4.1 thinking enabled, Chat displayed the Thinking panel but also
placed the same reasoning draft in the visible answer. The duplicated body began
with an invalid Unicode replacement character. The persisted failing turn proved
that `reasoning_content` was already correct while `content` contained a replayed
copy of the reasoning:

```text
Hi! �We need answer. ... Respond.Hi! 😊 How can I help you today?
```

This excluded the Chat renderer and Host persistence layer as the source of the
mixing.

## Root cause

The dedicated DeepSeek V4.1 engine decoded every growing token prefix with
`skip_special_tokens=True`. That removed the model's special `<think>` and
`</think>` tokens before the Worker reasoning parser could observe the boundary.
The same prefix-difference loop also emitted a transient U+FFFD while a multi-byte
UTF-8 sequence was incomplete; when the next token corrected that suffix, the loop
treated the revised full text as a new delta and replayed it.

## Fix

- Preserve special reasoning boundary tokens in the engine stream.
- Exclude EOS explicitly instead of hiding every special token.
- Withhold a trailing U+FFFD until the tokenizer has enough bytes to decode the
  complete character.
- Enforce append-only deltas; a decoder regression can no longer replay the whole
  generation into visible content.

## Verification

- Focused Runtime/Worker reasoning suite: 11 passed.
- Rebuilt the fixed App-Dev environment with
  `apps/ai2apps-acefox/scripts/build-app-dev-environment.sh`; the previous App was
  archived and the durable `app-dev` data was preserved.
- Restarted only `app-dev` Local. New boot ID:
  `f5a8e693-38f8-4c8f-9377-bd85771b6a03`.
- Real DeepSeek V4.1 request: `请只回答：你好`.
- Live UI showed the draft only under Thinking and the visible answer only as
  `你好`.
- Durable message record confirmed separate fields: the reasoning draft was stored
  in `reasoning_content`; `content_json` was exactly `{"content":"你好"}` with no
  U+FFFD and no duplicated reasoning.

## Release boundary

The fix changes oMLX Runtime code and is not attributed retroactively to immutable
Runtime 1.7.5. It shipped as `ai2apps/runtime-omlx` 1.7.6, frozen from the notarized
1.7.5 payload with only `omlx/patches/deepseek_v41/engine.py` overlaid. The existing
DeepSeek V4.1 model Package remains compatible: its `>=1.7.5,<2.0.0` dependency can
upgrade to 1.7.6 without changing checkpoint bytes or Package behavior.

Apple accepted notarization submission
`06b63e09-2d23-47c5-91b2-f6fbf7ea79a4`; the stapled DMG passed Gatekeeper. Cloud
submission `8a9f69d0-4512-4e3b-bdbb-ad9c0cce2f98` was published at Repository
metadata version 178. Anonymous public readback matched the local Package and
envelope exactly, and an isolated managed install started the DeepSeek V4.1 Worker
with a dependency lock on the exact Runtime 1.7.6 digest. The complete receipt is
`docs/ai2apps-mlx-runtime-1.7.6-deepseek-v41-stream-release.md`.
