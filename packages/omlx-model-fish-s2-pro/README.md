# Fish Audio Drama 3 4-bit

Requires Runtime >=1.8.20. Speech and reference cloning tested in Chinese and English.

Built with Fish Audio. This is the in-place S2 Pro upgrade: stable Package/service/model IDs are retained for existing roles and default selections. The legacy `/bf16` ID is an opaque compatibility key; the actual model is Drama 3 mixed 4/8-bit. Native multi-speaker and speed controls are not advertised. Emotion supports neutral/happy/scared/angry through native inline cues; normalized strength zero disables the cue, positive strength does not claim calibrated intensity.

Publisher scores: quality 5/5, speed 4/5. Median warm RTF 0.417 over 4 Chinese/English reference-clone samples on Apple M5 Max. Not a cold-start or cross-device benchmark. Checkpoint download 23781114058 bytes (including required codec). Minimum memory is a conservative capacity estimate, not a measured lower bound.

License: Fish Audio Community License. Read META/licenses/LICENSE.txt and NOTICE; download consent is required where the license requires it.
