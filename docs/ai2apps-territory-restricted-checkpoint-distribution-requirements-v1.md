# AI2Apps 地域受限 Checkpoint 获取需求 v1

日期：2026-08-27  
状态：按“上游直连”与“AI2Apps 再分发”两种模式冻结

## 结论

AI2Apps 对 MiniMax H3 的当前定位是本机部署工具，而不是 H3 Hosted Service 或权重托管方：

- AI2Apps Package 只声明上游 HF/MS repository、不可变 revision、文件摘要和本机运行配方；
- checkpoint 字节由最终用户的设备直接从上游 Hugging Face 或 ModelScope 下载；
- AI2Apps Cloud 不代理、缓存、回源或返回 checkpoint 字节；
- ACPF 和 Models App 在下载前要求用户确认其位于许可适用地区，并已接受条款或取得有效许可；
- AI2Apps 服务端不加载、运行或提供 H3 推理服务。

在以上边界内，AI2Apps 发布的是部署元数据和本地工具，不把 Checkpoint Distribution
envelope 本身解释为 AI2Apps 对模型权重的再分发。最终用户是访问、下载和运行 H3 Works
的一方，并承担符合 MiniMax H3 许可证的责任。

如果未来由 AI2Apps 上传镜像、代理下载、提供 CDN/cache、打包 checkpoint 或通过 P2P
向其他用户出传字节，则切换为“AI2Apps 再分发模式”，必须另行核对主体、团队所在地、
Hub 账号主体、接收方地域和权利方授权。

## 模式 A：上游直连，本次采用

### Cloud

Checkpoint Registry 只保存签名的来源与完整性元数据：

```json
{
  "deliveryMode": "upstream_direct",
  "byteCustody": "upstream_only",
  "sources": [
    {"provider": "huggingface", "repository": "...", "revision": "..."},
    {"provider": "modelscope", "repository": "...", "revision": "..."}
  ],
  "p2pPolicy": "prohibited"
}
```

要求：

- Cloud 不生成 checkpoint 代理 URL，不保存 Hub token，不接收或缓存文件内容；
- envelope 中的 URL 必须指向签名时固定的第三方上游 repository/revision；
- 上游不存在、revision 改变或文件摘要不匹配时 fail closed；
- `upstream_direct` checkpoint 禁止 AI2Apps P2P、LAN relay 和共享节点缓存出传；
- Index 和 envelope 可以公开，但它们不能被客户端当作模型使用许可；
- Cloud 保存 Publisher 审核记录，但不代表 AI2Apps 声明拥有 checkpoint 权利。

### Client / Local

在 cache 命中、本地导入、源探测和任何 checkpoint 字节读取前，Models App 与 ACPF 必须：

1. 展示许可证名称、固定条款 URL、适用/排除地区和用途限制；
2. 要求用户确认自己位于许可适用地区，并已接受条款或取得适用于其所在地的有效许可；
3. 将确认绑定到 `distributionId + manifestDigest + termsHash + decision`；
4. 未确认、位置声明不满足、策略未知或条款版本改变时 fail closed；
5. 直接连接 envelope 声明的 HF/MS 上游，不经过 AI2Apps Cloud；
6. 下载后执行文件 SHA-256 和 8 MiB piece 校验；
7. 不把 checkpoint 导入 P2P store 或自动分享目录；
8. 本地运行前再次验证许可收据仍与当前 distribution/terms 绑定。

本地缓存属于最终用户设备上的部署副本。AI2Apps 不回收、远程读取或向其他用户出传该副本。

## 模式 B：AI2Apps 镜像、代理或 P2P

下列任一行为进入再分发模式：

- AI2Apps 或其团队账号把 H3 文件上传到新的 HF/MS repository；
- Cloud/CDN/对象存储代理或缓存 checkpoint 字节；
- AI2Apps Package artifact 内包含模型文件；
- AI2Apps 节点、P2P、LAN relay 或共享 cache 向另一用户发送模型文件。

启用前必须由负责该行为的实际主体确认其在 MiniMax H3 许可的 Applicable Territory 内并
具有再分发权，同时落实许可证第三节要求的许可证交付、NOTICE、地域限制和下游约束。
若负责主体、Hub 账号或服务器位于 Excluded Territory，则需取得 MiniMax 的单独授权。

再分发模式必须使用独立的 `deliveryMode: mirrored` 或 `deliveryMode: p2p`，不得继续标记成
`upstream_direct`。Publisher 审核记录应保存授权依据、责任主体、服务地域和证据 hash。

## H3 当前五个 checkpoint 的双源状态

`ai2apps/model-minimax-h3 0.8.0` 当前声明：

- `MiniMaxAI/MiniMax-H3` BF16；
- `ddalcu/MiniMax-H3-FL2VA-MLX-Serve-8bit`；
- `ddalcu/MiniMax-H3-FL2VA-MLX-Serve-4bit`；
- `ddalcu/MiniMax-H3-REF2VA-MLX-Serve-8bit`；
- `gabrielrocco/MiniMax-H3-Ref2VA-MLX-Serve-4bit`。

截至 2026-08-27 的公开 Hub 元数据核对结果：

- 官方 BF16 在 HF 与 `MiniMax/MiniMax-H3` MS 仓库有 279 个同路径、同大小文件；MS 另有
  平台元数据文件。发布前仍需逐文件摘要和 8 MiB piece 校验，不能只凭文件名/大小认定一致；
- 四个 MLX 量化仓库在 HF 存在，但相同 repository ID 的 ModelScope 仓库均不存在；
- `Comfy-Org/MiniMax-H3`、`DiffSynth-Studio/MiniMax-H3-NF4` 等 MS 仓库使用不同布局或
  不同量化，不能冒充上述四个 checkpoint 的第二来源。

因此，BF16 可以在完成字节校验后升级为上游直连双源；四个 MLX checkpoint 当前只能保留
HF 单源，直到原作者或其他具备再分发权的适用地区主体发布字节完全相同的 MS 上游。若由
AI2Apps 北京团队负责创建镜像，应按模式 B 记录实际责任主体并完成许可证第三节义务。

## Builder 要求

- Builder 允许从最终用户或适用地区发布者已有的 HF cache 生成 8 MiB piece 摘要，不要求
  Cloud 持有 checkpoint；
- 没有本地完整文件时，不能仅由 Hub 的整文件 SHA 推导 piece 摘要；需要从某个上游读取
  一次全部字节，读取方必须符合相应许可；
- 双源必须逐文件路径、大小、SHA-256 和 piece 摘要一致；平台专用 README/.gitattributes
  可明确排除，但模型运行文件不能映射到不同量化或不同内容；
- 单源 checkpoint 可以继续使用统一 acquisition service，但 UI 必须如实显示只有一个来源，
  不能宣称具备 MS 容灾；
- Builder、Cloud 和 Client 都不得把 `upstream_direct` 静默升级为镜像或 P2P。
