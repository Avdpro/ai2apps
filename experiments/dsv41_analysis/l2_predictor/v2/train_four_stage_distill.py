"""Distill saved Block6 router scores into one four-stage head."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
import numpy as np

from train_four_stage import ROOT, STAGES, StageHead, evaluate, load


BLOCK6_ROOT = Path("artifacts/dsv41-l2-prefetch-credit-development-20260916")


def load_teacher(plan: dict, stage_name: str, temperature: float) -> tuple[tuple[np.ndarray, ...], list[str]]:
    stage = STAGES[stage_name]
    targets = list(stage.targets)
    chunks = []
    sequences = []
    for sample in plan["samples"]:
        if sample["split"] != "validation":
            continue
        route_file = BLOCK6_ROOT / sample["id"] / "candidate" / "routing.npz"
        if not route_file.exists():
            continue
        with np.load(ROOT / "data" / sample["id"] / "supervision.npz") as data, np.load(route_file) as block6:
            assert np.array_equal(block6["actual"], data["top6"])
            if stage.trigger_layer is None:
                history = data["previous_ffn"][:, targets]
                trigger = data["hidden"]
                token = data["embedding"]
                final = data["hidden"]
                resident = data["resident"][:, targets]
                teacher = block6["predictions"][:, targets]
            else:
                history = data["previous_ffn"][:-1, targets]
                trigger = data["previous_ffn"][1:, stage.trigger_layer]
                token = data["embedding"][:-1]
                final = data["hidden"][:-1]
                resident = data["resident"][:-1, targets]
                teacher = block6["predictions"][:-1, targets]
            scaled = teacher.astype(np.float32) / temperature
            scaled -= scaled.max(axis=-1, keepdims=True)
            probability = np.exp(scaled)
            probability /= probability.sum(axis=-1, keepdims=True)
            chunks.append(
                (
                    history.astype(np.float16),
                    trigger.astype(np.float16),
                    token.astype(np.float16),
                    final.astype(np.float16),
                    resident.astype(np.uint8),
                    probability.astype(np.float16),
                )
            )
            sequences.append(sample["id"])
    assert chunks
    return tuple(np.concatenate([chunk[index] for chunk in chunks]) for index in range(6)), sequences


def objective(
    model: StageHead,
    history: mx.array,
    trigger: mx.array,
    token: mx.array,
    final: mx.array,
    resident: mx.array,
    teacher: mx.array,
) -> mx.array:
    scores = model(history, trigger, token, final, resident)
    log_probability = scores - mx.logsumexp(scores, axis=-1, keepdims=True)
    return -mx.mean(mx.sum(teacher.astype(mx.float32) * log_probability, axis=-1))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rank", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    plan = json.loads((ROOT / "plan.json").read_text())
    teacher, teacher_sequences = load_teacher(plan, args.stage, args.temperature)
    # Reverse the original development split: Block6 traces exist for 20 old
    # validation conversations, while the 104 old training conversations are
    # disjoint-family evaluation data for this diagnostic.
    evaluation, evaluation_sequences = load(plan, "train", STAGES[args.stage])
    assert not (set(teacher_sequences) & set(evaluation_sequences))

    mx.random.seed(args.seed)
    rng = np.random.default_rng(args.seed)
    stage = STAGES[args.stage]
    model = StageHead(len(stage.targets), args.rank, stage.trigger_layer is not None, 0, "distill", False, True)
    optimizer = optim.AdamW(learning_rate=3e-4, weight_decay=0.01)
    value_and_grad = nn.value_and_grad(model, objective)
    best = -1.0
    best_epoch = 0
    best_metrics = None
    stale = 0
    history = []
    started = time.time()
    for epoch in range(args.epochs):
        order = rng.permutation(len(teacher[0]))
        total = 0.0
        for start in range(0, len(order), 32):
            indices = order[start : start + 32]
            batch = [mx.array(value[indices]) for value in teacher]
            loss, gradients = value_and_grad(model, *batch)
            optimizer.update(model, gradients)
            mx.eval(model.parameters(), optimizer.state, loss)
            total += loss.item() * len(indices)
        metrics, _ = evaluate(model, evaluation)
        score = metrics["fixed_top6"]["recall_at_6"]
        history.append({"epoch": epoch + 1, "train_loss": total / len(order), "evaluation": metrics})
        if score > best:
            best = score
            best_epoch = epoch + 1
            best_metrics = metrics
            stale = 0
            model.save_weights(str(args.output / "model.safetensors"))
        else:
            stale += 1
        (args.output / "history.json").write_text(json.dumps(history, indent=2))
        print(json.dumps({"epoch": epoch + 1, "recall_at_6": score}), flush=True)
        if stale >= 5:
            break
    result = {
        "stage": args.stage,
        "temperature": args.temperature,
        "teacher_sequences": teacher_sequences,
        "teacher_rows": len(teacher[0]),
        "evaluation_sequences": evaluation_sequences,
        "evaluation_rows": len(evaluation[0]),
        "best_epoch": best_epoch,
        "evaluation": best_metrics,
        "seconds": time.time() - started,
        "test_opened": False,
        "scope": "Block6 soft-score distillation; reverse family-disjoint development split",
    }
    (args.output / "result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
