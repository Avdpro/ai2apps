# AI2Apps Cloud: Browser Screenshot Input Requirements

## Status

Implemented and deployed to Cloud production on 2026-08-28:

- OpenAPI `1.26.0`
- release commit `b01f5ce`
- deployment record commit `a6a4c77`
- PNG, JPEG, and WebP Data URLs supported with 8 MiB and 25 MP limits
- clean Cloud build tests: 193/193
- first client production acceptance: passed from the AceFox Chat Sidebar with
  `cloud/openai/gpt-5.6-terra`; `/v1/ai/responses` returned HTTP 200 and streamed
  a page-grounded answer while visible-page screenshot input was enabled

The Cloud production report is maintained in the Cloud repository at
`docs/browser-screenshot-input-production-deployment-2026-08-28.md`.

## Scope

The AceFox Chat Sidebar can capture the visible page through native WebDriver
BiDi and send it to an image-capable model. Local already converts the standard
OpenAI Chat content part

```json
{"type":"image_url","image_url":{"url":"data:image/png;base64,..."}}
```

to the Cloud Responses input part

```json
{"type":"input_image","imageUrl":"data:image/png;base64,..."}
```

Older Cloud deployments rejected that request with
`400 INVALID_AI_REQUEST: imageUrl is invalid`. The production contract now
accepts it. Cloud implementation and deployment remain outside the Local
repository change boundary.

## Required Cloud change

- Accept `data:image/png;base64,...`, `data:image/jpeg;base64,...`, and
  `data:image/webp;base64,...` in `input[].content[].imageUrl`.
- Decode with strict base64 validation and reject malformed, empty, unsupported,
  or oversized images before invoking a provider.
- Enforce decoded-byte and pixel-dimension limits. The initial product limit
  should be at most 8 MiB decoded and 25 megapixels per image.
- Preserve the image when adapting the request to OpenAI, Anthropic, Google, or
  another provider, using that provider's native inline-image representation.
- Keep existing HTTPS image URL support if it is already part of the contract;
  do not fetch loopback, private-network, file, or other unsafe URLs.
- Never log the Data URL, decoded pixels, browser page text, or authorization
  material. Diagnostics may record media type, decoded byte count, dimensions,
  model ID, and validation outcome.
- Return a structured `INVALID_AI_REQUEST` message that distinguishes invalid
  base64, unsupported media type, excessive byte size, excessive dimensions,
  and a model that does not accept image input.

## Acceptance tests

1. A small valid PNG Data URL reaches an image-capable managed model.
2. JPEG and WebP Data URLs follow the same path.
3. Invalid base64 and unsupported MIME types return deterministic HTTP 400
   errors without provider invocation.
4. Oversized byte and pixel payloads are rejected before provider invocation.
5. A text-only model returns a model-capability error.
6. Logs and error responses contain no image payload or credential material.
7. Streaming text output remains compatible with the existing Local SSE
   bridge.
