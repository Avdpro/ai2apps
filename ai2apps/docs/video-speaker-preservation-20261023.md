# App-Dev 指定说话人换声完整链路验收

日期：2026-10-23。仅配置固定App-Dev；AS/General Agent未增加业务特例。

## 模型配置

通过视频工坊「视频角色换声 → 安装并配置模型」原有ACPF完成配置。
计划 `prv_2cc22069098b40329d5e6345f632f239`，Quality档位，最终ready。
原Runtime 1.8.11、详细转写0.1.4、Demucs与其他权重复用；新增官方目录的
`ai2apps/model-seed-vc-v2-mlx` 0.1.0，模型
`ai2apps.model.seed-vc-v2-mlx/default`，原安装器负责验证Package、定位权重与启动验证。
没有手动写模型状态或复制其他实例数据，未发布任何Package或Desktop。

## 真实样例与问题复现

输入为本机制作的24.3秒/243帧视频，机器合成Samantha(A)和Daniel(B)交替对白，
左右声道分别有220Hz/330Hz连续背景音，参考声音为机器合成Karen。
不使用真人录音。A出现在2.00–7.64和16.60–22.24秒，B在8.64–15.60秒。
[生成脚本](evidence/video-speaker-preservation-20261023/create_fixture.py)及
[精确时间](evidence/video-speaker-preservation-20261023/fixture.json)。

- 分析Job `stjob_ca66c18356f647e1a157b40b85d21d5b` 返回真实speaker_0(A)两段、
  speaker_1(B)一段。以样例文本确认目标，不猜编号。
- 首次真实replace `stjob_df75ec670ae4424c95bf859d937aa6d5` 成功产出，但比对发现
  视频提取及分离入口的默认mono解码丢失立体声背景。片头背景相关性仅0.707，
  全片左右差分相关性仅0.010，不能算保留性验收通过。

## 修复范围

- 公共媒体codec新增明确的`channels=2`选项，默认mono保持旧调用兼容；长度限制、
  PCM写入与损坏包间隙补零按实际声道数计算。原路径仍由PyAV直接打开。
- 视频换声提取音轨、源分离入口显式保留stereo；转写/声音模型可按自己的声明使用mono。
- 混音不再对整段做峰值归一化，目标声音过响时只按可用余量调整替换轨，避免影响
  未选中说话人和背景。20ms目标窗口淡入淡出及原时间线保留。
- 修复位于codec与Studio owner媒体层；后台队列、确认、引用、结果发布均复用原实现。

## 修复后真实执行与量化结果

同一原视频和参考引用、新Invocation、明确确认speaker_0及声音使用权后，执行
`timbre_fast`（实际Seed-VC v2模型）：

- Job `stjob_a8c824fc57504055bbe20c895c8ef0d3`
- Studio Run `strun_02520eaf85a742d9835121db71327eb0`
- 共享Video Output artifact `art_2bf38951b0ab46e2872f9c49c5ce5773`
- Chat引用 `art_b1d8e2d6bf154b1cb6c29cd9f3a49424`
- MP4 516496字节；source/reference均为stat引用，未staging原文件。

| 检查项 | 实测 |
|---|---|
| 画面与时间戳 | 243帧逐帧像素SHA-256及时间戳完全一致 |
| 解码音轨长度 | 源和结果均24.32秒（含容器编码尾部） |
| 目标A两段 | 波形相关性0.0314 / 0.0182，确实发生转换 |
| 非目标B，9.0–15.2秒 | 相关性0.998768；SNR26.06dB；音量差−0.057dB |
| 片头/片尾背景 | 相关性0.999866 / 0.999997 |
| 全片立体声背景 | 左右声道差分相关性0.958810，声场未再坍缩为mono |

[数值证据](evidence/video-speaker-preservation-20261023/metrics.json)与
[比对脚本](evidence/video-speaker-preservation-20261023/verify_result.py)。背景及B的内容、
声道布局得到保留；音轨经分离/重采样和AAC编码，不能宣称逐样本无损或所有素材均有相同指标。
目标波形变化不等于主观音色相似度评测。

另用现有详细转写核验输出，Job `stjob_ae53e0884c634994b26237b9e9593303`。
三段台词与源分析的完整text字段完全一致：A两次、B一次，顺序正确。此项仅证明台词
未丢失，不将ASR当作声纹核验；B保留由上述分段波形比对支撑。
[源分析](evidence/video-speaker-preservation-20261023/source-analysis.json)与
[结果转写](evidence/video-speaker-preservation-20261023/output-transcription.json)。

## 回归及激活

- 103项codec/Studio Broker/视频本地化/媒体工作流定向测试通过。
- 强制AaAT边界门禁297项通过；共享Output/音频bridge 9项通过。
- 新增4项回归覆盖显式stereo与mono兼容、视频嵌套音轨、分离模型实际输入声道、
  过响目标不能改变其他角色及左右背景。
- 固定App-Dev经标准Helper在空闲时重启Local；最终端口60157，native标题一致。
  App/Helper的DevelopmentSourceRoot均为当前Git根，真实Local导入日志指向本checkout，
  served共享表单JS逐字节相同。Python热源生效，未重建App。
