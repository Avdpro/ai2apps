# Frozen Time / 静止时间

Image Studio Mini-App: still photo to camera-motion MP4, interactive HTML or
paired Apple Live Photo. Geometry preview precedes Meridian rendering. Motion
curves and saved presets belong to this Package; final results use host Output.

This lightweight UI contains no model weights. The host provisions the selected
Depth Anything V2 or VGGT-Omega geometry capability plus Meridian and H3 through
their separately published model Packages. Model licenses remain independent.

Requires an Apple Silicon macOS host exposing Frozen Time camera-frames/v1,
mount-bound drafts, preview/render/convert and asset.pick bridge operations.
compatibility.ai2apps describes the Package contract (0.1.0), not the Local
product version. Use Desktop 0.1.7 Build 2262 or later for the corresponding
host APIs and native Save As support. The contract range alone cannot identify
which historical builds expose these APIs; Host capabilities remain required.

Mini-App entry: ai2apps.imagine.frozen-time in ai2apps.imagine-studio.
Categories: image, video. No independent launcher entry.

Copyright AI2Apps. Package UI source is Apache-2.0 (see LICENSE).
Project: https://github.com/Avdpro/ai2apps


## AaAT ownership (0.1.3)

This release owns its executable AaAT declarations and parameter schemas in signed `app.yaml.mini_apps[].aaat`. It requires the versioned native Host SDK protocol declared by each export (`ai2apps.mini-app-host-exports/v1`). The matching Desktop host registers exports only while this exact Package is installed, enabled, and compatible. The capability catalog alone never enables execution. Older Desktop hosts must be upgraded for this ownership contract. Existing native queues, original material references, and shared Studio Output are reused.
