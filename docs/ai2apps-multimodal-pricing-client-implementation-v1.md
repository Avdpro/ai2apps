# AI2Apps Local 多模态计价客户端实现 V1

状态：已实现，待定向测试与双帐号生产验收

日期：2026-09-02

Cloud 合同：`ai2apps-cloud/docs/multimodal-compute-pricing-client-integration-v1.md`

## 已实现

- Buyer 使用 `POST /v1/compute/quotes` 获取 Cloud 权威报价；金额全程使用十进制整数字符串；
- 新请求使用 `ai2apps.compute.request.multimodal-pricing.v1`，摘要域固定为
  `ai2apps.compute.request.v1\0`；
- P2P Model Share protocol v3 独立传输 `requestPayload`，Provider 在调用 Worker 前重算
  RFC 8785 摘要，防止签名 Manifest 与实际执行输入脱节；
- Provider 校验 Contract 冻结的 `calculatorType`、`pricingInput`、`boundedUsage` 和
  `maximumChargeMinor`，未知计算器拒绝执行；
- Result 使用 `ai2apps.compute.result.multimodal-pricing.v1`，摘要域固定为
  `ai2apps.compute.result.v1\0`；
- Provider 向 Cloud 同时提交 `actualUsage`、`resultManifest` 和 Ed25519 Commitment；
- Buyer 校验产物字节摘要、实际用量与 Result Manifest 后才提交 Delivery Receipt；
- TTS 从最终 WAV 的 frame count/sample rate 计算 `outputDurationMs`；
- 图片与视频提供最终产物计量器：图片解析真实头部尺寸，视频使用 `ffprobe` 读取最终可播放轨道；
- 本地作业账本记录计算器、最多预锁定、实际用量、最终扣费和释放金额；Dashboard 展示最近交易；
- 旧 `legacy_units_v1` 文本和 Audio TTS v2 路径继续保留。

## 当前运行适配范围

Model Share protocol v3、Quote/Request/Result、媒体计量与结算结构覆盖 `tts_v1`、`image_v1`
和 `video_v1`。当前可直接执行的 Provider Adapter 是已有、已审核的 TTS Package；图片和视频的
最终产物计量器及通用 v3 Artifact 传输已具备，但只有在相应 Package 的远程输入字段合同冻结后才会
加入可分享模型列表，避免把各模型私有参数误当成平台公共 API。

## 测试门槛

1. 静态编译与定向单元测试；
2. 临时数据库从 v68 升级到 v69；
3. 两个 Test 帐号执行 Quote → Hold → TTS → Result → Receipt；
4. 对照 Cloud Contract 的 `maximumChargeMinor`、`actualUsage.outputDurationMs`、
   `chargedMinor` 与 Hold Release；
5. Dashboard 确认“最多预锁定”不会显示成最终价格。
