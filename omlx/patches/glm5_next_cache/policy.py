"""Host-side per-layer SLRU policy for the GLM-5 dynamic L1.

The policy owns tags only.  A caller first obtains an immutable admission plan,
writes every missed expert into the reserved physical slots, and publishes the
plan only after the writes have completed.  This keeps a failed or partial SSD
read from making a tag visible before its weights.
"""

from __future__ import annotations

from dataclasses import dataclass

EMPTY = 0
PROBATION = 1
PROTECTED = 2


@dataclass
class LayerState:
    expert_ids: list[int]
    segments: list[int]
    last_used: list[int]
    clock: int = 0

    def clone(self) -> LayerState:
        return LayerState(
            list(self.expert_ids),
            list(self.segments),
            list(self.last_used),
            self.clock,
        )


@dataclass(frozen=True)
class AdmissionPlan:
    requested: tuple[int, ...]
    missing: tuple[int, ...]
    slots: tuple[int, ...]
    next_state: LayerState


class DynamicL1Policy:
    """A fixed-capacity, batch-pinned segmented LRU.

    New entries enter the probation segment.  A subsequent hit promotes an
    entry to protected; when protected is full, its least-recently-used entry
    is demoted.  Victim order is empty, probation LRU, then protected LRU.
    Every resident member of the current Top-K batch is pinned until all miss
    slots have been reserved.
    """

    def __init__(
        self,
        *,
        capacity: int = 80,
        num_experts: int = 288,
        protected_ratio: float = 0.70,
    ) -> None:
        if capacity < 1:
            raise ValueError("dynamic L1 capacity must be positive")
        if num_experts < capacity:
            raise ValueError("expert universe cannot be smaller than L1")
        if not 0.0 <= protected_ratio <= 1.0:
            raise ValueError("protected ratio must be in [0, 1]")
        self.capacity = capacity
        self.num_experts = num_experts
        protected = int(capacity * protected_ratio)
        self.protected_capacity = max(0, min(capacity - 1, protected))
        self._layers: dict[int, LayerState] = {}

    def _state(self, layer: int) -> LayerState:
        return self._layers.setdefault(
            layer,
            LayerState(
                expert_ids=[-1] * self.capacity,
                segments=[EMPTY] * self.capacity,
                last_used=[0] * self.capacity,
            ),
        )

    def state(self, layer: int) -> LayerState:
        """Return a detached snapshot suitable for telemetry and tests."""

        return self._state(layer).clone()

    @staticmethod
    def _unique(values: tuple[int, ...] | list[int]) -> tuple[int, ...]:
        return tuple(dict.fromkeys(int(value) for value in values))

    def _touch(self, state: LayerState, slot: int) -> None:
        state.clock += 1
        state.last_used[slot] = state.clock
        if state.segments[slot] != PROBATION or self.protected_capacity == 0:
            return
        protected = [
            index
            for index, segment in enumerate(state.segments)
            if segment == PROTECTED
        ]
        if len(protected) >= self.protected_capacity:
            demote = min(protected, key=lambda index: state.last_used[index])
            state.segments[demote] = PROBATION
        state.segments[slot] = PROTECTED

    @staticmethod
    def _victim_key(state: LayerState, slot: int) -> tuple[int, int]:
        segment = state.segments[slot]
        rank = 0 if segment == EMPTY else 1 if segment == PROBATION else 2
        return rank, state.last_used[slot]

    def plan(self, layer: int, requested: tuple[int, ...] | list[int]) -> AdmissionPlan:
        ids = self._unique(requested)
        if not ids:
            raise ValueError("dynamic L1 request cannot be empty")
        if len(ids) > self.capacity:
            raise ValueError("dynamic L1 request exceeds layer capacity")
        if min(ids) < 0 or max(ids) >= self.num_experts:
            raise ValueError("dynamic L1 request has an invalid expert ID")

        next_state = self._state(layer).clone()
        slots_by_expert = {
            expert: slot
            for slot, expert in enumerate(next_state.expert_ids)
            if expert >= 0
        }
        pinned = {
            slots_by_expert[expert] for expert in ids if expert in slots_by_expert
        }
        for expert in ids:
            slot = slots_by_expert.get(expert)
            if slot is not None:
                self._touch(next_state, slot)

        missing: list[int] = []
        reserved: list[int] = []
        for expert in ids:
            if expert in slots_by_expert:
                continue
            candidates = [
                slot
                for slot in range(self.capacity)
                if slot not in pinned and slot not in reserved
            ]
            if not candidates:
                raise RuntimeError("dynamic L1 has no unpinned victim")
            victim = min(
                candidates, key=lambda slot: self._victim_key(next_state, slot)
            )
            evicted = next_state.expert_ids[victim]
            if evicted >= 0:
                slots_by_expert.pop(evicted, None)
            next_state.clock += 1
            next_state.expert_ids[victim] = expert
            next_state.segments[victim] = PROBATION
            next_state.last_used[victim] = next_state.clock
            slots_by_expert[expert] = victim
            missing.append(expert)
            reserved.append(victim)

        return AdmissionPlan(ids, tuple(missing), tuple(reserved), next_state)

    def publish(self, layer: int, plan: AdmissionPlan) -> None:
        current = self._state(layer)
        # Plans are serialized by the runtime lock.  This guard catches an
        # accidental stale publication without coupling policy to MLX.
        if plan.next_state.clock < current.clock:
            raise RuntimeError("refusing to publish a stale dynamic L1 plan")
        self._layers[layer] = plan.next_state.clone()

    def install(self, layer: int, state: LayerState) -> None:
        """Install a fully materialized state after an external transaction."""

        if not (
            len(state.expert_ids)
            == len(state.segments)
            == len(state.last_used)
            == self.capacity
        ):
            raise ValueError("dynamic L1 state has the wrong capacity")
        resident = [expert for expert in state.expert_ids if expert >= 0]
        if len(resident) != len(set(resident)):
            raise ValueError("dynamic L1 state contains duplicate experts")
        if resident and (min(resident) < 0 or max(resident) >= self.num_experts):
            raise ValueError("dynamic L1 state contains an invalid expert")
        self._layers[layer] = state.clone()

    def lookup(self, layer: int) -> tuple[int, ...]:
        values = [-1] * self.num_experts
        for slot, expert in enumerate(self._state(layer).expert_ids):
            if expert >= 0:
                values[expert] = slot
        return tuple(values)

    def observe_slot_counts(self, layer: int, counts: tuple[int, ...]) -> None:
        """Merge device-accumulated all-hit use without changing any tags."""

        if len(counts) != self.capacity or min(counts, default=0) < 0:
            raise ValueError("dynamic L1 slot counters have an invalid shape")
        state = self._state(layer).clone()
        # Aggregate counters do not preserve route order. Apply colder slots
        # first so the most frequently used slot receives the newest clock.
        active = sorted(
            (count, slot)
            for slot, count in enumerate(counts)
            if count and state.expert_ids[slot] >= 0
        )
        for count, slot in active:
            self._touch(state, slot)
            if count > 1:
                state.clock += count - 1
                state.last_used[slot] = state.clock
        self._layers[layer] = state

    def replay(self, layer: int, batches: list[tuple[int, ...]]) -> LayerState:
        """Replay observed Top-K batches without performing any weight I/O."""

        for batch in batches:
            plan = self.plan(layer, batch)
            self.publish(layer, plan)
        return self.state(layer)
