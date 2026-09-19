"""Dependency-light CTC forced-alignment primitives."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TokenAlignment:
    token_index: int
    start: float
    end: float
    score: float


def log_softmax(values: np.ndarray) -> np.ndarray:
    maximum = np.max(values, axis=-1, keepdims=True)
    shifted = values - maximum
    return shifted - np.log(np.sum(np.exp(shifted), axis=-1, keepdims=True))


def ctc_viterbi_align(
    log_probabilities: np.ndarray,
    tokens: list[int],
    *,
    duration: float,
    blank_id: int = 0,
) -> list[TokenAlignment]:
    """Find the highest-scoring CTC path constrained to ``tokens``.

    The returned list contains one time span per target token. It is suitable
    for aggregating character-level CTC paths into word boundaries.
    """

    emissions = np.asarray(log_probabilities, dtype=np.float64)
    if emissions.ndim != 2:
        raise ValueError("CTC emissions must have shape [frames, vocabulary]")
    if not tokens:
        return []
    if duration <= 0:
        raise ValueError("Alignment duration must be positive")
    frames, vocabulary = emissions.shape
    if any(token < 0 or token >= vocabulary for token in tokens):
        raise ValueError("Target token is outside the CTC vocabulary")

    states = 2 * len(tokens) + 1
    negative_infinity = -np.inf
    previous = np.full(states, negative_infinity, dtype=np.float64)
    previous[0] = emissions[0, blank_id]
    previous[1] = emissions[0, tokens[0]]
    backpointers = np.full((frames, states), -1, dtype=np.int32)

    for frame in range(1, frames):
        current = np.full(states, negative_infinity, dtype=np.float64)
        for state in range(states):
            candidates = [(previous[state], state)]
            if state > 0:
                candidates.append((previous[state - 1], state - 1))
            if state > 1 and state % 2 == 1:
                token_index = state // 2
                if tokens[token_index] != tokens[token_index - 1]:
                    candidates.append((previous[state - 2], state - 2))
            best_score, best_state = max(candidates, key=lambda item: item[0])
            emitted = blank_id if state % 2 == 0 else tokens[state // 2]
            current[state] = best_score + emissions[frame, emitted]
            backpointers[frame, state] = best_state
        previous = current

    final_candidates = [(previous[states - 1], states - 1)]
    if states > 1:
        final_candidates.append((previous[states - 2], states - 2))
    final_score, state = max(final_candidates, key=lambda item: item[0])
    if not np.isfinite(final_score):
        raise ValueError(
            f"No valid CTC path for {len(tokens)} tokens across {frames} frames"
        )

    path = np.empty(frames, dtype=np.int32)
    for frame in range(frames - 1, -1, -1):
        path[frame] = state
        if frame:
            state = int(backpointers[frame, state])
            if state < 0:
                raise ValueError("CTC backtracking reached an invalid state")

    seconds_per_frame = duration / frames
    aligned: list[TokenAlignment] = []
    for token_index, token in enumerate(tokens):
        token_state = 2 * token_index + 1
        token_frames = np.flatnonzero(path == token_state)
        if not len(token_frames):
            raise ValueError(f"CTC path did not visit target token {token_index}")
        scores = np.exp(emissions[token_frames, token])
        aligned.append(
            TokenAlignment(
                token_index=token_index,
                start=float(token_frames[0] * seconds_per_frame),
                end=float((token_frames[-1] + 1) * seconds_per_frame),
                score=float(np.mean(scores)),
            )
        )
    return aligned
