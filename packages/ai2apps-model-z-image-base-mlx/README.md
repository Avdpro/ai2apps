# Z-Image Base MLX (development)

Independent undistilled Tongyi-MAI/Z-Image Package. Turbo remains unchanged.

Defaults: 30 steps, CFG 4, Q8, 1024x1024; supports negative_prompt through the image generation API. Uses native mflux ModelConfig.z_image() (not Turbo and no Turbo-specific fused RMS monkeypatch).

Only image_generation is exposed. This is NOT Z-Image-Edit. Imagine Studio must not send Turbo's 8-step controls to this model.

Pinned HF revision: 04cc4abb7c5069926f75c9bfde9ef43d49423021.

## Release gates still open

Real native Runtime generation passed: Q8, 1024², 30 steps, CFG 4, seed 42; 166.278s including cold setup, Metal peak 17,950,257,918 bytes on M5 Max 128 GiB. The 17 selected official HF/MS files match SHA-256 (20,538,488,386 bytes). Package and Imagine Studio regression: 19 passed. Source lock and SBOM are included.

No production publication or installed-model acceptance is claimed. Before signing: publish and verify the Checkpoint Distribution, add its distribution_id, and test a signed installation under Managed Service Sandbox and Imagine Studio. Installation authentication currently requires user administrator verification and explicit browser Cookie authorization for this Package/checkpoint publication. The 32 GiB admission floor is estimated headroom, not a measured minimum. No fake published distribution ID is supplied.

Source: https://huggingface.co/Tongyi-MAI/Z-Image
