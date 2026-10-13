# Frozen Time Package / Host camera contract

The Mini-App Package owns presets, amplitude, keyframe count and timing,
smooth/linear interpolation, filter curves, poster selection and return-to-origin
playback. The same JavaScript sampler draws the canvas and compiles the request.
Drafts retain editable keyframes; draft serialization is separate from requests.

`trajectory` is a JSON Form field with exactly:

```json
{"schema":"ai2apps.camera-frames/v1","frames":[],"playback":[],"poster":0}
```

- `frames`: one object per model frame with pitch/yaw/roll (−20…20 degrees),
  radius (0.6…1.4), blur (0…12), saturation/brightness (0…2), exposure (−2…2).
  Values must be finite numbers, not booleans. Counts are bounded by the Host
  safety envelope and installed Meridian metadata (currently 73–243 supported).
- `playback`: integer source-frame indices, beginning with every original frame
  in order. Total length is at most twice the model frame count. The Package
  chooses the subsequent indices; Host does not decide where “origin” is.
- `poster`: an integer source-frame index.

Host rejects missing/unknown schema, extra fields, invalid values and invalid
indices. Maximum JSON length is 128,000 characters. No scripts, code expressions,
filesystem paths or model endpoints are accepted in the plan. Existing mount,
actor, instance and capability checks remain enforced.

Preview and rendering compare the complete validated plan, output, dimensions
and geometry model. Changing any sample invalidates the cached preview. Host
renders geometry and executes fixed generic filter operations using these values;
it does not interpret movement names, keyframes, amplitude or transition labels.
HTML keeps model frames in source order; video/Live Photo follow `playback`.

Schema-2 `conversion.json` retains sampled parameters, playback and poster with
the raw video. Conversion reuses them without inference or trajectory rebuilding.
Legacy schema-1/older exports retain their old conversion-only fallback; they
are not accepted as new generation requests. Old keyframe drafts are compiled
by the Package when reopened.

Adding presets or interpolation algorithms within this envelope requires only
a Mini-App update. New rendering primitives or bounds require Host capability
evolution. This migration changes Host and Mini-App together, not Runtime or
Meridian. No Package is published by this development change.
