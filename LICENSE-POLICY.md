# AI2Apps license policy

This repository is a multi-license distribution. A file-level license notice
takes precedence over the repository default.

## Apache-2.0 default

Except for the files listed below and third-party material carrying its own
notice, the source code in this repository is licensed under the Apache
License, Version 2.0, in [`LICENSE`](LICENSE).

## AI2Apps Official Cloud Connector

The following files, for versions first distributed on or after 2026-09-07,
are licensed under the Business Source License 1.1 with the AI2Apps Official
Cloud Additional Use Grant in
[`LICENSES/AI2APPS-CLOUD-CONNECTOR-BSL-1.1.md`](LICENSES/AI2APPS-CLOUD-CONNECTOR-BSL-1.1.md):

- `ai2apps/api/cloud.py`
- `ai2apps/cloud_client.py`
- `ai2apps/cloud_gateway.py`
- `ai2apps/cloud_requests.py`
- `ai2apps/model_sharing/cloud.py`

Production use of those files is free when they are used by a client to
connect exclusively to an Official AI2Apps Cloud Service. A separate
commercial license is required to use them to implement, enable, connect to,
or provide an Alternative Cloud Service. Non-production use remains available
under the standard Business Source License 1.1 terms.

Each covered version changes to Apache-2.0 on the Change Date specified in its
Business Source License parameters. For this version, the Change Date is
2029-09-07.

Before the first public distribution of a later Connector version, its release
owner must update the Licensed Work version and set a new Change Date 36 months
after that version's planned first-publication date. A release must not shorten
the source-available period below 24 months.

Versions previously distributed under Apache-2.0 remain available under the
license terms that accompanied those versions. This policy does not withdraw
rights already granted for an earlier distribution.

## Third-party material

Third-party libraries, browser sources, model code, model weights, data, and
other bundled material may use different licenses. Their local license and
attribution notices control. In particular, Firefox/AceFox-derived source is
generally subject to MPL-2.0 and its bundled third-party notices.

## Trademarks

No software license in this repository grants trademark rights. See
[`TRADEMARKS.md`](TRADEMARKS.md).
