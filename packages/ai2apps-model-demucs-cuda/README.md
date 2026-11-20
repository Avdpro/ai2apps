# Demucs CUDA — development source

Three shared pipeline profiles: music_4stem, vocals_instrumental, and
dialogue_background. Dialogue is approximated by the vocals stem; it is not
a dedicated speech separator. Native outputs use the fixed HTDemucs FP32
checkpoint and retain the input timeline, with ZIP stem delivery.

CUDA backend and safe tensor mapping come from spark/demucs_cuda_backend.py
and spark/demucs_safe_weights.py. The shared media modules retain their
upstream notices. Fixed checkpoint bytes are not included here.

The signed CUDA distribution candidate is not yet published; distribution_id
is intentionally absent. Requires released Runtime >=0.6.0 and formal signed
installation acceptance. Existing development inference evidence does not
establish music-semantic quality or complete lifecycle acceptance.
