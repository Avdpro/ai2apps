# 本地 TTS 音频校验

`audio-check` 使用显式本地 Qwen3-ASR checkpoint，启用 Hugging Face 离线模式，
不会自动下载模型、上传音频或修改共享 checkpoint。依赖运行环境的 mlx-audio、
numpy 和 soundfile。当前机器已具备这些依赖。

先取得本次 Test Chat 实际生成的音频并保存到当前 Run 内，再运行：

```sh
./bin/ai2apps-test audio-check --run RUN_ID --audio ABSOLUTE_RUN_AUDIO_PATH --checkpoint LOCAL_QWEN_ASR_DIRECTORY --expected-text '本次实际朗读的文本' --language Chinese
```

输出原音频 SHA-256、时长、采样率、声道、RMS、峰值、削波比例、独立转写和
文本对照。预期文本不传入识别模型。忽略标点、大小写及 Unicode 兼容字形后
一致为 content-matched；不一致为 needs-listening-review，不直接归因 TTS。
空音频拒绝，静音为 failed。结果保存为音频文件旁的 `.asr.json`，将返回的
evidence 列表加入 Case result，报告即可链接原音频与转写。不会自动把 Case 判为通过。

边界：文件内容校验不验证扬声器是否实际播放，也不验证音色、自然度或韵律。
不得重新调用 TTS 生成替代证据。

## Test 应用真实播放捕获

使用 macOS ScreenCaptureKit 的 application-only 过滤器，仅选择 Harness 校验的
当前 Test Shell 路径和进程。不接入麦克风，不保存屏幕画面，不回退全系统混音。
首次使用需要 Xcode Command Line Tools 编译 Swift 辅助程序，以及 macOS
“屏幕与系统音频录制”权限。授权实际启动工具的宿主应用；Helper 与终端的权限可能不同。

```sh
./bin/ai2apps-test audio-capture permission
./bin/ai2apps-test audio-capture start --run RUN_ID --case CASE_ID --seconds 120
# 返回 status=recording 后，才通过 Computer Use 点击 Test Chat 的朗读按钮。
./bin/ai2apps-test audio-capture status --run RUN_ID --capture CAPTURE_ID
# 确认播放完成后：
./bin/ai2apps-test audio-capture stop --run RUN_ID --capture CAPTURE_ID
./bin/ai2apps-test audio-check --run RUN_ID --audio ABSOLUTE_OUTPUT_WAV --expected-text '实际朗读文本'
```

省略 checkpoint 时，仅在 AI2Apps 共享 checkpoint 目录中选择本地最小 Qwen3-ASR
权重；可显式指定目录。不会下载或修改共享模型。只对当前 pending UI Case 录音，
每 Run 同时一条，最长 180 秒。Run 结束、Case 结束、目标退出或录音错误会停止录音。
超时或非正常停止标记 incomplete，不能当作完整音频进行内容验收；重启后需要重新录音。
缺权限、目标身份不唯一或录音未就绪时，不要开始播放，记录 blocked。

把 audio-check 返回的 WAV、ASR JSON、capture.json 全部加入 Case evidence；
HTML 报告提供音频回放。静音、空文件、ASR 不一致必须保留证据，不能自动报告通过。
数字读法、同义读法及 ASR 自身误识别需要复听判断。应用音频过滤不等于证明实际
扬声器发声，也不能自动判断音色、自然度或韵律。真实 Chat TTS 端到端验收仍须在
登录有效、TTS 配置可用的 Test 实例中运行；编译和权限检查不替代该验收。
