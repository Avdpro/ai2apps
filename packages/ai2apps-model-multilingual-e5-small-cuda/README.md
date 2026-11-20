# Multilingual E5 Small CUDA — development source

Official FP32 encoder, eager attention, masked mean pooling and L2-normalized
384-dimensional embeddings. Inputs use explicit query/passage prefixes, with
512-token truncation and up to 256 texts per call (16-text native microbatches).
This is a knowledge embedding model, not a conversational model.

The Runtime owns cuda_e5_engine.py and its fixed official-inputs inventory.
This Package provides the Host/Worker adapter and Linux dependency declaration.
The original intfloat checkpoint distribution is published and anonymously
verified in Registry Index 126; the Service now binds its exact distribution ID.
The Mac converted MLX checkpoint is not interchangeable. A released Runtime
>=0.6.0, signed installation and live Knowledge configuration remain release gates.
