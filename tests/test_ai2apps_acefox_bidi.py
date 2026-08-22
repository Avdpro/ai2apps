from __future__ import annotations

from ai2apps.acefox_bidi import AceFoxAgentEndpoint


def test_acefox_endpoint_preserves_validated_helper_contract() -> None:
    result = {
        "profile_id": "a" * 64,
        "pid": 42,
        "automation": {
            "web_socket_url": "ws://127.0.0.1:49152/session",
            "authorization": "Bearer " + "b" * 64,
        },
    }
    endpoint = AceFoxAgentEndpoint.from_helper_result(result)
    assert endpoint.pid == 42
    assert endpoint.profile_id == "a" * 64
    assert endpoint.web_socket_url.endswith(":49152/session")
