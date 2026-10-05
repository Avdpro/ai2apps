"""Host-independent Python port of DeepSeek's pressure/retention transaction rules.

Derived from deepseek-ai/deepseek-harness 5badb150, MIT, Copyright 2026 DeepSeek.
Host adapters supply measurement, immutable surfaces, summarization and storage.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
from dataclasses import dataclass
from typing import Protocol

VERSION = "deepseek-context-python/1"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class Node:
    id: str
    body_json: str
    pinned: bool = False

    @classmethod
    def message(cls, identifier, message, pinned=False):
        return cls(identifier, canonical(message), pinned)

    @property
    def body(self):
        return json.loads(self.body_json)


@dataclass(frozen=True)
class Surface:
    session_id: str
    nodes: tuple[Node, ...]

    def __post_init__(self):
        if len({n.id for n in self.nodes}) != len(self.nodes):
            raise ValueError("Surface node IDs must be unique")


@dataclass(frozen=True)
class Route:
    provider: str
    model: str
    capacity: int
    output_reservation: int = 0
    unit: str = "tokens"

    def __post_init__(self):
        if type(self.capacity) is not int or self.capacity <= 0:
            raise ValueError("Positive routed capacity required")
        if (
            type(self.output_reservation) is not int
            or not 0 <= self.output_reservation < self.capacity
        ):
            raise ValueError("Output reservation leaves no input capacity")
        if self.unit not in {"tokens", "utf8_bytes"}:
            raise ValueError("Unknown measurement unit")
        if not self.provider or not self.model:
            raise ValueError("An explicit provider/model route is required")


@dataclass(frozen=True)
class Policy:
    threshold_ratio: float = 0.8
    headroom: int = 65536
    retain_ratio: float | None = 0.16
    retain_units: int | None = None
    summary_output: int = 65536
    compaction_retries: int = 1
    overflow_retries: int = 1

    def __post_init__(self):
        if (
            isinstance(self.threshold_ratio, bool)
            or not isinstance(self.threshold_ratio, (float, int))
            or not 0 < self.threshold_ratio < 1
        ):
            raise ValueError("Threshold ratio must lie between zero and one")
        if self.retain_units is None and (
            self.retain_ratio is None
            or not 0 <= self.retain_ratio < self.threshold_ratio
        ):
            raise ValueError("Retention ratio must be below pressure ratio")
        for key in ("headroom", "compaction_retries", "overflow_retries"):
            if type(getattr(self, key)) is not int or getattr(self, key) < 0:
                raise ValueError(f"{key} must be a nonnegative integer")
        if type(self.summary_output) is not int or self.summary_output <= 0:
            raise ValueError("Summary output cap must be positive")
        if self.retain_units is not None and (
            type(self.retain_units) is not int or self.retain_units < 0
        ):
            raise ValueError("Retention units must be nonnegative")

    def budgets(self, route):
        available = route.capacity - route.output_reservation
        threshold = math.floor(
            min(route.capacity * self.threshold_ratio, available - self.headroom)
        )
        retention = (
            self.retain_units
            if self.retain_units is not None
            else math.floor(available * self.retain_ratio)
        )
        if threshold <= 0 or retention >= threshold:
            raise ValueError(
                "Routed output/headroom/retention policy leaves no pressure budget"
            )
        return threshold, retention


DEFAULT_POLICY = Policy()


class Meter(Protocol):
    unit: str

    def node(self, node: Node, route: Route) -> int: ...
    def envelope(self, surface: Surface, route: Route) -> int: ...


class Utf8Meter:
    """Explicit byte fallback. This is never reported as token counting."""

    unit = "utf8_bytes"

    def node(self, node, route):
        return len(node.body_json.encode())

    def envelope(self, surface, route):
        return 0


def costs(surface, route, meter):
    if meter.unit != route.unit:
        raise ValueError("Meter and route units differ")
    values = tuple(meter.node(n, route) for n in surface.nodes)
    envelope = meter.envelope(surface, route)
    if any(type(v) is not int or v < 0 for v in (*values, envelope)):
        raise ValueError("Meter returned invalid costs")
    return values, sum(values) + envelope


def balanced_cuts(surface):
    """Validate actual call IDs, strengthening upstream's count-only balance fold."""
    pending = set()
    result = [True]
    for node in surface.nodes:
        message = node.body
        calls = message.get("tool_calls") or []
        if calls and message.get("role") != "assistant":
            raise ValueError("Tool calls require assistant messages")
        for call in calls:
            identifier = call.get("id")
            if (
                not isinstance(identifier, str)
                or not identifier
                or identifier in pending
            ):
                raise ValueError("Invalid or duplicate pending Tool call")
            pending.add(identifier)
        if message.get("role") == "tool":
            identifier = message.get("tool_call_id")
            if identifier not in pending:
                raise ValueError("Orphan or duplicate Tool result")
            pending.remove(identifier)
        result.append(not pending)
    return tuple(result)


