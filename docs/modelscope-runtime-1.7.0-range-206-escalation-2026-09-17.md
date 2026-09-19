# ModelScope Runtime 1.7.0 Range 206 escalation — 2026-09-17

## Target

Add this reproducer to the existing official ModelScope Hub issue:

- <https://github.com/modelscope/modelscope_hub/issues/50>

The issue already tracks the same server behavior: ModelScope honors a Range
request and returns the requested slice plus a correct `Content-Range`, but the
repository nginx responds with HTTP `200` instead of RFC-compliant `206`.

## Suggested comment

We can reproduce this on a newly uploaded public Git LFS object in
`ai2apps/desktop-releases`.

Object:

```text
repository: ai2apps/desktop-releases
revision: 18751703b53671cb2db926f9f8ed508a70df15b0
path: ai2apps-runtime-omlx-1.7.0-production.ai2service
size: 373748488
sha256: b066700dcebec87012e93de01e6114db9f231b0a1c89642e97c50cd91a1ec3a7
```

Minimal anonymous reproduction:

```bash
curl -sS -D - -o /dev/null \
  -H 'Range: bytes=0-4095' \
  -H 'Accept-Encoding: identity' \
  'https://modelscope.cn/models/ai2apps/desktop-releases/resolve/18751703b53671cb2db926f9f8ed508a70df15b0/ai2apps-runtime-omlx-1.7.0-production.ai2service'
```

Observed:

```text
HTTP/1.1 200 OK
Server: nginx/1.24.0
Content-Length: 4096
Accept-Ranges: bytes
Content-Range: bytes 0-4095/373748488
```

The body is exactly the requested 4096-byte slice. First, middle and final
4 KiB slices all match the local object, so only the response status is wrong.
The response does not redirect to the LFS CDN.

The object is a valid Git LFS pointer, the repository API reports
`IsLFS=true`, `.gitattributes` contains the exact LFS rule, and the upload
transferred all 373,748,488 bytes before committing. Committing the identical
OID under a new SHA-named path at revision
`bc1695dad1017b155d9b25b03a623793c2c7e308` produced the same direct nginx
`200 + Content-Range` response, which rules out the filename and commit
revision.

For comparison, the older object below in the same repository redirects to
`cdn-lfs-cn-1.modelscope.cn` and returns HTTP `206` correctly:

```text
revision: 97e28e20e9c420e50297d8891b2d1f4e2cb111d9
path: ai2apps-runtime-omlx-1.6.2-production.ai2service
size: 376086471
sha256: 040bdf2e5bc32fed203bbc695d5bd34ebd5e514a70a7b38dd8a97f0cdc28943a
```

Could the platform team either:

1. fix the repository nginx response to return `206 Partial Content` whenever
   a valid single-range request is honored; or
2. repair/reindex the LFS delivery mapping for OID
   `b066700dcebec87012e93de01e6114db9f231b0a1c89642e97c50cd91a1ec3a7`
   so immutable resolve URLs use the normal LFS CDN path?

This blocks strict resumable and parallel-range clients that correctly require
HTTP 206. No authentication is required to reproduce the problem.

Additional same-client, same-network probes show that this is associated with
individual LFS objects rather than one generally broken edge node:

| Repository object | Delivery | Result |
| --- | --- | --- |
| DS4 4-bit `model-00001-of-00046.safetensors` | redirect to `cdn-lfs-cn-1.modelscope.cn` | `206` |
| DS4 4-bit `model-00046-of-00046.safetensors` | redirect to `cdn-lfs-cn-1.modelscope.cn` | `206` |
| DS4 4-bit `experts/layer-000.moe` | direct `modelscope.cn` nginx | `200 + Content-Range` |
| Ornith `ornith15_vision_bf16.safetensors` | redirect to `cdn-lfs-cn-1.modelscope.cn` | `206` |
| Ornith `experts/layer-000.moe` | direct `modelscope.cn` nginx | `200 + Content-Range` |
| DS4.1 `experts/layer-0.bin` | direct `modelscope.cn` nginx | `200 + Content-Range` |

The direct-nginx responses still returned exactly the requested 4096 bytes and
the correct total size. In a wider one-file-per-repository sample, DS4 4-bit
and Ornith had a CDN-backed `206` object, while DS4.1, DS4 2-bit, GLM, Qwen
Next and Qwen3.6 sampled objects returned direct-nginx `200 + Content-Range`.
This pattern is consistent with older/reused global LFS objects already having
CDN delivery mappings while newly generated SSD objects do not.

## Information that must remain private

Do not include ModelScope tokens, upload URLs, temporary CDN signatures,
cookies, browser profile paths or Cloud publication credentials. The public
repository, immutable revisions, object hashes and anonymous curl command above
are sufficient.
