# EchoMimic V3 MLX 双源 Checkpoint 与 Package 发布收据

发布日期：2026-08-27

## Checkpoint repositories

- Hugging Face：`Avdpro/EchoMimicV3-MLX`
- Hugging Face immutable revision：`c04fb47465c0c615681b7d927256f6d5a3a314cc`
- ModelScope：`ai2apps/EchoMimicV3-MLX`
- ModelScope 首轮大文件 commit：`29c1c5e7dbb1a454f67b1323befc3fa62154eb6a`
- ModelScope 最终 immutable revision：`15f01fd1ab866b9c66b360ca15dc0dded52bc7cc`
- Checkpoint runtime 文件：10 个；distribution 发行文件：15 个
- Distribution 总大小：`20766374281` bytes
- 许可：EchoMimicV3、Wan-Fun、UMT5 和 AI2Apps conversion 为 Apache-2.0；Chinese Wav2Vec2 Base 为 MIT。完整组合许可由固定 revision 中的 `COMPOSITE-LICENSE.txt`、`LICENSE` 和 `NOTICE` 提供。

上传后使用 ModelScope Hub 最终文件元数据核对了每个发行文件的大小与 SHA-256。大文件与本地已冻结 checkpoint 及 Hugging Face 固定 revision 完全一致；构建过程没有再次下载 ModelScope checkpoint。

## Checkpoint Distribution

- Distribution ID：`dist_ai2apps_echomimic_v3_mlx_c04fb474_v1`
- Model ID：`ai2apps.model.echomimic-v3-mlx/default`
- Manifest digest：`sha256:d9d41bf8e7bd3c2b17c35ed2bba8c08e72ab045ec58a16849eb8503baf49f0a4`
- Piece size：`8388608` bytes
- Piece count：`2476`
- Verification builder：`ai2apps-local/checkpoint-metadata-verified-v1`
- Verified providers：Hugging Face、ModelScope
- Submission ID：`3c009910-d509-4b07-b3b3-1726ecca194d`
- Review ID：`7868fd6b-f1f5-4d06-b852-5b25dda70558`
- Published at：`2026-08-27T10:51:38.516Z`
- Checkpoint Index version：`29`

无 Cookie 公网回读验证了签名 Index、Publisher/key、manifest digest，并确认公网 envelope 与本地签名 envelope 的 JSON 完全一致。

## Package release

- Package ID：`ai2apps/model-echomimic-v3-mlx`
- Version：`0.1.1`
- Source baseline commit：`66736ccaed462e6f366b03d15c10aec5b43213ff`
- Artifact：`packages/ai2apps-model-echomimic-v3-mlx/dist/ai2apps-model-echomimic-v3-mlx-0.1.1-production.ai2service`
- Artifact SHA-256：`7286ac77edbacfda05d911f817c030d3d169022729ba1929972e241b17a6878b`
- Artifact size：`103576` bytes
- Publisher ID：`229d6350-cd0e-408a-9905-41367385ae5c`
- Publisher key ID：`8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc`
- Submission ID：`cd1cdd1b-7c09-4831-bc72-b92980116fc6`
- Review ID：`5b106b01-d28b-4673-9aab-49e36050ed68`
- Published at：`2026-08-27T10:54:35.089Z`
- Repository metadata version：`84`

Package `service.yaml`、Contract manifest、source lock 和 SBOM 已升级到 `0.1.1`，绑定上述 distribution、HF revision 与 MS revision。Package archive 不包含 checkpoint 字节、上传缓存、旧 `dist/` 内容或私钥文件。

## Validation

- EchoMimic Package tests：`5 passed`
- Checkpoint Package policy tests：`3 passed`
- JSON/YAML metadata parsing：passed
- `git diff --check`：passed
- Signed Package builder contract/signature checks：passed
- 公网 catalog：latest version `0.1.1`，status `published`
- 公网 artifact：SHA-256、size 和字节内容与本地 release artifact 完全一致
- 公网 Package envelope：JSON 与本地签名 envelope 完全一致

共享 `tests/test_ai2apps_model_providers.py` 同次诊断运行中为 `30 passed, 1 failed`；唯一失败是既存 FLUX 测试仍期待已经从当前 FLUX Package 移除的 9B variant，与 EchoMimic 变更无关，未在本次发布中修改。

本次 scoped Cloud Cookie 只用于该 distribution 与 Package 的提交、审核、发布；所有最终回读均为匿名公网请求。
