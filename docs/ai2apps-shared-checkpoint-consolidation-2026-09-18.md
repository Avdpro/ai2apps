# AI2Apps shared checkpoint consolidation — 2026-09-18

## Outcome

All complete Registry checkpoint distributions found in AI2Apps per-instance
checkpoint caches were verified and consolidated into:

```text
~/Library/Caches/AI2Apps/shared/checkpoint-cache-v1
```

The migration found 17 per-instance manifests representing 11 unique
distributions and 242,531,923,853 logical bytes. Every shared snapshot passed a
full manifest size and SHA-256 verification before source removal. The final
shared cache contains 11 manifests and 11 snapshots and reports approximately
203 GiB through `du`, reflecting content-addressed file reuse and hard-linked
snapshot views.

## Migrated distributions

- `dist_ai2apps_flux2_klein_4b_e7b7dc27_v1`
- `dist_ai2apps_ideogram4_fp8_bbee2ab2_v1`
- `dist_ai2apps_punctuation_restorer_5cccf43a_v1`
- `dist_ai2apps_qwen3_8_27b_nvfp4_16b6615a_v1`
- `dist_ai2apps_qwen3_asr_0_6b_4bit_313d8501_v1`
- `dist_ai2apps_qwen3_tts_1_7b_custom_voice_8bit_41d3337e_v1`
- `dist_ai2apps_qwen_image_2512_25468b98_v1`
- `dist_ai2apps_qwen_image_edit_2511_6f3ccc0b_v1`
- `dist_ai2apps_sensevoice_small_8ddd966b_v1`
- `dist_ai2apps_z_image_base_04cc4abb_v1`
- `dist_ai2apps_z_image_turbo_f332072a_v1`

## Removed private caches

After the shared verification gate passed with zero errors, the migration
removed the seven discovered per-instance `checkpoint-cache-v1` roots under
the `app-dev`, `dev`, `dev-acpf-20260903`, `dev-acpf-clean-20260903`,
`dev-acpf-clean2-20260903`, `main`, and `test` instances. The `main` cache was
empty before migration. A final filesystem scan found no remaining
per-instance `checkpoint-cache-v1` directory.

Instance-specific Worker checkpoint views, installed Package state, prepared
model output, and model runtime state were outside these source roots and were
not removed.

## Validation and receipts

- Migration utility: `scripts/consolidate_ai2apps_checkpoint_caches.py`
- Utility safety tests: 2 passed
- Ruff: passed
- First-stage receipt:
  `artifacts/shared-checkpoint-consolidation-20260918/migrate.json`
- Verified-delete receipt:
  `artifacts/shared-checkpoint-consolidation-20260918/delete.json`
- Final receipt status: `complete`; 11 unique distributions; 7 source roots
  deleted; 0 errors.
- Post-delete forced-offline acquisition of
  `dist_ai2apps_punctuation_restorer_5cccf43a_v1` returned `cache_hit=true`,
  `source_bytes={}`, and an existing shared snapshot; the transport was wired
  to fail on any network request.

APFS clone semantics and content-addressed reuse mean logical directory totals
must not be interpreted as exact physical free-space changes. The final volume
reported approximately 1.4 TiB free through the rounded `df -h` view.
