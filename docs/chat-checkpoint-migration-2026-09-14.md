# 全部对话模型自有 checkpoint 迁移

状态：in_progress。七套 SSD-ready checkpoint distribution 与 Runtime 1.7.0 已发布；七个模型
Package 已完成首轮发布。匿名验收发现 GLM/Qwen Next/Ornith 0.1.1 的 AI2Apps Contract
最低版本误写；三个 0.1.2 修正版已发布并完成匿名公开制品核验。七个当前版本均可由
0.1.0 Contract 客户端解析，最终 Repository metadata 为 v153。

## 范围

自动从 service.yaml 的 conversation/work capability 枚举，排除仅将内部组件标成 llm 的语音/标点模型：

|模型|迁移方式|
|---|---|
|DS4.1F（新增）|原 FP4/FP8，六段专家 SSD-ready|
|DS4 Flash 原版、2bit|现有 expert-major 布局|
|GLM-5.3 Flash|现有 fused-v2 布局|
|Qwen3.8 Flash Next|现有 fused-v1，保留 Full/Cached|
|Qwen3.6 35B、Ornith 1.5 Vision|对应 Qwen3.6 运行时布局|
|Qwen3.8 27B NVFP4|原字节自有镜像|
|Qwen3.5 2B、0.8B|原字节自有镜像|
|CUDA Qwen2.5 0.5B、Qwen3-VL 2B|原字节自有镜像，保持 CUDA Runtime 兼容|

现有 11 个模型变体 / 10 个 Package，另加 DS4.1F。具体旧版本、revision、distribution 与状态见 `artifacts/chat-checkpoint-migration-20260914/inventory.json`。目标 repo/revision/distribution 未确定前为 null，不填入生产 Package。

## 本轮实现

- `scripts/inventory_chat_checkpoints.py`：只读生成完整迁移清单。
- `scripts/build_dsv41_ssd_checkpoint.py`：首个数据布局导出器。所有 0–39 层专家逐 tensor 比较原始 checkpoint 与输出 expert-major 数据；保留其余所有 tensor（包括尚未启用的 MTP），构建紧凑 safetensors/index；逐 tensor reread 哈希验证、外置 tensor 位置表、逐文件 SHA-256、完整状态 manifest。完成前仅存在 `.partial`，不覆盖旧目录。
- macOS 优先使用 APFS 独立 CoW 克隆现成专家文件；不使用 hardlink。克隆失败回退复制；普通 tensor 有界流式拷贝，不需要将数百 GB 模型放入内存。
- 首轮 4 项导出测试通过；pytest 退出时现有 Metal 初始化回调在沙箱内发出 no-device 信息，测试本身 exit 0。还未以这些单元测试代替真实 checkpoint 或推理验收。
- 已登记 `NXR-CHAT-SSD-CHECKPOINTS-20260914`，正式 Runtime 集成/Package 验收完成前保持 in_progress。

## 来源审计和剩余工作

DS4.1F 官方 HF revision：`dba1be0a40aa45a94ad051997016db3960a90277`。本地下载来自 MS。正在逐文件核对 HF 固定 revision，发现 `.gitattributes` 不同，必须如实保留差异；不能因此宣称两个原始仓库所有文件完全一致。

仍需完成：实际重排导出及推理对照、其余 MoE 导出器和 dense 镜像、自有 MS/HF 上传和签名 distribution、Runtime 正式加载/Worker/Full 适配、全部真实 Package 构建安装回归及按依赖顺序发布。

上传命名空间已向用户询问，尚未收到答复；不影响本地构建。Cookie 和既往单次发布授权未被复用。

## 2026-09-14 首批候选完成

