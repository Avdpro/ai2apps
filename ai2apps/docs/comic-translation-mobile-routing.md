# Comic Translation on the mobile Owner surface

The Comic Translation Package uses the existing Studio mount, capability probe and Gallery asset routes. It also needs these exact routes under `/v1/platform/studios/{studio_id}/mini-app-mounts/{mount_id}/comic-translation`, with the existing authenticated Imagine Studio Owner policy.

| Method | Suffix |
| --- | --- |
| GET | `/models` |
| POST | `/image/{action}` with `analyze`, `recognize` or `recognize-vertical` |
| POST | `/translate` |
| POST | `/export/{format}` with `png` or `html` |

The worker accepts one image up to 16 MiB at a time. Export accepts at most 64 MiB total in multipart form. When an Edge request limit is lower, report the limit to the caller, and continue to use the existing Owner session and artifact download authorization. The standalone reader runs from the downloaded file and uses no routes.
