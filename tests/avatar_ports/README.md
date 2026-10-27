# 数字人模型参考测试

这些脚本是显式运行的 Metal/上游参考测试，不加入普通 Host 单元测试自动收集。

从仓库根目录运行；不要从 `ai2apps/` 运行 Python（目录名会遮蔽标准库模块）。

```sh
export AI2APPS_AVATAR_UPSTREAM=/absolute/path/to/pinned-upstream-checkouts
export AI2APPS_AVATAR_CHECKPOINTS=/absolute/path/to/local-checkpoints
export MLX_ENABLE_TF32=0
.venv/bin/python tests/avatar_ports/flashhead_parity.py
.venv/bin/python tests/avatar_ports/ltx_parity.py
.venv/bin/python tests/avatar_ports/wan_vae_parity.py
.venv/bin/python tests/avatar_ports/flashhead_media_contract.py
.venv/bin/python tests/avatar_ports/musetalk_checkpoint.py
.venv/bin/python tests/avatar_ports/grid_sample_parity.py
.venv/bin/python tests/avatar_ports/infinitetalk_parity.py
.venv/bin/python tests/avatar_ports/exomni_parity.py
.venv/bin/python tests/avatar_ports/exomni_speech_parity.py
.venv/bin/python tests/avatar_ports/talker_parity.py
```

上游文件夹为 `flashhead`、`musetalk`、`avtr`、`infinitetalk`、`exomni`、`mlx-audio`，版本见 Package 的 `upstream-lock.json`。bootstrap 会拒绝版本不符的现有 checkout。

权重目录：`flashhead/Model_Lite`、`flashhead/Model_Pro`、`flashhead/VAE_LTX`、`flashhead/VAE_Wan`、`wav2vec2`、`musetalk-q4`、`wan14b`、`infinitetalk/single`。
`.pth/.pt` 须先离线安全转换为对应 `.safetensors`，不在推理时自动导入 Torch。

`flashhead_checkpoint.py` 和 `infinitetalk_checkpoint.py` 会加载完整模型，并用小潜变量诊断严格映射与有限值；它们不是画质或 FPS 基准。
上游对齐脚本仅抽取实际类体，替换 CUDA attention 调用为等价 CPU SDPA；不是另写一个期望结果的模拟器。Torch、einops 仅是参考测试依赖。

## 额外回归

```sh
.venv/bin/python tests/avatar_ports/exomni_text_condition.py
.venv/bin/python tests/avatar_ports/exomni_speaker_parity.py
"$NATIVE_PYTHON" tests/avatar_ports/exomni_checkpoint.py
"$NATIVE_PYTHON" tests/avatar_ports/exomni_codec_checkpoint.py
```

`NATIVE_PYTHON` 必须来自未安装 Torch 的 MLX 环境；checkpoint 脚本显式检查未导入 Torch。同样设置上面的两个权重/源码环境变量，并安装或提供 Runtime 固定的 mlx-audio。相关脚本写出的诊断码本保存在用户指定的检查点测试目录。

Ex-Omni 需要 `exomni/`、`qwen-tts/`、`qwen-codec/`、`wan13b/`、`omniavatar/`；InfiniteTalk 还需要 `chinese-wav2vec2/`。详细文件布局、正式采样参数与 CLI 见各 Package README。测试网络缩小或短片生成通过，不代表长视频/画质全部通过。