- DS4.1F：`artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD`，510,320,301,243 bytes（含 manifest），96,085 tensors；所有 tensor payload 核对通过。元数据最终 manifest SHA-256：`6b4985ab33d963666bf1059bc591b9f3a7208e2a6c3cc247e047f2dd1bbf5711`。
- DS4.1F 原布局和新布局使用同一当前 MLX 源码，分别运行 5-token 短文本及 carrots 图像；每组 Prefill+3 Decode 共 4 logits，8/8 完整 logits 逐位一致。新布局 sampled footprint：文本 54.830 GB，图像 58.139 GB。图像测试按固定步数执行，EOS 后的 token 仅用于数值对照，不是产品停止策略验收。
- Qwen Next：`artifacts/chat-checkpoint-migration-20260914/Qwen3.8-Flash-Next-MLX-4bit-SSD`，111,602,366,814 bytes（含 manifest）；48 层专家全部逐 tensor 比较通过。元数据最终 manifest SHA-256：`ef3020c39ab358d6ad8a306744a3ed81bf663f0537b58843f2e09127f5975815`。
- Qwen Next 固定源 revision 全文件审计通过；DS4.1F 仅 `.gitattributes` 与 HF 不同，模型文件全部一致。自有候选添加独立格式说明 README、保留 README.upstream.md/LICENSE，并使用自己的 LFS 规则。
- 新增 `scripts/build_qwen_next_ssd_checkpoint.py`、`scripts/ssd_checkpoint_io.py`、`scripts/finalize_ssd_checkpoint_metadata.py`；后者只为未上传候选写部署说明并更新文件摘要，不是 Package/distribution 签名器。
- `omlx/cache/ssd_checkpoint.py` 提供原始 packed tensor 逐个读取接口，支持连续/跨专家 stride 映射、shape/范围与 metadata digest 检查；用于 Full 权重恢复的数据层，尚未接入完整 Full engine。安装仍须先验证签名 distribution。
- `experiments/dsv41_mlx/storage.py` / `model.py` 已适配 compact index 与原始 source index 的分离，用于上述实际新布局推理；没有把实验 loader 当成已经发布的 Runtime。
- 最终 8 项相关测试通过，日志 `export-tests.log`；正式模块导入触发 Metal 的测试已在 GPU 可访问环境重跑通过。
- 发现本地 `artifacts/glm5-3-flash-q4-expert-store` 是 split-v1，不是所需 fused-v2，后续必须生成/定位正确布局并验证，不能仅改文件名就上传。

尚未上传任何候选、发布 distribution、改 Package 版本或发布 Runtime。HF 目标命名空间未确认；现有其他模型仍 pending。Runtime/完整 Full-Cached engine、managed Worker、真实 Package 实装与多轮回归必须继续完成。

Qwen Next 正式 ExternalTensorReader 真实数据复核完成：首尾两层共18个原始 packed tensors 全部恢复后 SHA-256 与原始 tensor 一致；见 `qwen-full-reader.json`。这仍不是完整 Full 引擎启动/推理验收。


## 上传目标确认与权限检查

用户明确：HF 命名空间 `ai2apps`，MS 命名空间 `avdpro`。首批仓库名分别使用 `DeepSeek-V4.1-Flash-SSD` 和 `Qwen3.8-Flash-Next-MLX-4bit-SSD`。

当前 HF 登录 Avdpro，fine-grained token，whoami 未列出组织；对 `ai2apps/DeepSeek-V4.1-Flash-SSD` 创建请求返回403。MS whoami 为 ai2apps；对 `avdpro/DeepSeek-V4.1-Flash-SSD` 创建返回400 / E3021，服务端消息 `namespace is not valid`。重新只读查询未找到目标后复核了同一请求，没有切换命名空间。

未成功创建仓库或上传权重。上传阶段需要用户更新本机 Hub 登录/命名空间写权限；不在聊天或日志收集 token。候选与本地验证不受影响，其他实现仍保持未完成状态。收据：`artifacts/chat-checkpoint-migration-20260914/target-access-20260914.json`。


## 既有账号确认后的推进

用户接受 HF `Avdpro` / MS `ai2apps`，取代上一节未授权命名空间。四个 DS4.1F/Qwen Next SSD 仓库已创建，收据 `repositories-created.json`。双源上传由 `scripts/upload_ssd_checkpoint.py` 使用官方 SDK、精确 manifest 白名单及可恢复缓存执行；上传未完成，尚无可发布的固定 revision 或 distribution。

MS 默认模型卡错误继承 Apache-2.0；已通过官方 SDK 改为 `license: other`、`license_name: Qwen Community License 1.0`、`license_link: LICENSE`，页面已显示正确标签。HF Qwen 上传暂停后使用原缓存续传；仅 README 与 manifest 元数据改变，所有权重未变。新 Qwen manifest SHA256 为 `ae6243104e668a0b7d8286ae06312f1b6ec10451c2aa9ff864b991cf3811bc8c`，总大小111,602,367,120 bytes。

