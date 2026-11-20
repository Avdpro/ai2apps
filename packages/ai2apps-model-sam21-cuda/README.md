# SAM 2.1 Video Cutout CUDA — development source

Uses original Meta SAM2.1 Hiera Small and the shared point/mask output contract.
The fixed official .pt is SHA-verified before weights_only=True CPU loading;
519 tensors match the previously tested safe conversion exactly and pass the
official model strict loader. HF Transformers model.safetensors is a different
representation and must not be substituted.

Both official origins are pinned in META/checkpoint-distribution.json. The
distribution is published and independently verified; service.yaml binds its exact ID.
No checkpoint bytes are bundled. CUDA inference from original-file delivery,
Host workflow and formal signed installation remain pending.

2026-10-09: The original official checkpoint distribution is now published and
anonymously verified in Registry Index 126. service.yaml binds the verified ID;
signed Service installation and original-PT GPU acceptance remain pending.
