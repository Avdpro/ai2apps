# exomni MLX 移植

状态：开发源码，未发布，尚未注册可安装的 Model Service。完整验证与缺口见 [移植记录](../../docs/ai2apps-avatar-model-port-status.md)。

固定上游 commit 与模型 revision 见 `upstream-lock.json`。所有权重必须预先保存到本地；推理不自动下载。
从仓库根目录运行，使用支持 Metal 的 MLX 环境。以下 `$WEIGHTS` 是用户准备的本地权重根目录，`$PYTHON` 是该环境的 Python。

## Teacher 图像 + 音频视频

```sh
PYTHONPATH=packages/ai2apps-model-exomni-mlx/src "$PYTHON" -m exomni_mlx \
  --checkpoints "$WEIGHTS" --image portrait.png --audio speech.wav \
  --output result.mp4 --prompt 'A person speaking.'
```

需要 Runtime 已固定版本的 `mlx_audio` 与 `mlx_lm`。默认 512²、50 步、125 帧窗口。

目录：`wan13b/` 保存 Wan 1.3B DiT/config、`t5.safetensors`、`google/umt5-xxl/`；`omniavatar/model.safetensors`；`exomni/video_generator/teacher.safetensors`；`qwen-codec/` 完整 Qwen3-TTS-Tokenizer-12Hz 配置/权重；`flashhead/VAE_Wan/Wan2.1_VAE.safetensors`。

Thinker 和语音生成 API 在 `thinker.py`、`generator.py`、`codec.py`。额外需要 `exomni/` 的全部 5 个主模型 shard、config 与 tokenizer，以及 `qwen-tts/config.json`。官方缺少 tokenizer.json 时可用本地 `AutoTokenizer(..., local_files_only=True, trust_remote_code=False)` 导出。Thinker→16 码本与 codec 已单独测试；完整对话编排、视觉/语音输入未完成；`speaker.py` 已支持 24 kHz 参考音色编码并通过上游对齐。

Teacher 文本条件必须保留 512 个位置，末尾补零后再做 learned projection；直接裁掉补零会导致异常纹理。Teacher 为离线生成路径，未实现 Student/流式视频。

## 离线转换

原始 `.pth/.pt` 纯 tensor 字典通过仓库 `scripts/prepare_avatar_weights.py --input ... --output ...safetensors --source-revision <lock 中的 revision>` 转换；它使用 `weights_only=True` 并记录输入/输出 SHA-256。Torch 仅用于开发转换和参考测试。AVTR 的 TorchScript 不能套用此转换器。