Qwen 标准加载 context 已接入 SSD external tensor：Full 恢复原 packed tensors 后继续原 sanitizer；Cached 构建固定大小空槽，由原生 direct loader 按 miss 填充。模型目录以外的 safetensors 不受该 context 影响，退出会恢复原 loader。Cached 要求 expert store 来自同一 checkpoint。10项导出和加载测试通过（`loader-tests.log`），真实 Cached smoke 已启动；Full 全模型、prepared view、managed Worker 和 Package 验收尚未完成。


## Qwen Full/Cached 真实短推理验收

本地 `.venv` 为 CPython3.13，现有 GLM/Qwen SSD native 扩展为3.11；首次 Cached smoke 在 Decode 因 native ABI 不匹配终止，随后改用已存在的 `packaging/_export/framework-mlx-base/bin/python` (3.11.10)，确认 `preadv_fused_experts` 可用，未改动既有 App 或系统环境。

原/新布局 × Full/Cached 四条路径，在33 tokens提示、4 tokens生成中均输出 `[1206,3418,3069,264]` / `To understand why a`。这是短 token parity，不等同全 logits、多轮或 managed Worker 验收。Cached 新布局实际 direct_load_calls=293；此次原/新加载5.927s/0.690s。Full 新布局加载44.992s、MLX峰值75.169GiB；Full无第二份专家 safetensors 落盘。并发上传/磁盘缓存影响读数，本轮不作正式TPS比较。首个SSD Full benchmark重复计入最终summary token，比较按generation_tokens裁切，collector已修复。收据 `qwen-layout-smoke-parity.json`。

GLM完整源权重181,709,451,790 bytes。已调用现有 `scripts/convert_glm5_expert_store.py` 构建 `glm5-fused-v2`，保留旧 split-v1；当前只是专家存储转换，待全payload核验及紧凑backbone封装，不是已发布checkpoint。


## GLM SSD checkpoint 构建

现有 fused-v2 转换器已成功生成第3–45层专家存储。配置中主模型 `num_hidden_layers=45`、`first_k_dense_replace=3`，第45层为额外MTP，SSD导出只外置3–44层，保留45层原张量到backbone。新增 `scripts/build_glm5_ssd_checkpoint.py`：从原索引核对完整tensor集合，验证每个fused gate/up/down段形状与原字节，重新打包非专家/MTP/视觉等backbone，输出完整file SHA256/external-map/source-tensor-SHA256并原子提交候选。构建进行中，不得提前标成verified或上传。两个专用测试通过，覆盖MTP专家保留和fused payload损坏拒绝，日志 `glm-export-tests.log`。


## 上传状态复查及 HF 模型卡修复

HF DS4.1F 已由 SDK 完成172文件提交，revision `02c63dd01e8400591638cc8eefdb352adf160968`，尚需远端逐文件校验。MS Qwen 已完成73文件，Failed=0，耗时6h52m，尚需固定revision及远端校验。MS DS4.1F约254GB/510.3GB，上传继续。

HF Qwen 111.6GB预上传完成，但 README 的 `license_name: Qwen Community License 1.0` 不符合HF要求的小写slug，导致最终13文件提交反复失败。已停止该重试进程，本地改为 `qwen-community-license-1.0`，正文保留许可证完整名称和原LICENSE；新manifest SHA256 `16e581ab7753e47a3393383ffbc38bf1882960dc88b6f05a0d4c94eae38d35a5`。MS仍为前一manifest版本，后续需同步两个元数据文件，权重无需改动。

续传两次被自动审批拒绝：认为原始用户HF ai2apps指令未被后续“继续”明确替换，要求明确确认HF Avdpro目的地；已记录为 blocked_approval，没有绕过。等待用户明确确认现行 HF Avdpro / MS ai2apps，其他正在运行的上传未停止。


## 用户明确确认目的地后恢复

