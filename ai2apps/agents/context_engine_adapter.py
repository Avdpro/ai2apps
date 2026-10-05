"""Small host bridge: checkpoint round groups -> independent context-engine nodes.

Byte admission is explicitly a fallback; no bytes-to-token conversion is made.
The aggregate nodes preserve the host's already-validated complete Tool rounds.
"""

from ai2apps.context_engine import (
    VERSION,
    Node,
    Policy,
    Route,
    SummaryError,
    Surface,
    prepare,
    prepare_range,
    replacement,
)


class RoundMeter:
    unit = "utf8_bytes"

    def __init__(self, envelope=0):
        self.overhead = envelope

    def node(self, node, route):
        return len(node.body["content"].encode())

    def envelope(self, surface, route):
        return self.overhead


def _surface(groups, run_id, encode):
    return Surface(
        run_id,
        tuple(
            Node.message(
                str(i),
                {"role": "assistant", "content": encode(group)},
                pinned=i >= len(groups) - 2,
            )
            for i, group in enumerate(groups)
        ),
    )


def compactable_end(groups, covered, *, request_bytes, max_bytes, run_id, encode, force=False):
    remaining = groups[covered:]
    if len(remaining) <= 2 or max_bytes < 2:
        return covered
    surface = _surface(remaining, run_id, encode)
    meter = RoundMeter()
    meter.overhead = max(
        0, request_bytes - sum(meter.node(n, None) for n in surface.nodes)
    )
    route = Route(
        "ai2apps-byte-admission", "serialized-request", max_bytes, unit="utf8_bytes"
    )
    policy = Policy(
        threshold_ratio=0.75, headroom=0, retain_ratio=0.16, summary_output=2048
    )
    selected = prepare(surface, route, meter, policy, "manual" if force else "pressure")
    return covered if selected is None else covered + len(selected.source)


def validates_replacement(groups, count, candidate, *, run_id, encode):
    surface = _surface(groups, run_id, encode)
    route = Route(
        "ai2apps-byte-admission", "serialized-request", 524288, unit="utf8_bytes"
    )
    meter = RoundMeter()
    try:
        selected = prepare_range(surface, route, meter, 0, count)
        replacement(selected, surface, Node.message("checkpoint", candidate), meter)
    except (ValueError, SummaryError):
        return False
    return True


ENGINE_AUDIT = {
    "engine": VERSION,
    "measurement_unit": "utf8_bytes",
    "token_count_exact": False,
}
