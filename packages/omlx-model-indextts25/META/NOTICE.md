# Notices

This Package uses IndexTTS 2.5 model weights from IndexTeam under the Bilibili
Model Use License Agreement and a Torch-free MLX inference implementation
derived from WIndexTTS commit
`eafb98c1b2ba46f6a608f29d8831208b89047681` under Apache License 2.0.

- Model: https://huggingface.co/IndexTeam/IndexTTS-2.5
- Official implementation: https://github.com/index-tts/index-tts
- MLX implementation: https://github.com/baicai-1145/WIndexTTS

AI2Apps converts the fixed upstream weights to FP16 safetensors, removes
training state and the optional Qwen text-emotion model, retains the model and
implementation licenses, and adds offline checkpoint validation plus unified
structured speech controls. This modified checkpoint and Package are not
endorsed by Bilibili or the upstream authors.