用户明确确认“继续使用 HF Avdpro、MS ai2apps 上传”。审批阻塞解除，HF Qwen 已成功提交全部73文件，revision `a1de2bbd1727b3c46162a0f8bd426316e6f8dd37`，manifest SHA256 `16e581ab7753e47a3393383ffbc38bf1882960dc88b6f05a0d4c94eae38d35a5`。MS Qwen 仅同步README/manifest两个文件，原权重不变。HF DS和MS Qwen此前已完成，MS DS仍上传；SDK完成仍不代表签名distribution和Runtime/Package发布完成。


HF固定revision远端校验：Qwen73文件、DS172文件已全部核对（LFS服务端SHA256/size，非LFS下载原字节SHA256）。两个仓库均仅 `.gitattributes` 不一致，原因是HF自动追加tokenizer等LFS路径；其余文件摘要全部一致，无额外文件。详见 hf-qwen-remote-verification.json / hf-dsv41-remote-verification.json。发布前必须统一Hub属性文件与候选清单；目前不得标记完整distribution验收通过。MS Qwen README/manifest两文件同步已成功。


## 双源完整元数据验收完成

HF自动添加的LFS属性已保留并同步至MS，两个本地manifest已更新对应属性摘要；只提交元数据，模型张量未改变。两仓库均完成精确文件集合、size、SHA256对照，差异0。Qwen73文件/111,602,367,198 bytes，DS172文件/510,320,301,780 bytes。证据：qwen-dual-source-verification.json、dsv41-dual-source-verification.json；属于远端权威摘要校验，不是第二份完整下载。

固定版本：Qwen HF23c6ed09ef3ec9bec2f31039f0e23e94dfacd1b5 / MS ee79605dcf01e16e740cf5abcb67b1a16e3e6c92；DS HF efb7e03fd718ebbeb3e0d7e60ed037a920d8e441 / MS f06bb1c499bf38694d84f8b5f3e345a84b8e44d3。

已准备 `distribution-specs/qwen.json` 与 `distribution-specs/dsv41.json` 构建输入，均为未签名/未发布候选；DS新Package/model ID尚属候选命名，不能作为现有Registry发布项引用。未修改现有Package版本或weights.distribution_id。后续须确认既有Publisher/key上下文、通过标准构建器生成piece哈希与签名、完成Registry发布，再进入Runtime/Package升级。


## GLM 双源并行上传已启动

GLM 候选已完成全部114,160个tensor payload字节一致性校验；99文件共181,750,093,113 bytes，manifest SHA256 `1b2334f30bd0b52facbc7d09cad70e4cdb5840edfd5a5339ff1130f458c92852`。保留原MIT LICENSE和上游README，模型卡明确标记MIT；第45层MTP张量保留在backbone。

按用户明确确认的命名空间，已建立并启动 HF `Avdpro/GLM-5.3-Flash-MLX-4bit-MTP-SSD` 与 MS `ai2apps/GLM-5.3-Flash-MLX-4bit-MTP-SSD` 官方SDK并行上传，每源4 workers。状态/日志为 `hf-glm-upload.{json,log}`、`ms-glm-upload.{json,log}`。当前无已验证固定revision，不代表签名分发或Runtime/Package发布完成。

上传不会自动释放存储。旧GLM split专家库约160 GiB是迁移验收后的清理候选，需先验证新SSD布局的文本/视觉/MTP调用并检查现有消费者；原始HF snapshot也需确认无其他依赖。fused-v2中间库与最终SSD专家文件使用APFS clone，不能把二者逻辑大小重复计作可回收空间。本轮没有删除GLM数据。当前卷可用约1.1 TiB。其余DS4原版/2bit、Qwen3.6-35B、Ornith35B尚未生成并验收新SSD候选，不能直接上传旧专家库冒充完整checkpoint。

## 2026-09-17 GLM 上传收尾与完整候选复核

本地递归复核只发现三套具有 `ssd-checkpoint.json`、完整文件白名单和
`all_tensor_payloads_equal` 验证标记的可发布 SSD checkpoint：DS4.1F、Qwen Next
和 GLM。前两套此前已经完成双源逐文件验收；DS4 原版/2bit、Qwen3.6-35B 和
Ornith 35B 当前只有原模型或独立专家库，尚未形成可上传的完整 SSD checkpoint，
因此没有把这些中间目录上传成模型仓库。