@dataclass(frozen=True)
class Prepared:
    session_id: str
    source: tuple[Node, ...]
    before: tuple[str, ...]
    after: tuple[str, ...]
    route: Route
    source_cost: int
    source_sha256: str


def prepare(surface, route, meter, policy=DEFAULT_POLICY, trigger="pressure"):
    if trigger not in {"pressure", "context-overflow", "manual"}:
        raise ValueError("Unknown compaction trigger")
    values, total = costs(surface, route, meter)
    if trigger == "pressure":
        threshold, retention = policy.budgets(route)
        if total < threshold:
            return None
    else:
        retention = 0
    cuts = balanced_cuts(surface)
    start = 0
    while start < len(surface.nodes) and (
        surface.nodes[start].pinned or surface.nodes[start].body.get("role") == "system"
    ):
        start += 1
    if start == len(surface.nodes) or not cuts[start]:
        return None
    keep, accumulated = len(surface.nodes), 0
    # Matches upstream: even retain=0 retains the newest surface node.
    for i in range(len(values) - 1, -1, -1):
        accumulated += values[i]
        keep = i
        if accumulated >= retention:
            break
    first_pinned = next(
        (i for i in range(start, keep) if surface.nodes[i].pinned), keep
    )
    keep = min(keep, first_pinned)
    while keep > start and not cuts[keep]:
        keep -= 1
    if keep <= start:
        return None
    source = surface.nodes[start:keep]
    return Prepared(
        surface.session_id,
        source,
        tuple(n.id for n in surface.nodes[:start]),
        tuple(n.id for n in surface.nodes[keep:]),
        route,
        sum(values[start:keep]),
        hashlib.sha256(canonical([n.body_json for n in source]).encode()).hexdigest(),
    )


class ChangedError(RuntimeError):
    pass


class SummaryError(RuntimeError):
    pass


class BusyError(RuntimeError):
    pass


def replacement(prepared, current, summary, meter):
    """Selected-span CAS allows unrelated appends, rejects changed sources or route."""
    if current.session_id != prepared.session_id:
        raise ChangedError("Session changed")
    ids = [n.id for n in current.nodes]
    try:
        start = ids.index(prepared.source[0].id)
    except ValueError as error:
        raise ChangedError("Selected source disappeared") from error
    end = start + len(prepared.source)
    if current.nodes[start:end] != prepared.source:
        raise ChangedError("Selected span changed during summarization")
    if tuple(ids[:start]) != prepared.before:
        raise ChangedError("Source boundary changed")
    if tuple(ids[end : end + len(prepared.after)]) != prepared.after:
        raise ChangedError("Retained boundary changed")
    cuts = balanced_cuts(current)
    if not cuts[start] or not cuts[end]:
        raise ChangedError("Tool pairing changed")
    if (
        summary.pinned
        or summary.body.get("tool_calls")
        or summary.body.get("role") not in {"assistant", "user"}
    ):
        raise SummaryError("Summary must be a nonprivileged text checkpoint")
    if (
        not isinstance(summary.body.get("content"), str)
        or not summary.body["content"].strip()
    ):
        raise SummaryError("Empty or non-text summary")
    if meter.node(summary, prepared.route) >= prepared.source_cost:
        raise SummaryError("Summary does not reduce routed context cost")
    projected = Surface(
        current.session_id, current.nodes[:start] + (summary,) + current.nodes[end:]
    )
    return projected


