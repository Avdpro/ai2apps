# infinitetalk MLX 移植

状态：开发源码，未发布，尚未注册可安装的 Model Service。完整验证与缺口见 [移植记录](../../docs/ai2apps-avatar-model-port-status.md)。

固定上游 commit 与模型 revision 见 `upstream-lock.json`。所有权重必须预先保存到本地；推理不自动下载。
从仓库根目录运行，使用支持 Metal 的 MLX 环境。以下 `$WEIGHTS` 是用户准备的本地权重根目录，`$PYTHON` 是该环境的 Python。

## 运行单人模型

```sh
PYTHONPATH=packages/ai2apps-model-infinitetalk-mlx/src "$PYTHON" -m infinitetalk_mlx \
  --checkpoints "$WEIGHTS" --image portrait.png --audio speech-16k.wav \
  --output result.mp4 --prompt 'A person speaking.'
```

默认 480²、40 步、81 帧窗口、25 帧重叠。真实样例已验证的是 256²、9 帧窗口、5 帧重叠的诊断配置；默认长窗口尚未验收。

目录：`wan14b/` 保存 Wan2.1-I2V-14B-480P 配置、全部 7 个 DiT shard 和 `clip.safetensors`；`wan13b/t5.safetensors` 与 `wan13b/google/umt5-xxl/`；`flashhead/VAE_Wan/Wan2.1_VAE.safetensors`；`chinese-wav2vec2/`；`infinitetalk/single/infinitetalk.safetensors`。具体来源以 lock 为准。

双人注意力已数值对齐，真实双人权重与分区遮罩尚未验收。不得把单人测试结果标成双人可用。

## 离线转换

原始 `.pth/.pt` 纯 tensor 字典通过仓库 `scripts/prepare_avatar_weights.py --input ... --output ...safetensors --source-revision <lock 中的 revision>` 转换；它使用 `weights_only=True` 并记录输入/输出 SHA-256。Torch 仅用于开发转换和参考测试。AVTR 的 TorchScript 不能套用此转换器。