GLM 的 181.75 GB 权重此前已在两端上传完成。本次发现唯一差异是 HF 自动扩展
`.gitattributes`；将该文件同步到本地冻结 manifest 和 ModelScope，并只重传
`.gitattributes` 与 `ssd-checkpoint.json`。最终 99 个文件、181,750,093,284 bytes
在两端的文件集合、大小与 SHA-256 全部一致，差异为零：

- HF：`Avdpro/GLM-5.3-Flash-MLX-4bit-MTP-SSD`，revision
  `f0afe58b4162d269b316a5913a202627d4472e34`；
- ModelScope：`ai2apps/GLM-5.3-Flash-MLX-4bit-MTP-SSD`，revision
  `d503648e76809c2f14eda4468e983238aeb4ac07`；
- manifest SHA-256：
  `fcbe05b970cd1b5c1272c700b929cad67b44ba7e6ccd72976992b814c79e03fe`；
- 验收收据：`artifacts/chat-checkpoint-migration-20260914/glm-dual-source-verification.json`。

至此，当前已构建完成的三套 SSD checkpoint 均已上传并通过 HF/ModelScope 双源
验收。该结论只覆盖 checkpoint 上传；Registry distribution、Runtime 与模型
Package 的发布仍按各自发布门禁执行。

## 2026-09-17 剩余三个模型族的 SSD checkpoint

按用户授权继续处理 DS4F、Qwen3.6 35B 和 Ornith 35B Vision。DS4F 同时存在原版
与 2bit 两个已发布 Package 变体，因此三个模型族实际生成四个 checkpoint 仓库。
新增导出器只读取 DMoE 的既有 DS4F 源工件，不修改兄弟 checkout；所有输出都写入
本仓库。每个候选都重新构建紧凑 backbone，并把全部 routed tensor 与现有极速
expert-major/fused store 逐字节核对。

已完成候选：

|候选|文件数|总字节|manifest SHA-256|
|---|---:|---:|---|
|DeepSeek-V4-Flash-SSD|121|159,635,168,296|`aacf2c20cb9e86af03b2e41414179e198cd193ff598871e4ca1bf762fae733d3`|
|DeepSeek-V4-Flash-2bit-DQ-SSD|76|96,531,568,414|`6ee2fd1f98820dbd697a930d0003716e38609437b12ff68c5bc6c9cb15aafcf1`|
|Qwen3.6-35B-A3B-4bit-SSD|63|20,429,602,610|`d6c9951eae834c732b3a1efd97daaab43a86e816f35bdbdf4472e3e249fd5ad2`|
|Ornith-1.5-35B-A3B-MLX-4bit-Vision-SSD|63|20,422,831,727|`199f99ee64ed1eb007200c715792ec55a9c6016ce94249396720ffb6082d480a`|

DS4F 原版源 tensor 使用 `I8/F8_E8M0` 描述 FP4 packed storage，运行时 store 以
等价 `U32/U8` 视图描述同一字节。导出器明确验证视图形状换算和完整 payload
相等，没有重新量化。2bit 使用 stacked affine tensor，Qwen3.6 使用既有 fused-v2，
Ornith 从其自身视觉 checkpoint 直接生成 fused-direct-v3；Ornith 的 BF16 vision
sidecar 保留在 checkpoint 内存常驻部分。

HF `Avdpro` 与 ModelScope `ai2apps` 的四组仓库已创建，八个官方 SDK 可恢复上传
任务已启动，每源 2 workers。启动收据为
`artifacts/chat-checkpoint-migration-20260914/remaining-ssd-upload-launch-20260917.json`。
上传完成前不得写入固定 revision 或标记双源验收通过。

## 2026-09-17 七套 SSD checkpoint 上传与 Runtime 1.7 收尾

后续四套候选均已完成 HF `Avdpro` / ModelScope `ai2apps` 上传和逐文件集合、大小、
SHA-256 验收，差异为零：