class Store(Protocol):
    """commit must atomically CAS source/route, replace surface and close journal lock."""

    def snapshot(self) -> Surface: ...
    def route(self) -> Route: ...
    def begin(self, prepared: Prepared) -> str: ...
    def commit(
        self, transaction: str, prepared: Prepared, summary: Node, meter: Meter
    ) -> Surface: ...
    def fail(self, transaction: str, code: str) -> None: ...


async def compact(store, meter, summarize, policy=DEFAULT_POLICY, trigger="pressure"):
    """A bounded transaction; source remains intact on any summary/commit failure."""
    results = []
    limit = policy.compaction_retries + 1 if trigger == "pressure" else 1
    for _ in range(limit):
        snapshot, route = store.snapshot(), store.route()
        selected = prepare(snapshot, route, meter, policy, trigger)
        if selected is None:
            return tuple(results)
        transaction = store.begin(selected)
        try:
            summary = await summarize(selected, policy.summary_output)
            if store.route() != route:
                raise ChangedError("Routed model changed")
            replacement(selected, store.snapshot(), summary, meter)
            projected = store.commit(transaction, selected, summary, meter)
            results.append(projected)
        except asyncio.CancelledError:
            store.fail(transaction, "cancelled")
            raise
        except Exception:
            store.fail(transaction, "failed")
            raise
        if (
            trigger != "pressure"
            or costs(projected, route, meter)[1] < policy.budgets(route)[0]
        ):
            return tuple(results)
    raise SummaryError("Pressure remains above threshold after bounded compaction")


async def with_overflow_recovery(call, recover, retries=1):
    """Retry only provider-confirmed overflow and only after durable progress."""
    if type(retries) is not int or retries < 0:
        raise ValueError("Invalid overflow retry budget")
    for attempt in range(retries + 1):
        try:
            return await call()
        except ContextOverflowError:
            if attempt >= retries or not await recover():
                raise


class ContextOverflowError(RuntimeError):
    pass


def prepare_range(surface, route, meter, start, end):
    """Explicit half-open range contract for checkpoint-replay host adapters."""
    if (
        type(start) is not int
        or type(end) is not int
        or not 0 <= start < end <= len(surface.nodes)
    ):
        raise ValueError("Invalid surface range")
    values, _ = costs(surface, route, meter)
    cuts = balanced_cuts(surface)
    source = surface.nodes[start:end]
    if (
        not cuts[start]
        or not cuts[end]
        or any(n.pinned or n.body.get("role") == "system" for n in source)
    ):
        raise ValueError("Range crosses a protected or unbalanced boundary")
    return Prepared(
        surface.session_id,
        source,
        tuple(n.id for n in surface.nodes[:start]),
        tuple(n.id for n in surface.nodes[end:]),
        route,
        sum(values[start:end]),
        hashlib.sha256(canonical([n.body_json for n in source]).encode()).hexdigest(),
    )


@dataclass(frozen=True)
class Policies:
    default: Policy = Policy()
    overrides: tuple[tuple[str, str, Policy], ...] = ()

    def __post_init__(self):
        targets = [(p, m) for p, m, _ in self.overrides]
        if len(set(targets)) != len(targets) or any(not p or not m for p, m in targets):
            raise ValueError("Duplicate or empty policy route")

    def resolve(self, route):
        return next(
            (
                policy
                for p, m, policy in self.overrides
                if (p, m) == (route.provider, route.model)
            ),
            self.default,
        )
