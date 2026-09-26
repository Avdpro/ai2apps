# AI2Apps oMLX Runtime 1.7.11 发布收据

状态：Cloud 已发布；Cloud、GitHub、ModelScope 三源均已激活，匿名多源完整下载与签名验证通过。

- Package：`ai2apps/runtime-omlx 1.7.11`
- 源码基线：`61da0fc6a87d4f743d312c8ae1987d1d1b7babb8` 加工作树修复；原1.7.10签名/JIT权限保留。
- Publisher：`229d6350-cd0e-408a-9905-41367385ae5c`
- Key：`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- 公钥指纹：`216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`
- Package SHA-256：`979f48ad9ac43a05b66904bac0b19901628795136ef73e007ae5f2892c8e7b85`
- Package字节：382394257
- Apple公证：`0a551cba-7a7d-44ce-ab63-5409a8d5b845`，Accepted；staple/Gatekeeper通过。
- DMG SHA-256：`c02ea93ed52692f18626af47a5cb42d86a41683348197c5dac46bb4dbfcc1ffe`

## 修复与验证

Worker的转写、详细转写、音频处理主file限制提高到1GiB；参考文件及其他操作仍100MiB。保留WAV、时长、声道和采样率验证。

70项相关回归通过。正式Package安装到隔离临时实例，Demucs 0.1.0依赖锁绑定本版本和摘要。真实managed Worker处理131424044字节、1369秒48kHz静音测试WAV，返回482984911字节ZIP，包含separation.json、vocals.wav、instrumental.wav，CRC验证通过。此测试验证长请求和真实引擎处理，不是用户整集音质评价。

首轮验收脚本预期无checkpoint返回503，但共享已验证权重缓存使引擎直接成功；脚本改为也校验成功ZIP后重跑通过。

未更新用户App-Dev安装状态；未在另一台Mac上验证。正式制品与安装收据在packages/ai2apps-runtime-omlx/dist/1.7.11/。

## 授权

用户明确授权本次Runtime1.7.11公证和Dev Cookie发布；Cookie仅通过标准脚本live路径在内存使用，不输出、不复制。发布结束后授权失效。

## 镜像预检与三源激活

GitHub不可变tag `package-runtime-omlx-v1.7.11`，完整SHA/size与首中尾Range(206)通过。
ModelScope不可变revision `d729d98bf7ad04c41f68d585b3990d05e77c93c8` 返回严格
`HTTP 200 + Content-Range`。2026-09-25 重新核对首、中、尾各65536字节，三个响应的
offset、total、`Content-Length`和本地正式制品字节均精确匹配。Cloud随后使用已经部署的
`package-single-range-v2`兼容策略完成完整预检：49次Range均记录为
`http-200-content-range`，完整SHA-256、382394257字节大小和46-piece manifest全部匹配。

使用用户针对本次Runtime1.7.11多源发布明确授权的Dev live会话，标准发布脚本先激活既有
GitHub Source，再登记、验证并激活ModelScope Source。管理员step-up自审按生产既有策略写入
审计；没有修改Cloud数据库、Release字节或Publisher签名。此次Cookie授权随三源发布完成而失效。

## 最终发布结果

- Cloud submission：`5f0cb427-5fc2-4c3a-9b19-705def130fbb`，`published`
- 初始 Repository metadata：192
- 匿名回读：`artifactExactBytes=true`、`envelopeExactJson=true`；Registry信任和Publisher签名通过。
- GitHub source：`src_e3d4dea1-685e-4f33-8be7-5afd11eda880`，`active`
- GitHub validation：`val_e266d55b-3633-4e5e-9576-cb1ac52a74bf`，`passed`；49个HTTP206请求，piece manifest匹配。
- Validation digest：`930f1784ae448e507d48043a8ea5a6e8044c2bfea472ca4d0e9eb55d1b77847a`
- GitHub激活结果：Source revision 3；Repository metadata 198；Snapshot digest
  `5973adc50f43bdea0225c0fac9af23f71d6652f2bce9cf25edee5626f4b6e28c`。
- ModelScope source：`src_faa74736-6b57-44f8-a376-1e4afd6c903e`，`active`
- ModelScope validation：`val_3f93f7b3-53fd-49fc-9aa0-421187cfb813`，`passed`。
- ModelScope validation digest：`061d4cefa4f2deabedeb0e96e71a2cd51deee5ae247300ff042a2add58905a1d`
- 最终 Source revision / ETag：6 / `"sources-6"`
- 最终 Repository metadata：199；Snapshot digest
  `96688078ab004a60c246948344efae23563ecd053e2fcd295c67c8ae365489f0`。
- 匿名签名Snapshot回读确认公开`artifact.sources`包含Cloud、GitHub、ModelScope三源。
- 全新匿名客户端从空缓存完成382394257字节下载、Repository签名、Package SHA-256和
  Publisher envelope验证，用时约12.8秒；`artifactExactBytes=true`、
  `envelopeExactJson=true`。

本次Package与三源分发发布均已完成，Dev Cookie授权结束。用户App-Dev仍需通过模型管理更新已安装Runtime到1.7.11；发布不等于已经替换该实例当前运行的Worker。