|checkpoint|文件/字节|HF revision|MS revision|manifest SHA-256|
|---|---:|---|---|---|
|DS4F 4bit|121 / 159,635,168,361|`8fab5a37c9eb2003abb9fd2bb3c74c071c13bca7`|`0bdefefeca58c807727f0ec334f8533007615050`|`cce6106fe13a1819596c78ba9b20243503dc7505f0c36557e6b346416e3b46fa`|
|DS4F 2bit|76 / 96,531,568,414|`19116161696aa83be5de1915df9f7dd5c6c23c48`|`1c3ceacb711d39c33b628d226935e448f6f8ac4e`|`6ee2fd1f98820dbd697a930d0003716e38609437b12ff68c5bc6c9cb15aafcf1`|
|Qwen3.6 35B|63 / 20,429,602,662|`c6b2081c394f6c1270b243eb77292e70769af341`|`76886e4ff28626ca5eeceab84583a9dadd63e85d`|`7c0f920d61bb94f715d8107c4efeff5c16bff4f92023c4f37035f5b3ffc93cb3`|
|Ornith 35B Vision|63 / 20,422,831,779|`114f31e6c416027b78488a4b8afa1e12c2156275`|`520901e3136a5f2e910fbb799109b04c80cef370`|`d12ae8003e0df4e08bde830426e6e38d732ced142a183463fe2b6074d567bf36`|

GLM 首次真实 Runtime 启动发现模型处理器需要 `processor_config.json`。导出器已补齐该
文件并更新 manifest，随后只增量同步元数据；最终为 100 文件、181,750,094,334 bytes，
HF revision `a4d3f3e489a12893e0056a5b9494cc76194a220a`，MS revision
`f928d2572dc6d5706d61d43acf27e613cc28320a`，manifest SHA-256
`612d7eac144e6af5f5fa5d3de3b07f6bdc2f5e2f8c04765bf3bad1112f7a684c`。
至此 DS4.1、Qwen Next、GLM、DS4 4bit/2bit、Qwen3.6 和 Ornith 七套 checkpoint
均完成双源验收；机器结果见各 `*-dual-source-verification.json`。

Runtime 1.7.0 已实现统一 SSD schema 校验、直接激活和全部七套真实加载路径。DS4.1
正式文本与视觉 engine 与冻结基线完整 logits 摘要一致，其余六套完成真实短推理；Qwen
Next Cached smoke 峰值为 54.014 GiB。Runtime 自带 CPython 3.11 原生扩展已验证
`copy_expert_slots` 六段 GPU copy。集中测试分别为 20 passed 与 77 passed；宿主 Python
3.13 缺少 cp313 原生扩展的单项环境限制，不影响打包 Runtime 的 cp311 验收。

Apple submission `19de5929-dbb1-486f-a471-8b3038ec8b8b` 已 Accepted；最终 stapled
DMG 为 375,944,358 bytes，SHA-256
`cf9a645e84c46711392b53d18855f86201fd32cca280dbd1f0c2d66b69748a32`。外层正式
Package 也已构建并通过签名、内嵌字节和全新临时安装验收：373,748,488 bytes，SHA-256
`b066700dcebec87012e93de01e6114db9f231b0a1c89642e97c50cd91a1ec3a7`。尚未提交
Registry；当前 Installation Cloud session 无 active user session，Cookie 授权按 1.7.0
精确 Package/version 另行执行。

## 2026-09-17 Runtime、distribution 与模型 Package 发布

Runtime 1.7.0、七套 SSD-ready checkpoint distribution 和七个模型 Package 已按依赖顺序
发布。模型首轮版本为 DS4 0.3.3、DS4 2bit 0.3.4、GLM 0.1.1、Qwen Next 0.1.1、
Qwen3.6 0.3.3、Ornith 0.1.1、DS4.1 0.1.0；Repository metadata 最终为 v150。

全新匿名客户端验收时，GLM/Qwen Next/Ornith 0.1.1 因
`compatibility.ai2apps >=0.1.1` 被当前 0.1.0 Contract 客户端正确拒绝。三个版本的公开签名和
摘要没有损坏，但不能安装。兼容范围已恢复到 `>=0.1.0 <2.0.0`，源码、Service、SBOM、
release lock、Discover 有界映射和测试同步升至 0.1.2。三个正式签名修正版已构建并完成
本地归档审计。随后使用三个精确版本的 AI2Apps-dev Cookie 授权发布，Repository metadata
依次推进到 v151/v152/v153；无 Cookie 的全新客户端逐个验证双签名、摘要、大小、本地归档
字节和 envelope JSON 全部一致。完整 ID、摘要和验证见
`docs/ai2apps-chat-ssd-model-packages-release-2026-09-17.md`。
