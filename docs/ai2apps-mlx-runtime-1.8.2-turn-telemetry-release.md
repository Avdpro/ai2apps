# AI2Apps oMLX Runtime 1.8.2 整轮遥测发布收据

状态：`ai2apps/runtime-omlx 1.8.2` 已正式发布。Developer ID 签名、Apple 公证、
staple、Gatekeeper、隔离安装、Cloud 发布、GitHub/ModelScope 三源激活和匿名 Registry
回读均通过。模型 Package 与 checkpoint 没有变化。

## 变更

Runtime 在既有最近 10 个 Decode token SSD pressure 之外，新增按 Chat Session 隔离的
`ssd_turn_by_session`。它从 Decode 起点累计本轮专家加载次数和 SSD 读取字节，并以本轮
token 数乘模型理论路由专家字节为分母计算整轮 pressure 与健康等级。Chunked Prefill
期间会刷新基线，因此 Prefill 读取不会混入 Decode 整轮平均。

Host 只投影这一受限遥测结构；Chat 在生成中继续显示最近 10 token，完成后显示整轮平均。
Worker 内存则在请求期间采样 RSS，结束后显示与对应 Worker service key 绑定的峰值。统计
复用已有 loader counters 和既有状态边界，没有增加 Decode 期间的 Metal readback 或
GPU→CPU 同步。

## 正式制品

- 源码基线：`de405d2371d61f85fda19da583b5d9fa1000849a` 上的 working tree。
- Apple 公证 submission：`383188a0-ded6-4842-ae28-748d72bcc909`，状态
  `Accepted`；staple、`stapler validate` 与 Gatekeeper 通过。
- DMG：387,386,570 bytes，SHA-256
  `c462b1225b0bb426e5ba52ab2481a89121503dc7e7c192180bf3228409c2ed21`。
- Package：384,698,906 bytes，SHA-256
  `9e2cdf344a3fe1d7152540a321d1947feca89a2b381d4920838a4f6baf495544`。
- Publisher：`229d6350-cd0e-408a-9905-41367385ae5c`；key
  `8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`。
- Cloud submission：`717062a6-7216-4033-af49-e5d711f17dcc`；review
  `83ae4662-2b02-4722-8e7e-0a949b76f4a0`；状态 `published`。

## 三源发布

- Cloud Source 保持 active。
- GitHub tag：`package-runtime-omlx-v1.8.2`；Source
  `src_a34467ad-57b0-45e8-bbac-533aee877993`；validation
  `val_2ea00d4a-4082-4126-8936-911ef8f6a8f8`；digest
  `009120aa3ccb5ab4add1cf58ce5daa5e1a060393c2b3ae1aed834781b64bf5cc`。
- ModelScope immutable revision：`3a27d806e1ccafb52c040696065db5787706e892`；
  Source `src_afce68de-e18c-475a-9c6c-3a040df2ab6a`；validation
  `val_df1c479a-3e41-40b7-a877-f0cbc0f22c2c`；digest
  `55c3fcfad3c518fac27c6e8856d9184c3be5ea83219394efbd47fd12686c5fac`。
- 两个外部源分别完成匿名完整下载，长度、SHA-256 和原始字节均与正式 Package 一致。
  首段、中段、尾段和单字节 Range 也逐字节匹配。GitHub 返回标准 HTTP 206；
  ModelScope 返回已支持的 HTTP 200 加精确 `Content-Range`。
- Cloud 对每个外部源重复验证完整 SHA-256、46-piece manifest 和 49 次 Range 请求。
  最终 Source revision / ETag 为 6 / `"sources-6"`；Repository metadata 为 218；
  Snapshot digest 为
  `c131c0dc4d157f002f80870026c238d5920a38d141034c7beb81198066e02aef`。
- 匿名 Registry 回读确认正式 Package 字节和 Publisher envelope 均与本地签名制品精确
  一致。

## 验证

- 整轮 SSD 数学回归以及 Runtime、Worker、Package、Product、Chat 与 Engine Pool 定向
  回归共 254 项通过。
- 正式签名 Package 在独立 Platform 根目录安装成功；CPython 3.11.10、MLX 0.32.0、
  Metal 和原生 `preadv_fused_experts` 通过。已安装代码包含
  `ssd_turn_by_session`。
- DeepSeek V4.1 0.1.0 Worker 在隔离环境中启动为 `running`，依赖锁精确指向 Runtime
  1.8.2 的上述 SHA-256。
- `git diff --check` 与 CPython 3.11 `compileall` 通过。

本轮验证覆盖统计数学、Runtime 制品、依赖解析和 Worker 启动，没有重复下载 475 GB
checkpoint 或执行新的真实生成吞吐测试，因此不据此改变既有 TPS 结论。
