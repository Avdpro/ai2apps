# 数字人 Package 发布回执（2026-10-01）

当前状态：三个 Package 均已正式发布，Repository Snapshot 232。Host 原图回贴代码尚未发布为 Desktop Build。

## 发布身份与可复用签名上下文

沿用 MiniMax H3 0.9.1 的成功构建命令，同一 Publisher 与原签名记录；未新建或切换密钥。

- Publisher：`229d6350-cd0e-408a-9905-41367385ae5c`
- Cloud key：`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- 派生公钥指纹：`216f5256f2e80ad188f3ebe2fd1eeccf666f713c87dc098c443770617d5b3027`，与 Cloud 完全一致。
- 本地签名记录引用（非秘密值）：`sec_7d62c890f9cb46c0a223c02ec6d7ee9e`
- 原 namespace（非秘密值）：`local_cd8e3c23002c87b528cc5f4790fa1269`
- 该 namespace 不等于当前 Dev installation ID；不要从 Dev 空的 Secret 元数据推断密钥丢失。后续发布仍须先核对 Cloud 公钥指纹，只加载这一精确记录，不枚举 Keychain。
- 本次用户授权 Dev Cookie；通过标准发布脚本 `--browser-live` 在内存使用，未导出 Cookie、Cloud token 或私钥。此授权在本次发布完成后失效。

## AVTR 权重

- Distribution：`dist_ai2apps_avtr1_mlx_57bfb656_v1`
- HF：`Avdpro/AVTR-1-MLX@57bfb656636e9fdb24646a2711a7bb606cbd7cb5`
- ModelScope：`ai2apps/AVTR-1-MLX@17caeffa78ee672e36e22e6f3d798ccef90e7c45`
- 30 个文件，304 pieces，2,549,026,222 bytes；两个固定源分别全量下载并验证 SHA-256。
- Manifest digest：`sha256:1893a36b5f2440ba19a91a37d86c51e1afdd6ff192606093c01d130f76799b4c`
- 已发布并匿名验证 Checkpoint Index 96，保留原协议、组件许可证与署名。

## 实现与验收

- AVTR 是独立模型 Package，依赖现有 Runtime >=1.8.5,<2，不内置 Runtime。图执行、采样与渲染使用 MLX；无 OpenCV/ONNX 推理依赖，无其它模型 Package 源码依赖。
- Host 通用原图模式覆盖 AVTR、FlashHead Lite/Pro、EchoMimic：系统 Vision 人脸定位、原生尺寸裁剪、生成、逆变换回贴、保留画布与音轨。支持 EXIF 和 Alpha 合成；边缘羽化不是人物抠像。
- 44 项 Python 回归与两组 Mini-App 前端测试通过；Ruff 与 diff whitespace 检查通过。无 Metal 的测试进程退出时有 MLX atexit 警告；实际 GPU 验收在完整权限的已安装 Worker 中执行。
- AVTR 正式签名字节完成独立 Managed Service 安装、Runtime 依赖解析、签名 Distribution 快照激活、真实图片+音轨生成、停止、重启与卸载。2 秒 512px 沙箱调用第二次实测 20.45 秒；首次 45.89 秒。短片时间包含加载/编译，不能作为稳态吞吐比较。
- Suite 在独立临时实例完成签名安装，保留原有沙箱 Mini-App 权限和通用能力依赖。临时实例无 Local AI Auditor，记录了静态审阅批准；没有更改用户实例的审计策略。
- 通用回贴四模型真实生成的 1920×1080 样片已经检查；新增 Host 功能仍须随 Desktop 发布，不能仅安装 Mini-App 更新便宣称生产客户端具备它。

源码基线：`fa377dcb62875d5c82fc8177afd4277cd2357db9` 加本次未提交改动；发布制品摘要是最终字节身份。

## 正式 Package 回执

| Package | 版本 | bytes | SHA-256 | Submission | Snapshot |
| --- | --- | ---: | --- | --- | ---: |
| `ai2apps/model-avtr1-mlx` | 0.1.0 | 85815 | `f19538e23806f9467eb9267b43250b31e8a3d450c17ce2ec2f38a92bacad3c8c` | `a012495c-6c71-42c1-ac9b-cf5b2091a516` | 229 |
| `ai2apps/model-echomimic-v3-mlx` | 0.1.2 | 104492 | `d6dc3a0640be29796951d3ca24cc3406802daa163a35108f6907502ebe63aae9` | `5441e376-a879-45e3-907c-1a73603945a5` | 230 |
| `ai2apps/avatar-studio-suite` | 0.1.2 | 12043 | `e4eedfa2daaeb6a02e947f136cfc4153a3394a9824935f682a759fcff9721a9f` | `ef5d0111-ba5f-44be-ab04-86edae6148d7` | 232 |

EchoMimic 0.1.2 已完成独立签名安装、原分发清单的完整 SHA-256 校验、真实 multipart 图片/音轨生成、停止、重启及卸载。3.24 秒样片的沙箱首次调用为 173.17 秒，包含加载和编译，不作为稳态性能比较。

Suite 使用手册规定的 `--omit-mini-app-catalog`：当前 Cloud 拒绝可选顶层 miniApps 搜索投影；签名 app.yaml 仍完整，精确兼容制品已在新临时实例安装验证。首次 schema 拒绝没有产生 submission；未覆盖任何已发布版本。

三份 Package 均为小型代码包，保留 Cloud 制品源；模型权重由独立的 HF/ModelScope 双源 Distribution 分发。无需发布新 Runtime。

机器可读回执：`ai2apps-avatar-packages-release-2026-10-01.json`。Package 与 envelope 位于各源码目录的 `dist/<version>/`；AVTR Distribution 的签名 envelope、manifest 与双端验证回执也已保存于 AVTR `dist/0.1.0/`。


### Suite 0.1.2 兼容性修复

最终匿名下载验收发现旧声明 `compatibility.ai2apps >=0.1.1` 与 Local 固定的 Package Contract 0.1.0 不兼容。0.1.1 已发布，因此不覆盖原字节；0.1.2 把范围改为 `>=0.1.0 <2.0.0`，与当前客户端契约一致。候选先通过真实 Registry 兼容性检查，再在新临时实例安装。最终交付版本是 0.1.2；0.1.1 作为不可变历史版本保留，客户端会拒绝安装该旧版本。机器回执记录其被替代原因。

最终三个版本均通过无 Cookie 的 Local Registry 信任链回读：Repository Snapshot 232，制品 SHA-256 与本地精确一致，envelope JSON 精确一致，当前客户端契约兼容检查通过；两个模型的 modelInstall 均完整返回。本次 Cookie 发布授权已完成，不再沿用到其它发布。
