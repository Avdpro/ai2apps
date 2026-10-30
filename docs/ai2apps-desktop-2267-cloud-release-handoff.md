# Desktop 0.1.8 / Build 2267 — Cloud 发布需求

日期：2026-10-30。状态：双源公证制品已发布并验证；Cloud 清单与目标 Mac 升级待执行。

请遵循 Cloud `docs/desktop-update-production-runbook.md`：双源预检 → 原子登记 0% → 验收 → 同一 rollout ID 扩至 100%。不要直接复制覆盖生产 stable.json，不伪造 operator/approver 身份。

## 本次固定输入

- 源码 commit：`fbee5c826b0387704fdf4b739be8ef9987f6990d`，干净分支 `codex/release-2267`，已推送。
- 产品：0.1.8，Build 2267；`com.ai2apps.desktop` / `default` / `arm64` / `cloud`，macOS 13+，Team `84XL5V265N`。
- Rollout ID：`build2267-test`；先 0，验收后目标 10000 basis points。
- GitHub：https://github.com/Avdpro/ai2apps/releases/tag/v0.1.8-build2267 （prerelease 标记，不影响更新器固定资产 URL）。
- ModelScope：`ai2apps/desktop-releases`，不可变 revision `86094cfd60ae09be92d18ae8cacb2df6281a61f7`。
- Apple Submission ID：`509ea0a2-e31c-4170-9709-227cb0dd14dc`，Accepted；DMG stapled，Gatekeeper / 签名 / 元数据 / 更新资格通过。

制品目录：
`/Users/avdpropang/sdk/omlx-moe-cache/apps/ai2apps-acefox/.build/releases/AI2Apps-0.1.8-build2267`

| 文件 | 字节 | SHA-256 |
| --- | ---: | --- |
| AI2Apps-0.1.8-build2267-macos-arm64.dmg | 268264389 | f9ffc11f8429f992be57b0b3601defde4714408083d269ab74b53aea5387f09c |
| AI2Apps-0.1.8-build2267-macos-arm64.release.json | 1011 | b5a53f3bb4d1d999b9a0eface685e301b3560186643206794a08c4fd6ca9bdc2 |

同目录 `stable-zero.json` 是登记输入，SHA-256 `2d032c0ed4456fa2f0dbeabc0827db37ea331a814ae8755065063a5712987591`。
`stable.json` 是 100% 目标参考，SHA-256 `0b3a4e07b3272df6e3d38b04f43d3d11fc7599fc4d228477fdf03219f4af1a55`；扩灰必须走 Cloud rollout，不绕过审计。

## 已完成验收

- 两个公开源的 DMG/metadata 均完整匿名下载，size/SHA-256 与本地一致；DMG `bytes=1024-2047` 返回206，Content-Range 和实际字节一致。
- GitHub PyPI run41019056614、Homebrew run41019056775 均 skipped。
- Host2880 passed/2 skipped，前端1037 passed，AaAT701 passed；最新冻结源码专项81 passed，OCR UI专项通过。
- 最终冻结前端1035 Desktop cases passed；iOS关联测试因独立源码不在 Desktop 快照而不可执行，其2项在原 iOS 工程复验通过，不修改产品规避测试。
- Swift79项通过；干净临时数据冷启动3.21秒，schema98；包内源码与冻结源一致。
- App717498403字节，比2266增加186675字节；没有完整推理 Runtime、模型 checkpoint 或实验虚拟环境。
- 真实 App-Dev：原生上传合成图 → 本地 SoMark OXR → ORCHID2267文字检索 → 系统简单任务模型归入腕表情报 → 收件箱临时归属移除。用户明确允许测试使用已配置云端模型；未放宽产品权限/隐私策略。
- 临时目录2266→2267更新器替换/验签通过；不冒充目标 Mac 的完整安装重启验收。

## 本版范围

纳入：NXR-ACCOUNT-RECHARGE-ICON-20261030、NXR-ACCOUNT-RECHARGE-20261030、NXR-KNOWLEDGE-COMPOSER-AUTO-BUCKET-20261030、NXR-KNOWLEDGE-ADD-FROM-ASK-20261030、NXR-KNOWLEDGE-REMOVE-APP-COLOR-20261030、NXR-KNOWLEDGE-IMAGE-OCR-20261030、NXR-AGENT-INPROCESS-LOOPBACK-20261030、NXR-CHAT-DELETE-DURABLE-REVISION-20261030，以及本次识别/归类资料卡UI与轮询修复。

源码同步：NXR-WORKER-SSD-PREFIX-CACHE-20261030、NXR-WORKER-TOOL-PROTOCOL-20261030、NXR-WORKER-SYSTEM-PLACEMENT-20261030、NXR-OXR-RUNTIME-20261030。独立 Package/Runtime 发布不属于本次；现有 Worker 仍需对应 Runtime 升级，不声称 Desktop 自身启用所有 Worker 改进。

## Cloud 执行与回执要求

1. 发布前重新读取线上清单；本次预检基线是2266/10000bp。如已被其他发布替换，停止并报告，不覆盖并行发布。
2. 使用以上本地文件绑定及不可变双源清单完成 schema、完整摘要、Range、公证预检。
3. 以真实可审计 operator、独立 approver 和限定 reason 登记2267/0%，再按批准扩至100%。身份不具备时请求负责人处理。
4. 回报 before/after digest、0%/100%审计、GET/HEAD200、ETag304、缓存/内容头、无Set-Cookie、健康与错误日志、跨地域一致性。
5. 至少一台已安装2266或更低版本的合格 Mac 完成检查、下载、安装、重启，记录新Build和下载源。完成前不能标记端到端发布成功。
6. 失败保持2266清单；若扩灰后发现问题，走 pause/历史摘要回滚，不手改清单或推送降级Build。

本任务没有直接修改 Cloud，也没有读取 Dev Cookie。此文档由用户交给 Cloud 生产任务执行。
