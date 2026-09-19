# AI2Apps checkpoint cross-cache deduplication — 2026-09-19

## Scope

The canonical checkpoint store remains:

`~/Library/Caches/AI2Apps/shared/checkpoint-cache-v1`

Fifteen complete signed distributions were present. Active files under
`partial/`, prepared model output, SSD expert layouts not present in a signed
distribution manifest, and unrelated model checkpoints were excluded.

Every candidate was matched by file size and full SHA-256 against the signed
distribution manifest before replacement.

## Result

| Source | Verified files | Logical duplicate bytes | Method | Observed physical space released |
| --- | ---: | ---: | --- | ---: |
| Global Hugging Face cache, per-instance caches, App-Dev reset backup | 369 | 342,412,178,555 | Hard links to immutable shared snapshot files | 130.18 GiB |
| Repository migration/build artifacts and ModelScope cache | 373 | 927,367,822,932 | APFS copy-on-write clones from shared snapshot files | 157.81 GiB |
| **Total** | **742** | **1,269,780,001,487** |  | **287.99 GiB gross** |

The filesystem's available space increased by 266.54 GiB from the initial
measurement. During the audit, the active shared-cache downloader added about
21.45 GiB under `partial/`, accounting for the difference from the 287.99 GiB
gross release. Final available space was about 1.4 TiB.

Logical duplicate size is larger than released physical space because some
files already used APFS clones, sparse allocation, compression, or shared
blocks.

## Compatibility and safety

- Hugging Face and instance cache paths were preserved. Immutable payload files
  now share the exact inode with the canonical shared snapshot.
- Repository artifacts and ModelScope files remain separate inodes. They use
  APFS copy-on-write clones so a future rebuild can modify a target without
  changing the shared checkpoint.
- The post-check found all 369 immutable cache files on the expected shared
  inode.
- All 373 clone replacements completed successfully and remained distinct
  inodes from their shared source.
- Incomplete historical DeepSeek V4/V4.1, Ornith, and Qwen Next Hugging Face
  snapshots were not treated as complete checkpoints. Only their individually
  verified metadata files were linked.
- The active `partial/` tree was not changed. At the final check it occupied
  about 105 GiB and still had recent writes.

## Reproducible tools

```bash
python3 scripts/dedupe_checkpoint_cache_copies.py --apply --report /tmp/cache-dedupe.json
python3 scripts/audit_checkpoint_manifest_duplicates.py --report /tmp/cross-cache-audit.json
python3 scripts/apply_checkpoint_duplicate_clones.py /tmp/cross-cache-audit.json --apply --report /tmp/clone-dedupe.json
```

The apply tools revalidate SHA-256 before changing a file and use an atomic
same-directory replacement.

## GLM 5.3 follow-up

After `dist_ai2apps_glm5_3_flash_4bit_mtp_ssd_a4d3f3e4_v1` finished
downloading, the shared cache contained all 99 files and 181,750,094,029
logical bytes. The `partial/` directory was empty.

- App-Dev had already installed all 99 files as hard links to the shared
  snapshot. The completed installation therefore did not create another 169
  GiB physical copy.
- Eleven metadata files in the global Hugging Face cache were verified and
  replaced with shared-snapshot hard links.
- Eighty-eight files in the historical chat-checkpoint migration tree matched
  the signed manifest, totalling 181,749,502,227 bytes. They were replaced with
  APFS copy-on-write clones.
- The separate 160 GiB `glm5-3-flash-q4-expert-store` did not match the signed
  checkpoint files byte-for-byte and was left unchanged.
- The operation released another 9.78 GiB of physical space. The smaller
  physical result confirms that most of the historical migration checkpoint
  already shared APFS blocks despite its full logical size.
- Post-checks found zero clone errors, 88 distinct clone inodes, and all 110
  cache references on the expected shared inode.
