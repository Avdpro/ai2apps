# SAM 2.1 Video Cutout MLX 0.1.0 发布回执

状态：Checkpoint Distribution、oMLX Runtime 1.8.6 与 SAM 2.1 模型 Package
均已正式发布。用户授权的 Dev Cookie 只由标准发布脚本以 `--browser-live` 在内存
使用；没有读取 SQLite、输出 Cookie 或复制浏览器 Profile。上述发布完成后，该授权失效。

## 固定权重与 Distribution

- Distribution：`dist_ai2apps_sam21_hiera_small_mlx_1b7b9882_v1`
- 模型：`ai2apps.model.sam21-mlx/small`
- Hugging Face：`eisneim/sam2.1_mlx@1b7b98828e383e3d64025b615aff049b1face026`
- ModelScope：`ai2apps/SAM2.1-Hiera-Small-MLX@5717d4e02f95c3bad4a784748b6830b10277aba7`
- 权重：`sam2.1_hiera_small.safetensors`，184,302,864 bytes，SHA-256
  `0b3a0198309acc9d1879d0a78aedc4adea10cf2fa9ff6ab173872fc6f4ae3eef`
- 双端完整下载逐字节验证；1 个文件、22 pieces；manifest digest
  `sha256:82b836e5bd2537d089627aa84ac313fd81deeb93dd63bb4ac50e5b9a4e2e1a39`
- submission `4c51d91d-f974-4e82-b28a-a62c9a2c4f78`，review
  `202cb176-79a5-459d-8aaa-11e85bcea10c`，Checkpoint Index 97；匿名回读的
  envelope JSON 与本地签名文件完全一致。

## Runtime 1.8.6

- 新增有界 `video_segmentation` Worker operation、模型类型和 capability schema；
  复用 MLX、NumPy、SciPy、Pillow、PyAV 与现有视频编码层，不增加原生依赖。
- Apple notarization `e81b3803-baef-4662-b655-04ba5d0e7022` Accepted；staple、
  `stapler validate` 与 Gatekeeper 通过。
- DMG：386,459,912 bytes，SHA-256
  `e1a61dedb1904e804ab812e22dea48caf7b457532835e3d3763107b17c8b0f6c`。
- 正式 Package：383,767,580 bytes，SHA-256
  `0da6fda250a7144173a1dd27bfc84df17716e2398357456738796a4f19cc6b7e`。
- submission `e2bf34a2-8fdf-447e-81c6-9e747c3a49ad`，release published。
  初始上传客户端在服务端完成后收到泛化 internal error；标准查询确认该 submission
  已发布且摘要完全一致，因此没有重复上传。
- GitHub tag `package-runtime-omlx-v1.8.6`；Source
  `src_0d4104d4-921e-4c6b-b489-3e10c0b1ff3d`，validation
  `val_84c31b8b-45f1-4846-9b42-b3534644382f`，digest
  `d755c8c1d97ad2545f406fb43c4af91179433de49cb3d734ed136bce78444f71`。
- ModelScope immutable revision `af22b6c5b5641accd7029ca7eb920bfd3379eaa1`；Source
  `src_fafc7799-3d0b-41a8-9853-aa049394e3e2`，validation
  `val_8e01b6ae-4186-41c3-989a-6eeb59f6bd64`，digest
  `9d859ecd19f82d32a122bec85ef4e9dd2331e00a74f2106818bc945016f62667`。
- Cloud/GitHub/ModelScope 三源均 active；两个外部源完成匿名完整 SHA-256、首/中/尾
  Range 及 Cloud 46-piece/49-request 校验。最终 source revision 6，Repository metadata
  235，Snapshot digest
  `6759dc8ad9732b83762bbfa52bc0d18c65861c9443d67396145de606e03ec519`。

## SAM 2.1 模型 Package

- Package：`ai2apps/model-sam21-mlx` 0.1.0。
- 归档：50,083 bytes，SHA-256
  `d780f1374b17a2278d981f02376f6e4981fd7056b9fc522529caf6524f2a249e`。
- submission `7894c594-7325-4d7b-9acc-dede4de87c0d`，review
  `1460c8c1-1aaf-4fe4-a0b1-5e811a0f56ee`，Repository metadata 236。
- 归档不含 184 MB 权重；`modelInstall` 唯一推荐 Hiera Small，并依赖
  `ai2apps/runtime-omlx >=1.8.6,<2.0.0`。
- MVP 支持单对象正/负点提示、从提示帧向后跟踪、软灰度 H.264 MP4 蒙版；最多
  450 帧、1920×1080。输出用于 Host 动态蒙版，不宣称透明视频容器输出。

## 验证与未完成项

- 75 项当前 Provider/Worker/资源/capability 回归通过；此前完整定向套件、标准
  Model Worker harness、Ruff、diff check 和软蒙版 MP4 编码/回读通过。
- 精确签名 Runtime 1.8.6 与 SAM Package 在新的隔离实例安装成功；SAM Worker
  `running`，依赖锁精确指向 Runtime 摘要。Runtime 也用已发布 FlashHead Package
  完成独立 Worker 启动验证。
- 无 Cookie 的公共 Registry 回读确认 Runtime 与 SAM 两份归档字节、大小、SHA-256
  及 Publisher envelope 与本地完全一致，Repository metadata 236。
- 当前终端环境无 Metal，测试退出时会产生已知 MLX atexit 警告。真实 SAM 权重视频
  推理、停止/重启/卸载全生命周期和 Video Composer 动态人物蒙版 UI 接入仍需在完整
  GPU 权限的安装实例中完成；本回执不把这些项目记作已验收。
