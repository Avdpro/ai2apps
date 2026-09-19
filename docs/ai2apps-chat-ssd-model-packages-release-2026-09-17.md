# AI2Apps SSD 对话模型 Package 发布回执

日期：2026-09-17（Asia/Shanghai）

源码基线：`8ff6faf966d56ae92d21bf2d36d9512da5745784`，分支
`experiment/moe-cache`；发布工作区包含尚未提交的本轮 Package/Runtime 迁移改动。

## 已发布依赖

- `ai2apps/runtime-omlx 1.7.0`：published，submission
  `5553a51b-7cf2-48be-8d66-7e5466be7293`。
- 七套 SSD-ready checkpoint distribution 均已 published，并通过匿名签名 Index
  验证：DS4 4bit/2bit、GLM、Qwen Next、Qwen3.6、Ornith、DS4.1。
- Runtime 与模型 Package 均只引用已发布的固定 distribution；模型 Package 不包含
  checkpoint、expert store 或原生 Runtime 载荷。

## 2026-09-17 首轮模型 Package 发布

|Package|版本|submission|Repository metadata|SHA-256|字节|
|---|---:|---|---:|---|---:|
|`ai2apps/model-deepseek-v4-flash`|0.3.3|`f336f7a9-294d-4248-9a42-ab7596b3092e`|144|`decd23cf3b6ed6d02bf34008b25fedae0092d5cd91ed7e178d185fd4224a679a`|51,166|
|`ai2apps/model-deepseek-v4-flash-2bit`|0.3.4|`6a2fdf3d-67a4-42f6-8708-0c645c41f149`|145|`6639f6c8f14222ae31aebaa17f502f05e6625fee085fa0b58d4a4629825d1f4c`|51,357|
|`ai2apps/model-glm5-3-flash-4bit-mtp`|0.1.1|`94d7810c-52a1-4098-ac35-59917c5b32c4`|146|`7b6f955c3c599f3c0af6993b97aa220ba3f9791405874f9ad6c23210ef6b4cac`|129,072|
|`ai2apps/model-qwen38-flash-next-4bit`|0.1.1|`a2101fc5-3058-4867-a08a-561637d3b329`|147|`d8f30bee6c6ddc7a77245936fdf6816cc599053c6db0fd066262b87c755598cd`|477,065|
|`ai2apps/model-qwen36-35b`|0.3.3|`8b01ef25-907f-49dc-97ad-45eecab2af2f`|148|`f75d14a172db652c69e18ca045fd68729e089594069aab57545abe267718425a`|179,772|
|`ai2apps/model-ornith15-35b-a3b-4bit-vision`|0.1.1|`b8635594-8568-47f4-a4fc-bfe291a7cb57`|149|`12036687a5be9210955f5669e9fda1a605fa7c4aa8cdcc7f3e0b7330d6308ce6`|183,797|
|`ai2apps/model-deepseek-v41-flash`|0.1.0|`843094c3-6e4c-454e-a4d2-16dd2d7f761b`|150|`93bc2eccc2ce8de05159ff6a8563e7ae314abc0d6d7dc0071014c4a14184339f`|10,538|

全新匿名客户端读取 Repository metadata v150。DS4 4bit/2bit、Qwen3.6、DS4.1
已完成公开归档下载、Repository/Publisher 签名验证、本地最终归档逐字节一致和 envelope
JSON 一致性检查。

## 兼容性修正

匿名验收发现 GLM、Qwen Next、Ornith 0.1.1 的
`compatibility.ai2apps` 被误写为 `>=0.1.1 <2.0.0`。当前正式 Package Contract 版本仍为
0.1.0，因此客户端会在制品下载前拒绝这三个版本。错误不涉及 checkpoint、Runtime、模型
配置、Publisher 签名或归档摘要，但 0.1.1 不应作为可安装版本使用。

源码已恢复 `>=0.1.0 <2.0.0` 并提升为不可变修正版 0.1.2：

|Package|修正版|submission|Repository metadata|SHA-256|字节|
|---|---:|---|---:|---|---:|
|GLM-5.3 Flash 4-bit MTP|0.1.2|`ed1266b5-eb50-4adc-880c-f5d9bcea08cd`|151|`5a326ef1fa2c3be9e0d2d0bc1caeb1e49d55a031372d3f55e8125f98fcbd69e2`|129,095|
|Qwen3.8 Flash Next 4-bit|0.1.2|`80ca9578-e761-4889-87cb-69cd132caa4b`|152|`3c22edeff3cefb07b7a62d8a2e6ec964762c4d863528cafa1df707be008d1ec1`|477,702|
|Ornith 1.5 35B Vision|0.1.2|`bed97c3f-12c1-443f-9c5c-d150c1540d1d`|153|`2d889550e92be24fa03c4e9ea928e85b20ee03e43ee83b3a05f4c31bba87d206`|183,842|

三个修正版均使用原 Publisher/key。标准构建器启用
`--omit-model-install-catalog` 兼容当前 Cloud schema；源码仍保留有界 `modelInstall`，客户端
按精确版本映射补回。归档内没有 `modelInstall`、`runtimeMemoryBytes`、权重、原生库或 DMG。
本地 Publisher 签名、Package 身份、SHA-256、大小及 9/11/11 个归档成员均已复核。
三个修正版均已 published。全新匿名客户端读取 Repository metadata v153，逐个下载公开
归档并验证 Repository/Publisher 签名；三份公开归档均与本地最终归档字节一致，公开
envelope JSON 也与本地签名件一致。0.1.2 已成为三个 Package 的最新可安装版本。

## 验证

- 三个修正版 Package 专项测试：10 passed。
- Package Contract 与 checkpoint distribution policy：10 passed。
- Discover 有界兼容映射：24 passed。
- 发布范围 `git diff --check`：passed。
- 宿主 Python 3.13 在测试退出时报告无 Metal device；上述测试 exit 0，真实 Metal/Runtime
  1.7.0 模型 smoke 已在此前候选验收完成。

精确 0.1.2 Cookie 授权只用于上述三项标准发布，匿名核验开始前已经结束。AI2Apps-dev
Shell 因独占锁定 Cookie SQLite 被精确关闭；发布完成后已从固定
`apps/ai2apps-acefox/.build/AI2Apps-dev.app` 路径恢复，Helper/Local 未被终止。
