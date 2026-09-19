# Z-Image Base MLX 0.1.0 release — 2026-09-11

## Published

- Package: ai2apps/model-z-image-base-mlx 0.1.0
- Artifact: packages/ai2apps-model-z-image-base-mlx/dist/ai2apps-model-z-image-base-mlx-0.1.0-cloud-compatible.ai2service
- SHA-256: 1650f2b5723e73af4ab267fb5c984cbeee9faf5ebc3c4e8d005f63b5760d7ac1
- Size: 11914 bytes
- Publisher: 229d6350-cd0e-408a-9905-41367385ae5c
- User-approved existing key: f54e5b3f-375b-4fb0-a253-3e230f567327
- Public fingerprint: 4d0414816987a3c418897c8a8b7d7e2bad85acebb2534016298f76ba9a8d5102
- Submission: cad78ce6-5aeb-4abb-8681-3e3186bba2a6; published; Registry metadata 128.
- Uses standard --omit-model-install-catalog for current Cloud schema; source modelInstall and signed service model remain intact. Client compatibility maps are bounded through 0.1.0. Initial full-projection submission failed schema validation before creating a submission; no published artifact was overwritten.

## Checkpoint

- dist_ai2apps_z_image_base_04cc4abb_v1
- Submission 30a07ee3-0a95-4427-b0fd-b329bec1b447; published; Index63 anonymously verified, envelopeExactJson=true.
- Manifest digest sha256:038781d703c689a133bf2afc20a0ebfb0706cd58db394b309aa519389f772a38
- HF 04cc4abb7c5069926f75c9bfde9ef43d49423021; MS 77e77d0c115ea46c072f7f3f0f5aa82381f84c5b.
- 17 files, 20538488386 bytes, 2449 pieces; metadata_verified (HF local bytes vs authoritative MS hashes, not full dual download).

## Acceptance and remaining gate

FINAL LIVE ACCEPTANCE — 2026-09-11: App-Dev restarted on port 59377. Retried existing ACPF session, which reached ready without downloading weights again. Imagine Studio selected Z-Image Base MLX, prompt 胖胖熊猫吃竹子, no style, 1024x1024, 30 steps, CFG4, empty negative prompt (quality selector Medium). Real local generation succeeded; result isr_6a08567f2ff94a419bc9117e8863d297, Artifact imagine-text-to-image-ffa5f17d.png, image/png, 1024x1024. Add to Gallery returned Added to Gallery · Recent. Full page reload restored model, steps, CFG, prompt, output image, successful Run and Artifact. Screenshot visually verified a natural panda eating bamboo. First live run took roughly five minutes including initial quantized cache creation; no warm-run performance claim. The Gallery button's transient Added state resets on reload; image/Run/Artifact persistence passed. Earlier blockers below are historical and resolved. Live acceptance complete; no additional restart required.

Latest live acceptance update (supersedes restart blocker below): App-Dev restarted on port 53496, installed the published Package and downloaded all 19.13 GiB weights. Service running / health ok, ready logged at 2026-09-11T05:46:46Z. ACPF timed out at 95% because checkpoint validation did not recognize Base's Runtime-owned scheduler. Added exact backend (z-image, mflux-native-cfg), retaining missing-shard rejection; aligned Base ACPF verification to signed Service capability image-generation. 97 regression tests passed from repository root. A first run from ai2apps/ failed due to stdlib secrets shadowing. Remaining gate: restart Local again, retry existing install without redownload, verify actual Imagine generation and refresh recovery. Helper native control timed out twice; user restart required. No published artifact changed.

- Native Runtime1.6.2 Q8 1024-square / 30 steps / CFG4 / seed42: real panda image, 166.278s, Metal peak17950257918 bytes.
- Final exact artifact installed in independent /private/tmp/z-image-base-final-signed-install; Managed Service Worker running; Runtime1.6.2 dependency locked to 040bdf2e5bc32fed203bbc695d5bd34ebd5e514a70a7b38dd8a97f0cdc28943a.
- Standard smoke tool extended to verify distinct Runtime/model public keys separately; no signature checks removed.
- 43 Package/Imagine/Discover tests passed. CPU test teardown emits unavailable Metal warning; actual GPU generation used the installed Runtime successfully.
- App-Dev Discover visibly lists Z-Image Base MLX 0.1.0. Current Local still has pre-change Python discovery map loaded: Install model returns 'This Package does not declare a trusted model installation plan'. Restart App-Dev Local to load the new exact-version map, then complete installation, checkpoint activation, Imagine Studio generation and refresh recovery. These final live-App gates are NOT yet claimed passed.
- No existing Turbo package/model data was changed. No other instance was restarted.
- Cookie authorization used only for this Package and checkpoint publication and is now closed. No private key or Cookie exported or printed. The explicitly authorized legacy signing key was used through the standard Keychain builder.
