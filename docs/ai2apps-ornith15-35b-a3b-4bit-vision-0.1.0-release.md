# AI2Apps Ornith 1.5 35B A3B 4-bit Vision 0.1.0 Release

Release date: 2026-08-29 (Asia/Shanghai)

Source commit at release time: `66736ccaed462e6f366b03d15c10aec5b43213ff`

## Checkpoint distribution

- Distribution ID: `dist_ai2apps_ornith1_5_35b_a3b_mlx_4bit_vision_31428ce8_v1`
- Status: `published`
- Submission ID: `e00aa03a-dbba-42f4-8b08-2e2797b59882`
- Review ID: `b0814c89-f8b1-4fe9-b391-879194fb5fdc`
- Published at: `2026-08-29T04:42:55.377Z`
- Manifest digest: `sha256:1135d851511b6baa9c6ba88ea9bd334e0a2183ac374729613b1b62be777a3c63`
- Payload: 19 files, 2,435 pieces, 20,422,417,145 bytes
- Hugging Face revision: `31428ce8829c277f9255c59662b8efab58898ecf`
- ModelScope revision: `2ceda9edec98ac813104d04f1fe05ca1b8fdae58`
- Anonymous verification: signed checkpoint Index v35 accepted and the public envelope was exactly equal to the locally signed envelope.

## Model Package

- Package ID: `ai2apps/model-ornith15-35b-a3b-4bit-vision`
- Version: `0.1.0`
- Status: `published`
- Submission ID: `62586a4b-4ea9-42e4-8685-f2628e22e3d8`
- Review ID: `ec012111-b209-437f-81a5-f7715a7b4bdb`
- Published at: `2026-08-29T04:46:04.974Z`
- Repository metadata version: 92
- Artifact SHA-256: `f2c466dd164b54e13cca32588e6920b4c8543230421753f96dac7c3ebd9b54bb`
- Artifact size: 182,909 bytes
- Publisher ID: `229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID: `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Publisher public-key fingerprint: `216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`
- Runtime dependency: `ai2apps/runtime-omlx >=1.5.6 <2.0.0`
- Compatibility: macOS 26.2 or later on Apple Silicon

The production archive contains 12 code, metadata, test, and Scope-profile files. It contains no checkpoint, safetensors, expert-store, or other model-weight bytes. The default execution mode is full resident; explicit Cached-MoE compact and performance modes retain the visual and multi-turn Worker path.

## Verification

- Four Package-focused tests passed.
- Package archive audit passed, including the immutable distribution binding, Runtime dependency, visual Worker adapter, and ten-Scope profile.
- `git diff --check` passed for the Package source.
- The public signed repository snapshot exposed the release as `published` at metadata v92.
- A clean anonymous Registry client downloaded the public artifact and verified its repository signature, Publisher binding, exact SHA-256, and exact size.
- The checkpoint-building tests that instantiate MLX could not run in the managed headless sandbox because no Metal device is exposed. This is an environment limitation, not a Package contract failure; real-device checkpoint construction and VLM inference remain separate hardware acceptance checks.

Publication used only the repository's standard signed-artifact builders and publication scripts. The authorized browser Cookie was passed only to the standard publication script for this exact release and its authorization expired when publication completed. No Cookie, token, administrator password, or private key was printed or stored.
