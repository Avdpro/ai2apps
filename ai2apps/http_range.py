"""Strict validation for immutable single-range HTTP responses."""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

_CONTENT_RANGE = re.compile(r"^bytes (\d+)-(\d+)/(\d+)$")


class StrictRangeResponseError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class StrictRangeResponse:
    total_size: int
    length: int
    transport_mode: str


def validate_strict_range_response_headers(
    response: httpx.Response,
    *,
    start: int,
    end: int,
    expected_total: int | None,
    allow_http_200: bool,
) -> StrictRangeResponse:
    """Validate headers before a bounded response body is consumed."""

    if start < 0 or end < start:
        raise ValueError("requested byte range is invalid")
    if response.status_code == 206:
        transport_mode = "http-206"
    elif response.status_code == 200:
        if not allow_http_200:
            raise StrictRangeResponseError(
                "range_source_not_eligible",
                "HTTP 200 range compatibility is not enabled for this source",
            )
        transport_mode = "http-200-content-range"
    else:
        raise StrictRangeResponseError(
            "range_status_unsupported",
            f"Range source returned HTTP {response.status_code}",
        )

    content_ranges = response.headers.get_list("content-range")
    if not content_ranges:
        raise StrictRangeResponseError(
            "content_range_missing", "Range response omitted Content-Range"
        )
    if len(content_ranges) != 1 or "," in content_ranges[0]:
        raise StrictRangeResponseError(
            "content_range_malformed", "Range response has multiple ranges"
        )
    match = _CONTENT_RANGE.fullmatch(content_ranges[0])
    if match is None:
        raise StrictRangeResponseError(
            "content_range_malformed", "Range response has invalid Content-Range"
        )
    actual_start, actual_end, total_size = (
        int(value) for value in match.groups()
    )
    if actual_start != start or actual_end != end:
        raise StrictRangeResponseError(
            "content_range_mismatch", "Range response returned different offsets"
        )
    if total_size <= end or (
        expected_total is not None and total_size != expected_total
    ):
        raise StrictRangeResponseError(
            "range_total_mismatch", "Range response returned a different total size"
        )

    expected_length = end - start + 1
    content_lengths = response.headers.get_list("content-length")
    if (
        len(content_lengths) != 1
        or not content_lengths[0].isdigit()
        or int(content_lengths[0]) != expected_length
    ):
        raise StrictRangeResponseError(
            "range_length_mismatch", "Range response returned a different length"
        )

    encodings = response.headers.get_list("content-encoding")
    if len(encodings) > 1 or (
        encodings and encodings[0].strip().lower() not in {"", "identity"}
    ):
        raise StrictRangeResponseError(
            "content_encoding_invalid", "Range response transformed signed bytes"
        )
    content_types = response.headers.get_list("content-type")
    if len(content_types) > 1 or any(
        value.split(";", 1)[0].strip().lower() == "multipart/byteranges"
        for value in content_types
    ):
        raise StrictRangeResponseError(
            "range_multipart_rejected", "Multipart range responses are not supported"
        )

    return StrictRangeResponse(
        total_size=total_size,
        length=expected_length,
        transport_mode=transport_mode,
    )
