# AI2Apps oMLX Runtime 1.8.5 MoE 遥测与内存口径发布收据

状态：`ai2apps/runtime-omlx 1.8.5` 已正式发布。Developer ID 签名、Apple 公证、
staple、Gatekeeper、精确签名 Package 隔离安装、Cloud 发布、GitHub/ModelScope 三源
激活和匿名 Registry 回读均通过。模型 Package 与 checkpoint 没有变化。

## 变更

Runtime 1.8.5 将 rolling 10-token 与 whole-turn SSD pressure 的实时 SSE 数据补齐到全部
已发布 Cached-MoE 对话引擎：DeepSeek V4/V4 2-bit、DeepSeek V4.1、GLM-5.3、Qwen3.6
文本版、Ornith 1.5 Vision 和 Qwen3.8 Flash Next。共享 telemetry helper 只采样既有缓存
计数，并复用各引擎已有的 Decode 完成边界；原 Boost/adaptive callback 继续在同一边界
执行，没有增加 MLX 求值、Metal readback 或 GPU→CPU 同步。全驻留模型继续明确返回无
SSD pressure 样本。

Host 同时导出 RSS 和 macOS `phys_footprint`。Chat 当前值与整轮峰值优先显示 physical
footprint，并在系统调用不可用时回退 RSS。真实 DeepSeek V4.1 短推理测得峰值 RSS
43.4923 GiB、physical footprint 51.6140 GiB，差值 8.1218 GiB；这解释了旧 UI 对
Metal/IOAccelerator 统一内存的低报。Host/UI 展示属于下一版 Desktop/App 源码，安装本
Runtime 不会单独改变旧 Desktop 的内存卡片。

## 正式制品

- 源码基线：`de405d2371d61f85fda19da583b5d9fa1000849a` 上的 working tree。
- Apple 公证 submission：`966aa354-afd5-4f59-9b4f-1abc51667d11`，状态 `Accepted`；
  staple、`stapler validate` 与 Gatekeeper 通过。
- DMG：387,385,482 bytes，SHA-256
  `3763f666663abf31ebd686cc831092739216af28fd5d6a2539dc79c18caa4d11`。
- Package：384,686,288 bytes，SHA-256
  `56997274091b7c7df8d7823c26767c7111eb53539ff400e361220b0f0fec7c97`。
- Publisher：`229d6350-cd0e-408a-9905-41367385ae5c`；key
  `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`。
- Cloud submission：`bc7414ec-5cea-4854-aea2-98da196138da`；review
  `788a9624-701c-4c68-94a4-462de307be08`；状态 `published`。

## 三源发布

- Cloud Source 保持 active。
- GitHub tag：`package-runtime-omlx-v1.8.5`；Source
  `src_8a361644-d5c9-4dba-883c-6d2c64de8b13`；validation
  `val_e6e19c2b-8014-4665-bb4e-99d78cbd2829`；digest
  `01c83d4536efe2cac30828d7c28e0a1cf4949700bdb325321982a5a2a7a3b1fe`。
- ModelScope immutable revision：`1a5b1e1b3aa0d50ad619f659b655302bb0884158`；tag
  `package-runtime-omlx-v1.8.5`；Source
  `src_2d4e9767-1e6d-4193-bb2f-7eb6a08454d0`；validation
  `val_3d8f6c51-18f4-4791-903c-ead3e7421e78`；digest
  `0f41c9d6018fdf867e34c8425366c05bcf09b45144657e92a56c797ccad8f71c`。
- 两个外部源均完成匿名完整回读，长度、SHA-256 和原始字节与正式 Package 一致；首、
  中、尾 Range 逐字节匹配。GitHub 使用标准 HTTP 206，ModelScope 使用兼容的 HTTP
  200 加精确 `Content-Range`。
- Cloud 对两个外部源分别校验完整 SHA-256、46-piece manifest 和 49 次 Range 请求。
  最终 Source revision / ETag 为 6 / `"sources-6"`；Repository metadata 为 224；
  Snapshot digest 为
  `3a07275ea889a89005f9c9610e1c522686fe9e95842508abd37dfbb88c3f2d0b`。
- 无用户会话的公开 Registry 回读确认正式 Package 字节和 Publisher envelope 与本地
  签名制品精确一致。

## 验证

- 共享 telemetry 和四个新增引擎接线：9 passed。
- Runtime、Worker、Package、Engine、Adapter 与 Chat 联合定向套件：237 passed。
- Desktop Product、Shell、Package 和 Chat UI 收口套件：198 passed。
- Ruff、CPython `compileall` 与 `git diff --check` 通过。
- 正式签名 Package 在独立 Platform 根目录安装成功；CPython 3.11.10、MLX 0.32.0、
  Metal 和原生 `preadv_fused_experts` 通过。DeepSeek V4.1 0.1.1 Worker 启动为
  `running`，依赖锁精确指向 Runtime 1.8.5 的上述摘要。
- 真实 DeepSeek V4.1 短推理的完整 Decode 步读取 83 个专家、1,560,453,120 bytes，
  pressure 34.583333%，recent 与 turn window 一致，推理正常结束。

本轮没有重复下载并执行 GLM、Qwen3.6/Ornith 和 Qwen3.8 Next 的大型 checkpoint；这些
后端通过真实缓存接口形状、callback 保留、SSE 合同和正式 Runtime 内容检查验收。因此
不据本次发布改变既有模型质量或 TPS 结论。
