# MuseTalk CUDA release preparation

Development preparation only: not installable, signed or published.

The Package entrypoint delegates to the pinned CUDA Runtime MuseTalk adapter.
The Runtime owns the engine, official source, preprocessing and native libraries;
no duplicate Torch/CUDA or model weights are bundled here.

The Host selects five independently verified snapshots: MuseTalk UNet, SD VAE,
Whisper tiny, YuNet detector and BiSeNet parser. Adapter model IDs are respectively
`ai2apps.model.musetalk-cuda/{default,vae,whisper,detector,parser}`.
Video generation consumes template_video and driving_audio multipart references;
optional prepared regions are an internal Worker input. It returns MP4 with the
driving audio preserved. Public Host capability declarations still need validation.

Upstream model inference, automatic face preparation and fixture Host evidence
are retained in spark/MEDIA-INVENTORY.json. Separate snapshot activation and the
original BiSeNet checkpoint full-pipeline tests are queued independently. Those
results must pass before final installation acceptance; import tests are not
inference evidence.

The five META checkpoint specs are proposed immutable distributions, not proof
of Registry publication. All five are signed candidates with complete dual-source download verification;
Registry publication remains pending. Do not insert placeholder
published distribution IDs into a releasable manifest.

Before release: publish and verify dependencies, declare the actual Runtime
version/capabilities, finalize the development manifest with compatible Host version constraints
and real distribution bindings, audit, sign, install and run an actual
Host request plus cleanup. Follow docs/ai2apps-package-publication-runbook.md.

Development service.yaml now declares one callable video model and four internal
checkpoint components. It requires the new Host component model-type contract;
older Host builds cannot load it. No distribution_id is bound before publication.

Development manifest and external-checkpoint SBOM are prepared. Memory and scores
are estimates, not benchmark results. Contract validation uses an in-memory file
index; the standard builder owns the final release index. No signed build performed.
