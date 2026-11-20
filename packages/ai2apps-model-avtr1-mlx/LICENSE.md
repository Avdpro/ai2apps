# **AVTR-1 Repository**

## *License Notice and Component Map*

| Repository owner | Goodsize Inc. |
| :---- | :---- |
| **Repository** | https://github.com/avaturn-live/avtr-1 |
| **Effective date** | May 20, 2026 |
| **Components** | AVTR-1 model, Avaturn Renderer, and Avaturn Streamer (separately licensed) |
| **Contact** | hello@avaturn.me |

# **Overview**

This repository contains **three separately licensed components**. Different files are governed by different terms. Read this notice and the individual license files before using, copying, modifying, or distributing any part of this repository. The AVTR-1 **weights** themselves are distributed separately at [avaturn-live/avtr-1](https://huggingface.co/avaturn-live/avtr-1) and are governed by LICENSE-MODEL.md.

# **Component Map**

| Path | Component | License | License file |
| :---- | :---- | :---- | :---- |
| **src/avtr1_renderer/** | Avaturn Renderer — model inference pipeline (motion generator, face encoder/decoder, audio encoder, warp, stitch) | PolyForm Noncommercial License 1.0.0 with Required Notice | LICENSE-RENDERER.md |
| **src/avaturn_live_streamer/** | Avaturn Streamer — orchestration backend (audio scheduler, drift-compensated stream clock, frame-accurate event emission, dual-stream rendering coordination) | PolyForm Noncommercial License 1.0.0 with Required Notice | LICENSE-STREAMER.md and PATENTS.md |
| **scripts/** | Build and demo tooling (engine builders, artifact downloader, demo runners) | AVTR-1 Community License Agreement | LICENSE-MODEL.md |

*Top-level files (this notice, README, configuration files) are licensed under the AVTR-1 Community License Agreement unless they primarily document one of the noncommercial components, in which case they take that component's license.*

# **Key Consequences of the Multi-License Structure**

## **1\. The licenses are independent.**

The AVTR-1 Community License, the Renderer license, and the Streamer license each grant rights only to their own component. Compliance with one does not establish compliance with the others. If you use more than one component, you must comply with each applicable license.

## **2\. Commercial use thresholds are different.**

**AVTR-1 model:** the AVTR-1 Community License permits use, including commercial use, by Entities with annual revenue **below USD 10,000,000**, subject to the use restrictions in Attachment A of LICENSE-MODEL.md. Entities at or above USD 10,000,000 in annual revenue must obtain a separate **Commercial Use Agreement** from Goodsize Inc. before any commercial use.

**Renderer:** the Renderer license permits **no commercial use of any kind**, regardless of the licensee’s revenue. Any commercial use of the Renderer — including by sub-USD 10,000,000 entities — requires a separate written **Renderer Commercial License**.

**Streamer:** the Streamer license permits **no commercial use of any kind**, regardless of the licensee’s revenue. Any commercial use of the Streamer — including by sub-USD 10,000,000 entities — requires a separate written **Streamer Commercial License**.

## **3\. Patents.**

The Streamer is patent-pending. The patent license granted under the PolyForm Noncommercial License is narrow: it covers only use of the Streamer in the form distributed by Goodsize Inc., for noncommercial purposes only, and does not transfer or assign ownership of any patent. Independent reimplementation of the claimed inventions, or any commercial practice of them, requires a separate commercial license. See the Patent Notice and Reservation of Rights document for the full notice and reservation of rights.

## **4\. Trademarks.**

Neither license grants any right to use the “Avaturn,” “AVTR-1,” “Goodsize,” or related marks except to the extent required by attribution and notice obligations.

## **5\. Output.**

The AVTR-1 license addresses ownership of model outputs and use restrictions on those outputs (see Sections 5 and Attachment A of LICENSE-MODEL.md). The Streamer does not generate outputs in the same sense; it orchestrates real-time avatar rendering and is licensed only for noncommercial deployment.

# **If You Are a Noncommercial User**

You may, subject to the terms of each license:

* use the AVTR-1 model under LICENSE-MODEL.md, subject to the use restrictions in Attachment A;

* use the Renderer under LICENSE-RENDERER.md, subject to the noncommercial limitation and the Required Notice; and

* use the Streamer under LICENSE-STREAMER.md, subject to the noncommercial limitation, the Required Notice, and the patent reservation in the Patent Notice.

You must preserve all license, notice, and patent files in any redistribution.

# **If You Are a Commercial User**

Contact hello@avaturn.me (or visit https://avaturn.live/licensing) to obtain the licenses you need. Most commercial deployments require all three:

1. the AVTR-1 Commercial Use Agreement (if the licensing Entity has annual revenue at or above USD 10,000,000);

2. the Renderer Commercial License (required regardless of revenue if the Renderer is used commercially); and

3. the Streamer Commercial License (required regardless of revenue if the Streamer is used commercially).

Commercial licenses are negotiated on a per-deployment basis.

# **Contacts**

All inquiries — licensing, legal notices, and security disclosures — go to a single address:

**hello@avaturn.me**

# **Disclaimer**

This notice is provided for the convenience of users. In the event of any conflict between this notice and the underlying license files (LICENSE-MODEL.md, LICENSE-RENDERER.md, LICENSE-STREAMER.md, Patent Notice and Reservation of Rights), the underlying license files control.

*Copyright (c) 2026 Goodsize Inc. All rights reserved. Last updated: May 17, 2026\.*