# DeepSeek V4 Flash model package

Adds the pinned checkpoint recipe and Scope Pack needed to download and prepare
DeepSeek V4 Flash in AI2Apps/oMLX.

This release binds the published SSD-ready checkpoint. The expert store is activated in place without a second conversion copy.

Version 0.3.4 declares DeepSeek V4 Flash as a required-reasoning model and
ships the Package-owned chat template that opens generation with `<think>`.
It requires Runtime 1.7.5 or later so reasoning is transported separately from
the visible answer even when a client requests Thinking Off.
