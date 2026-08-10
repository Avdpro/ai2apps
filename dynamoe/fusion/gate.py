"""Adaptive review gate for Fusion turns."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Mapping, Sequence

from .types import FusionConfig, FusionRequest, GateDecision, GateSignals


_HIGH_RISK_PATTERNS = (
    r"\b(?:medical|diagnos|legal|lawsuit|financial|investment|dosage|safety)\b",
    r"(?:医疗|诊断|法律|诉讼|金融|投资|剂量|安全事故)",
)
_COMPLEX_PATTERNS = (
    r"\b(?:prove|derive|audit|debug|complete code|citation|calculate)\b",
    r"(?:证明|推导|审计|调试|完整代码|引用|计算)",
)


@dataclass(frozen=True)
class GateEvaluation:
    decision: GateDecision
    score: float
    prompt_risk: float
    reasons: tuple[str, ...]


class AdaptiveGate:
    def __init__(self, config: FusionConfig):
        self.config = config

    @staticmethod
    def _message_text(messages: Sequence[Mapping[str, object]]) -> str:
        parts: list[str] = []
        for message in messages:
            content = message.get("content", "")
            if isinstance(content, str):
                parts.append(content)
        return "\n".join(parts)

    @classmethod
    def estimate_prompt_risk(cls, request: FusionRequest) -> float:
        if request.prompt_risk is not None:
            return request.prompt_risk
        text = cls._message_text(request.messages).lower()
        score = 0.05
        if any(re.search(pattern, text) for pattern in _COMPLEX_PATTERNS):
            score += 0.30
        if any(re.search(pattern, text) for pattern in _HIGH_RISK_PATTERNS):
            score += 0.55
        if len(text) >= 4000:
            score += 0.15
        return min(score, 1.0)

    def evaluate(self, request: FusionRequest, signals: GateSignals) -> GateEvaluation:
        policy = self.config.gate_policy
        prompt_risk = self.estimate_prompt_risk(request)
        if policy == "off":
            return GateEvaluation(GateDecision.SKIP, 0.0, prompt_risk, ("policy_off",))
        if policy == "always":
            return GateEvaluation(
                GateDecision.FORCE, 1.0, prompt_risk, ("policy_always",)
            )

        reasons: list[str] = []
        if request.high_risk:
            reasons.append("request_high_risk")
        if signals.structural_failure:
            reasons.append("structural_failure")
        if signals.finish_reason == "length":
            reasons.append("length_capped")
        if reasons:
            return GateEvaluation(GateDecision.FORCE, 1.0, prompt_risk, tuple(reasons))

        score = 0.35 * prompt_risk
        if prompt_risk >= 0.5:
            reasons.append("prompt_risk")

        length_fraction = min(
            signals.output_tokens / max(self.config.long_output_tokens, 1), 1.0
        )
        score += 0.20 * length_fraction
        if length_fraction >= 1.0:
            reasons.append("long_output")

        uncertainty = 0.0
        if signals.mean_nll is not None:
            uncertainty = max(
                uncertainty,
                min(signals.mean_nll / self.config.mean_nll_threshold, 2.0) / 2.0,
            )
        if signals.tail_nll is not None:
            uncertainty = max(
                uncertainty,
                min(signals.tail_nll / self.config.mean_nll_threshold, 2.0) / 2.0,
            )
        if signals.p95_nll is not None:
            uncertainty = max(
                uncertainty,
                min(signals.p95_nll / self.config.mean_nll_threshold, 2.0) / 2.0,
            )
        if signals.low_confidence_ratio is not None:
            uncertainty = max(
                uncertainty,
                min(
                    signals.low_confidence_ratio
                    / self.config.low_confidence_ratio_threshold,
                    2.0,
                )
                / 2.0,
            )
        if signals.min_logit_margin is not None:
            margin_uncertainty = 1.0 - min(
                signals.min_logit_margin / self.config.min_margin_threshold, 1.0
            )
            uncertainty = max(uncertainty, margin_uncertainty)
        if signals.uncertainty_spikes:
            uncertainty = max(
                uncertainty, min(math.log2(signals.uncertainty_spikes + 1) / 4, 1.0)
            )
        if uncertainty:
            reasons.append("generation_uncertainty")
        score += 0.35 * uncertainty

        if signals.scope_confidence is not None:
            score += 0.10 * (1.0 - signals.scope_confidence)
            if signals.scope_confidence < 0.5:
                reasons.append("scope_uncertainty")

        score = min(score, 1.0)
        if score >= self.config.force_threshold:
            decision = GateDecision.FORCE
        elif score >= self.config.review_threshold:
            decision = GateDecision.REVIEW
        else:
            decision = GateDecision.SKIP
        return GateEvaluation(decision, score, prompt_risk, tuple(reasons))
