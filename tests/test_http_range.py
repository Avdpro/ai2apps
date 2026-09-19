from __future__ import annotations

import httpx
import pytest

from ai2apps.http_range import (
    StrictRangeResponseError,
    validate_strict_range_response_headers,
)


def _response(status: int = 206, **headers: str) -> httpx.Response:
    defaults = {
        "Content-Range": "bytes 2-5/10",
        "Content-Length": "4",
        "Content-Encoding": "identity",
    }
    defaults.update(headers)
    return httpx.Response(status, headers=defaults)


@pytest.mark.parametrize("status", [200, 206])
def test_strict_range_headers_accept_exact_single_range(status: int) -> None:
    result = validate_strict_range_response_headers(
        _response(status),
        start=2,
        end=5,
        expected_total=10,
        allow_http_200=True,
    )

    assert result.total_size == 10
    assert result.length == 4
    assert result.transport_mode == (
        "http-206" if status == 206 else "http-200-content-range"
    )


@pytest.mark.parametrize(
    ("response", "allow_http_200", "code"),
    [
        (_response(200), False, "range_source_not_eligible"),
        (
            _response(200, **{"Content-Range": "bytes 1-5/10"}),
            True,
            "content_range_mismatch",
        ),
        (
            _response(200, **{"Content-Range": "bytes 2-5/11"}),
            True,
            "range_total_mismatch",
        ),
        (
            _response(200, **{"Content-Length": "5"}),
            True,
            "range_length_mismatch",
        ),
        (
            _response(200, **{"Content-Encoding": "gzip"}),
            True,
            "content_encoding_invalid",
        ),
        (
            _response(200, **{"Content-Type": "multipart/byteranges"}),
            True,
            "range_multipart_rejected",
        ),
    ],
)
def test_strict_range_headers_reject_invalid_responses(
    response: httpx.Response,
    allow_http_200: bool,
    code: str,
) -> None:
    with pytest.raises(StrictRangeResponseError) as raised:
        validate_strict_range_response_headers(
            response,
            start=2,
            end=5,
            expected_total=10,
            allow_http_200=allow_http_200,
        )

    assert raised.value.code == code
