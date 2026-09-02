# Cloud Package ModelScope HEAD 回退需求 v1

日期：2026-09-03
状态：生产阻塞修复需求

## 1. 背景

生产 Cloud OpenAPI `1.39.0` 已支持 Package 多源注册、完整预检、双人审批和签名
Repository Snapshot。为现有发布版本 `ai2apps/runtime-omlx 1.5.7` 配置三源时：

- GitHub 不可变 Release 源通过完整预检并进入 `pending_approval`；
- ModelScope 不可变 revision 源被标记为 `validation_failed`，失败码为
  `size_mismatch`；
- ModelScope API 文件元数据、匿名 Range 响应及本地正式制品均确认大小为
  `457410846` 字节、SHA-256 为
  `b7f5e0bddcf285908ddd75465c02bdd35a9f6aa90690c739054a75295ea4bd49`；
- 首段、中段、尾段及单字节 Range 均返回正确 `206`，且字节与本地正式制品一致。

根因是 ModelScope 的公开不可变 `resolve/<40-hex-revision>/<filename>` URL 对
`HEAD` 返回 `200`，但不提供 `Content-Length`；同一 URL 的
`GET Range: bytes=0-0` 经受控重定向后返回：

```text
206
Content-Length: 1
Content-Range: bytes 0-0/457410846
Accept-Ranges: bytes
X-Linked-Etag: b7f5e0bddcf285908ddd75465c02bdd35a9f6aa90690c739054a75295ea4bd49
```

当前验证器把“HEAD 未声明完整长度”当作“已确认长度不一致”，导致生产白名单允许的
ModelScope 大型 LFS 制品无法激活。

## 2. 必须修改的行为

仅调整 Package 外部源预检器，不修改 Package Release、Publisher envelope、piece
manifest、公开 API 结构或客户端合同。

1. 对 allowlist 已通过、URL 已规范化、重定向仍满足现有限制的外部源先执行现有
   `HEAD`。
2. 如果 `HEAD` 明确返回有效、可解析且非负的 `Content-Length`，继续要求它等于
   Release `artifact.size`；明确不一致仍返回 `size_mismatch`，不得回退掩盖冲突。
3. 如果 `HEAD` 成功但缺少 `Content-Length`，不要把缺失值解释成 `0`，也不要立即
   返回 `size_mismatch`；改为执行单字节探针：

   ```http
   GET <source-url>
   Range: bytes=0-0
   Accept-Encoding: identity
   ```

4. 单字节探针必须同时满足：

   - 最终响应为 `206`；
   - `Content-Length` 精确为 `1`；
   - `Content-Range` 严格匹配 `bytes 0-0/<total>`；
   - `<total>` 精确等于 Release `artifact.size`；
   - 响应体精确为一个字节；
   - 所有重定向继续满足现有 host、scheme、次数、DNS/SSRF 和临时签名参数规则。

5. 只有上述探针通过后才能继续现有首段/中段/尾段 Range、逐 piece SHA-256、完整
   SHA-256 和 size 预检。单字节探针不能替代完整校验。
6. 如果 `HEAD` 缺少长度且单字节探针失败，返回 `head_rejected`、
   `range_not_supported` 或更准确的新错误码；不得错误报告已经观察到的文件长度不一致。
7. 验证收据仍记录最终观察到的完整大小、完整 SHA-256、Range 支持状态、piece 匹配状态
   和 validation digest，不降低激活门槛。

## 3. 安全边界

- 回退只适用于成功 `HEAD` 缺少 `Content-Length` 的情况；明确冲突不能回退。
- 不放宽 Package source allowlist。生产仍只允许当前精确的 GitHub/ModelScope 仓库。
- 不把 ModelScope 重定向中的临时签名参数写入数据库、日志、API 响应或审计记录。
- 不接受 `200` 作为 Range 成功，不接受模糊或多段 `Content-Range`。
- 不信任 `X-Linked-Etag` 代替完整 SHA-256；它只能作为诊断信息。
- 不允许注册人激活自己的 source，既有双人审批规则保持不变。

## 4. 回归测试

至少新增以下自动化用例：

1. HEAD `200`、无 `Content-Length`，单字节 Range 提供正确 total：通过并继续完整预检；
2. HEAD 提供正确长度：沿用原路径；
3. HEAD 提供错误长度：立即 `size_mismatch`，不执行回退；
4. HEAD 无长度、Range 返回 `200`：拒绝；
5. HEAD 无长度、Range total 错误/缺失/语法非法/多段：拒绝；
6. HEAD 无长度、Range body 非一字节或编码非 identity：拒绝；
7. ModelScope 受控重定向通过；未允许 host、DNS rebinding、凭据 URL 和超限重定向拒绝；
8. 正确 Range total 但完整 SHA-256 或任一 piece 错误：拒绝；
9. GitHub 现有 HEAD 路径继续通过；Cloud fallback、旧单源 Package 和公开 Snapshot 不变；
10. 注册人与激活人相同仍被拒绝。

## 5. 生产复验

部署后不需要重新上传、重新签署或重新发布 Runtime Package。对现有失败 source 调用：

```text
POST /v1/admin/registry/packages/ai2apps/runtime-omlx/versions/1.5.7/
     sources/src_2b44203b-e194-4df6-8a1a-3e0ec8bfe797/validate
```

等待它进入 `pending_approval`，核对：

- size `457410846`；
- SHA-256 `b7f5e0bddcf285908ddd75465c02bdd35a9f6aa90690c739054a75295ea4bd49`；
- `rangeSupported=true`；
- `pieceManifestMatched=true`；
- validation digest 非空。

随后由不同于注册人的 reviewer/admin 分别激活 ModelScope 与已经通过预检的 GitHub
source。最终匿名回读必须显示 Cloud + ModelScope + GitHub 三个 active 源，并验证新
Repository Snapshot 签名；Package 版本、Publisher envelope、完整摘要和 Cloud 兼容 URL
必须保持不变。

## 6. 当前生产交接数据

- Package：`ai2apps/runtime-omlx 1.5.7`
- artifact size：`457410846`
- artifact SHA-256：
  `b7f5e0bddcf285908ddd75465c02bdd35a9f6aa90690c739054a75295ea4bd49`
- ModelScope source：`src_2b44203b-e194-4df6-8a1a-3e0ec8bfe797`
- ModelScope validation：`val_5ff09c36-640c-448b-99be-5efdc6f665f4`
- GitHub source：`src_93a2debf-8a8a-4d14-b485-597142933bb9`
- GitHub validation：`val_569a6c15-8dd7-4c9f-8ee0-2a64090135d1`
- GitHub validation digest：
  `dde90d4cef4c073729cb01a46e8a0a7e038f1d2044b59a2c0d7fccf58e7302a0`

当前 GitHub source 为 `pending_approval`；ModelScope source 为
`validation_failed`。不得在 Cloud 热修前伪造 ModelScope 通过状态。
