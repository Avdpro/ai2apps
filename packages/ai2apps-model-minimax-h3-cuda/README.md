# MiniMax H3 CUDA — development source

FL2VA and Ref2VA use fixed official Comfy checkpoints with generated stereo audio.
Variant selection is stored under metadata so it survives Host normalization.
The Runtime must include the H3 metadata fix recorded on 2026-10-09; earlier
unsigned integrated candidate r2 is not suitable for this Package.

This draft covers the two existing base variants only. LightX2V, OpenVDN and
Avatar remain separate work in the parity inventory, not implicitly supported.
Ref2VA currently accepts up to four images, one video and one audio reference;
Mac permits more. Fast presets, continuation and wider reference counts are
not declared here and remain capability gaps. Default generation uses the
existing CUDA adapter settings, not Mac quantization presets.

Fixed distribution candidates are signed but unpublished; distribution_id is
intentionally absent. No weights are bundled. Model license and installation
consent remain user-owned. Formal signed installation/GPU acceptance of this
Package is pending; Runtime >=0.6.0 is required.
