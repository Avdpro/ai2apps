# musetalk MLX 移植

状态：开发源码，未发布，尚未注册可安装的 Model Service。完整验证与缺口见 [移植记录](../../docs/ai2apps-avatar-model-port-status.md)。

固定上游 commit 与模型 revision 见 `upstream-lock.json`。所有权重必须预先保存到本地；推理不自动下载。
从仓库根目录运行，使用支持 Metal 的 MLX 环境。以下 `$WEIGHTS` 是用户准备的本地权重根目录，`$PYTHON` 是该环境的 Python。

## 运行

```sh
PYTHONPATH=packages/ai2apps-model-musetalk-mlx/src "$PYTHON" -m musetalk_mlx \
  --weights "$WEIGHTS/musetalk-q4" --template template-25fps.mp4 \
  --audio speech.wav --regions regions.json --output result.mp4
```

权重采用锁定社区 MuseTalk-1.5-q4 文件结构。`regions.json` 为与模板帧数一致的列表，每项格式 `{"box":[x0,y0,x1,y1],"mask":"masks/0001.png"}`；mask 为 256² 灰度 alpha，路径相对 JSON。框与分割遮罩必须预先准备，自动检测/分割尚未移植。模板须为 25 FPS，音频较长时循环模板。

## 离线转换

原始 `.pth/.pt` 纯 tensor 字典通过仓库 `scripts/prepare_avatar_weights.py --input ... --output ...safetensors --source-revision <lock 中的 revision>` 转换；它使用 `weights_only=True` 并记录输入/输出 SHA-256。Torch 仅用于开发转换和参考测试。AVTR 的 TorchScript 不能套用此转换器。
