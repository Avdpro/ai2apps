# FlashHead Lite / Pro MLX 模型 Package

状态：0.1.0 发布候选，双源权重已上传；Registry Distribution 已正式发布，签名 Package 和安装 Sandbox 验收进行中。

一个模型 Package 提供 Lite / Pro，Lite 推荐。仅包含 Python 模型实现与 Worker Adapter，复用共享 oMLX Runtime；Host 下载权重，推理不联网。

## Worker 输入输出

- PNG / JPEG / WebP 图片 + 16 kHz 单声道 WAV。
- 固定 512×512、25 FPS、4 步，输出 H.264 / AAC MP4。
- Lite 最长 60 秒，Pro 最长 10 秒；支持取消、串行生成。
- 接收 Host 视频队列的 `reference_parts`，由 Host 选择 checkpoint。

## Runtime 实测

Apple M5 Max 128 GiB，Python 3.11.10 / MLX 0.32.0，`MLX_ENABLE_TF32=0`，未导入 Torch。

| 模型 | 视频 | 总耗时 | MLX 峰值分配 |
| --- | --- | --- | --- |
| Lite | 60 秒 / 1500 帧 | 99.71 秒 | 8.53 GiB |
| Pro | 10 秒 / 250 帧 | 132.59 秒 | 10.53 GiB |

耗时包含加载、生成、编码及输出校验。MLX 峰值不等于整个进程内存；此次为单图片功能验收，尚未完成跨人物质量评估。16 项 Worker/Package 定向测试通过。

`service.yaml` 与 `ai2apps.json` 已绑定真实发布的 Distribution；META 内保留发布准备阶段的候选声明。固定双源 revision 见 `META/checkpoint-distribution-{lite,pro}.json`。完整移植说明见 [移植记录](../../docs/ai2apps-avatar-model-port-status.md)。

固定上游 commit 与模型 revision 见 `upstream-lock.json`。所有权重必须预先保存到本地；推理不自动下载。
从仓库根目录运行，使用支持 Metal 的 MLX 环境。以下 `$WEIGHTS` 是用户准备的本地权重根目录，`$PYTHON` 是该环境的 Python。

## 运行

```sh
PYTHONPATH=packages/ai2apps-model-flashhead-mlx/src "$PYTHON" -m flashhead_mlx \
  --weights "$WEIGHTS/flashhead" --wav2vec "$WEIGHTS/wav2vec2" \
  --variant lite --image portrait.png --audio speech-16k.wav --output result.mp4
```

Pro 使用 `--variant pro`。默认 512²、4 步。Lite 使用 LTX VAE，9 帧重叠；Pro 使用 Wan VAE，5 帧重叠，均固定 33 帧分块。

权重目录：`Model_Lite/`、`Model_Pro/`、`VAE_LTX/` 保留配置和 safetensors；`VAE_Wan/Wan2.1_VAE.safetensors` 由官方 pth 离线转换。Wav2Vec2 目录使用固定的 facebook/wav2vec2-base-960h 配置和权重。

## 离线转换

原始 `.pth/.pt` 纯 tensor 字典通过仓库 `scripts/prepare_avatar_weights.py --input ... --output ...safetensors --source-revision <lock 中的 revision>` 转换；它使用 `weights_only=True` 并记录输入/输出 SHA-256。Torch 仅用于开发转换和参考测试。AVTR 的 TorchScript 不能套用此转换器。
