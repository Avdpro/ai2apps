# Desktop 0.1.8 / Build 2268 — Cloud 发布交接

日期：2026-10-31。制品已完成 Developer ID 签名与 Apple 公证，已上传双源。
Cloud 生产清单及目标 Mac 完整升级仍待执行，不能标记端到端发布完成。

按 Cloud `docs/desktop-update-production-runbook.md` 执行双源预检、原子登记 0%、
验收后以同一 rollout ID 扩至 100%。不得直接覆盖 stable.json，不伪造审批身份。

## 固定输入

- 产品：0.1.8 / Build 2268；`com.ai2apps.desktop`、`default`、`arm64`、`cloud`、macOS 13+，Team `84XL5V265N`。
- 源码：`a000d0971e7288d7445829843c97bad88edf43d0`，分支 `codex/release-2268`，已推送。构建起点 `cfe9647c`；后续提交仅补 CI 门禁，全部内嵌产品内容与最终源码逐字节相符。
- Rollout ID：`build2268-test`，先 0，验收后 10000 basis points。
- GitHub：https://github.com/Avdpro/ai2apps/releases/tag/v0.1.8-build2268 （沿用 prerelease 标记，更新器按固定资产地址获取）。
- ModelScope：`ai2apps/desktop-releases`，不可变 revision `c99d4cd80338d8ea29f01720ca168b0f29be3de8`。
- Apple Submission：`30d2e70c-0b3b-4edb-99a3-9de9bcf8c1f0`，Accepted，stapled，Gatekeeper 接受。

制品绝对目录：
`/Users/avdpropang/sdk/omlx-moe-cache/apps/ai2apps-acefox/.build/releases/AI2Apps-0.1.8-build2268`

| 文件 | 字节 | SHA-256 |
| --- | ---: | --- |
| AI2Apps-0.1.8-build2268-macos-arm64.dmg | 268276357 | 3fb1e8ab81edd0bb6f9830b547af18080a5fc8f9b1e1d3cdd7a31ba3126d16d1 |
| AI2Apps-0.1.8-build2268-macos-arm64.release.json | 1011 | 592e2bcada6e170561ead9188ce5544457150ed4918db95e6efae68ee071288a |
| stable-zero.json | 1818 | 0bb5c00ab5cfbaea64d2fd591c78a8a86046045f498f70b8d5c87cf0bb5a19eb |
| stable.json | 1822 | cf598f74339fcf59bb5254fa576facfd706dab4e164e334231ad1ee38a5e05cc |

`stable-zero.json` 是发布输入；`stable.json` 仅为目标参考，扩灰必须走 Cloud rollout。
本地双源核验结果见同目录 `github-verification.json`、`modelscope-verification.json`；
Cloud 仍须独立完成完整下载、摘要、Range 与公证元数据检查。

本地双源匿名校验均已完成：DMG 和 metadata 完整 SHA-256/大小一致；
DMG `bytes=1024-2047` 均返回206，Content-Range 与实际字节完全相符。

## 范围和验证

纳入：NXR-MOBILE-KNOWLEDGE-CAPTURE-ASK-20261030、NXR-KNOWLEDGE-GROUPED-FILES-20261030、
NXR-KNOWLEDGE-SCREENSHOT-OVERLAP-20261030、NXR-KNOWLEDGE-MOBILE-PUBLIC-UPLOAD-20261030、
NXR-MOBILE-KNOWLEDGE-NATURAL-QUERY-20261030、NXR-MULTIMODAL-MEMORY-ADMISSION-20261030、
NXR-KNOWLEDGE-SEMANTIC-SETUP-BANNER-20261030、NXR-KNOWLEDGE-ACPF-DIALOG-STYLES-20261030、
NXR-AUDIO-STARTUP-20261031；已发布共享 MLX/LanceDB/E5 的 Desktop 配置与官方 RAG 白名单适配。
独立 Runtime/Package 发布、实验目录和模型权重不纳入 DMG。音频目录优化不声称已测量实机提速。

- 用户明确确认手机图片上传、自然语言问答、多图合并/重叠去重实机通过。
- Host 2917 passed / 2 skipped；冻结专项 90 passed；Swift 79 passed；存储/Chat 修正测试 68 passed。
- 前端 1033 passed，加最终路径/语言映射复验 8 passed；独立 iOS 契约 2 passed。
- AaAT 冻结快照 699 passed；CI 门禁缺项补齐后架构 27 passed；独立 Package 源码不在 Desktop 快照，完整开发目录绑定测试 19 passed。没有跳过真实业务失败。
- 已纠正旧数据库测试表/迁移预期、崩溃测试固定版本号冲突、旧 Chat 删除断言和误入访客键映射的 Knowledge 文案。
- 签名 App 717562729 字节，仅比 2267 增加 64326 字节；没有完整推理 Runtime 或 checkpoint。
- 干净临时数据冷启动 3.709 秒，schema 100，源码和实际服务资产一致；不触碰用户实例数据。
- 2267→2268 更新资格检查 eligible；不冒充目标 Mac 完整升级。
- GitHub PyPI run 41148341292、Homebrew run 41148341319 均 skipped。

## Cloud 执行要求

1. 重新读取生产基线；本次核验为 2267 / 10000bp，如已变化则停止并报告，避免覆盖并行发布。
2. 绑定以上本地 DMG 与 metadata，完成双源匿名完整摘要、大小、Range206、schema 和 notarization 检查。
3. 使用真实 operator、独立 approver、限定 reason，原子登记 2268 / 0%，验收后扩至 100%。
4. 回报前后清单摘要、0%/100%审计、GET/HEAD200、ETag304、缓存头/内容头、无 Set-Cookie、健康与错误日志、多地域结果。
5. 在至少一台合格 Mac 完成检查更新、下载、安装及重启，记录旧/新 Build 和下载源。完成前保持 released_pending_target_mac。
6. 预检失败保留 2267；扩灰后有问题走 pause 或审计历史摘要回滚，不手改清单、不推送降级 Build。

本任务不直接修改 Cloud，没有读取 Dev Cookie；交接文档由用户交给 Cloud 生产任务执行。
