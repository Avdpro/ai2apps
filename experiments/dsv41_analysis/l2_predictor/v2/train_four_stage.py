"""Train one causal stage of the DS4.1F four-stage L2 predictor."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
import numpy as np
from mlx.utils import tree_flatten


ROOT = Path("artifacts/dsv41-l2-state-v3-20260916")


@dataclass(frozen=True)
class Stage:
    name: str
    trigger_layer: int | None
    targets: tuple[int, ...]


STAGES = {
    "A": Stage("A", None, tuple(range(3, 10))),
    "B": Stage("B", 5, tuple(range(10, 20))),
    "C": Stage("C", 15, tuple(range(20, 30))),
    "D": Stage("D", 25, tuple(range(30, 40))),
}


class ResidualBlock(nn.Module):
    def __init__(self, width: int):
        super().__init__()
        self.up = nn.Linear(width, 2 * width)
        self.down = nn.Linear(2 * width, width)
        self.down.weight = mx.zeros_like(self.down.weight)
        self.down.bias = mx.zeros_like(self.down.bias)

    def __call__(self, value: mx.array) -> mx.array:
        normalized = value * mx.rsqrt(mx.mean(value * value, axis=-1, keepdims=True) + 1e-6)
        return value + self.down(nn.gelu(self.up(normalized)))


class StageHead(nn.Module):
    def __init__(
        self,
        layers: int,
        rank: int,
        has_trigger: bool,
        blocks: int,
        loss_kind: str,
        per_layer: bool,
        use_cache: bool = True,
    ):
        super().__init__()
        self.has_trigger = has_trigger
        self.loss_kind = loss_kind
        self.per_layer = per_layer
        self.use_cache = use_cache
        if per_layer:
            self.history = mx.random.normal((layers, 5120, rank)) * (5120**-0.5)
        else:
            self.history = nn.Linear(5120, rank)
        self.token = nn.Linear(5120, rank, bias=False)
        self.final = nn.Linear(5120, rank, bias=False)
        if use_cache:
            self.cache = nn.Linear(384, rank, bias=False)
        if has_trigger:
            if per_layer:
                self.trigger = mx.random.normal((layers, 5120, rank)) * (5120**-0.5)
            else:
                self.trigger = nn.Linear(5120, rank, bias=False)
        self.layer = mx.zeros((layers, rank))
        self.blocks = [ResidualBlock(rank) for _ in range(blocks)]
        self.out = mx.random.normal((layers, rank, 384)) * 0.02
        self.bias = mx.zeros((layers, 384))

    @staticmethod
    def norm(value: mx.array) -> mx.array:
        value = value.astype(mx.float32)
        return value * mx.rsqrt(mx.mean(value * value, axis=-1, keepdims=True) + 1e-6)

    def __call__(
        self,
        history: mx.array,
        trigger: mx.array,
        token: mx.array,
        final: mx.array,
        resident: mx.array,
    ) -> mx.array:
        normalized_history = self.norm(history)
        if self.per_layer:
            hidden = mx.matmul(normalized_history.transpose(1, 0, 2), self.history).transpose(1, 0, 2)
        else:
            hidden = self.history(normalized_history)
        hidden = hidden + self.token(self.norm(token))[:, None]
        hidden = hidden + self.final(self.norm(final))[:, None] + self.layer
        if self.use_cache:
            hidden = hidden + self.cache((resident > 0).astype(mx.float32))
        if self.has_trigger:
            normalized_trigger = self.norm(trigger)
            if self.per_layer:
                projected = mx.matmul(normalized_trigger[None], self.trigger).transpose(1, 0, 2)
                hidden = hidden + projected
            else:
                hidden = hidden + self.trigger(normalized_trigger)[:, None]
        hidden = nn.gelu(hidden)
        for block in self.blocks:
            hidden = block(hidden)
        return mx.matmul(hidden.transpose(1, 0, 2), self.out).transpose(1, 0, 2) + self.bias


def make_truth(top6: np.ndarray) -> np.ndarray:
    truth = np.zeros(top6.shape[:-1] + (384,), dtype=np.uint8)
    np.put_along_axis(truth, top6.astype(np.int64), 1, axis=-1)
    return truth


def load(plan: dict, split: str, stage: Stage) -> tuple[tuple[np.ndarray, ...], list[str]]:
    chunks: list[tuple[np.ndarray, ...]] = []
    sequence_ids: list[str] = []
    targets = list(stage.targets)
    for sample in plan["samples"]:
        if sample["split"] != split:
            continue
        data_dir = ROOT / "data" / sample["id"]
        if not (data_dir / "verified.json").exists():
            continue
        with np.load(data_dir / "supervision.npz") as data:
            if stage.trigger_layer is None:
                history = data["previous_ffn"][:, targets]
                # Kept as a uniform array slot; Stage A does not consume it.
                trigger = data["hidden"]
                token = data["embedding"]
                final = data["hidden"]
                resident = data["resident"][:, targets]
                top6 = data["top6"][:, targets]
            else:
                # Row t+1 stores row t's exact current-token FFN inputs as
                # previous_ffn. Labels and other causal inputs come from row t.
                history = data["previous_ffn"][:-1, targets]
                trigger = data["previous_ffn"][1:, stage.trigger_layer]
                token = data["embedding"][:-1]
                final = data["hidden"][:-1]
                resident = data["resident"][:-1, targets]
                top6 = data["top6"][:-1, targets]
            chunks.append(
                (
                    history.astype(np.float16),
                    trigger.astype(np.float16),
                    token.astype(np.float16),
                    final.astype(np.float16),
                    resident.astype(np.uint8),
                    make_truth(top6),
                    top6.astype(np.uint16),
                )
            )
            sequence_ids.extend([sample["id"]] * len(top6))
    assert chunks, split
    arrays = tuple(np.concatenate([chunk[i] for chunk in chunks]) for i in range(7))
    return arrays, sequence_ids


def objective(
    model: StageHead,
    history: mx.array,
    trigger: mx.array,
    token: mx.array,
    final: mx.array,
    resident: mx.array,
    truth: mx.array,
) -> mx.array:
    scores = model(history, trigger, token, final, resident)
    truth = truth.astype(mx.float32)
    # Keep the label cache-independent, while emphasizing the positive experts
    # that were absent from L0/L1 at collection time.
    if model.loss_kind == "rank":
        labels = truth * (1 + 3 * (resident == 0))
        labels = labels / mx.maximum(mx.sum(labels, axis=-1, keepdims=True), 1)
        return -mx.mean(mx.sum(labels * (scores - mx.logsumexp(scores, axis=-1, keepdims=True)), axis=-1))
    weights = 1 + truth * (15 + 48 * (resident == 0))
    return mx.mean((mx.logaddexp(scores, 0) - truth * scores) * weights)


def evaluate(model: StageHead, data: tuple[np.ndarray, ...], keep_scores: bool = False) -> tuple[dict, np.ndarray | None]:
    rows = len(data[0])
    total_loss = 0.0
    intersections = np.zeros(data[5].shape[1], dtype=np.int64)
    target_misses = 0
    budgets = (8, 16, 24, 48, 64)
    useful = {budget: 0 for budget in budgets}
    reads = {budget: 0 for budget in budgets}
    score_chunks: list[np.ndarray] = []
    for start in range(0, rows, 32):
        batch = [mx.array(value[start : start + 32]) for value in data[:6]]
        scores = model(*batch[:5])
        loss = objective(model, *batch)
        mx.eval(scores, loss)
        count = len(batch[0])
        total_loss += loss.item() * count
        scores_np = np.array(scores)
        if keep_scores:
            score_chunks.append(scores_np.astype(np.float16))

        truth = data[5][start : start + count].astype(bool)
        resident = data[4][start : start + count]
        fixed = np.argsort(scores_np, axis=-1)[..., -6:]
        intersections += np.take_along_axis(truth, fixed, axis=-1).sum(axis=(0, 2))
        eligible = resident == 0
        missing_truth = truth & eligible
        target_misses += int(missing_truth.sum())
        flattened = np.where(eligible, scores_np, -np.inf).reshape(count, -1)
        order = np.argsort(flattened, axis=-1)[:, -64:][:, ::-1]
        good = np.take_along_axis(missing_truth.reshape(count, -1), order, axis=-1)
        finite = np.take_along_axis(np.isfinite(flattened), order, axis=-1)
        for budget in budgets:
            useful[budget] += int(good[:, :budget].sum())
            reads[budget] += int(finite[:, :budget].sum())

    metrics = {
        "loss": total_loss / rows,
        "rows": rows,
        "fixed_top6": {
            "mean_intersection": float(intersections.sum()) / (rows * len(intersections)),
            "recall_at_6": float(intersections.sum()) / (rows * len(intersections) * 6),
            "per_layer_intersection": (intersections / rows).tolist(),
        },
        "target_misses_per_token": target_misses / rows,
        "stage_budget": {
            str(budget): {
                "coverage": useful[budget] / max(target_misses, 1),
                "precision": useful[budget] / max(reads[budget], 1),
                "useful_per_token": useful[budget] / rows,
                "reads_per_token": reads[budget] / rows,
            }
            for budget in budgets
        },
    }
    saved_scores = np.concatenate(score_chunks) if keep_scores else None
    return metrics, saved_scores


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rank", type=int, default=256)
    parser.add_argument("--blocks", type=int, default=0)
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--loss", choices=("bce", "rank"), default="bce")
    parser.add_argument(
        "--selection",
        choices=("recall", "coverage8", "coverage16", "coverage24", "coverage48", "coverage64"),
        default="coverage16",
        help="validation metric used for checkpoint selection and early stopping",
    )
    parser.add_argument("--per-layer", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--warm-start", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)

    stage = STAGES[args.stage]
    plan = json.loads((ROOT / "plan.json").read_text())
    train, train_sequences = load(plan, "train", stage)
    validation, validation_sequences = load(plan, "validation", stage)
    assert not (set(train_sequences) & set(validation_sequences))

    mx.random.seed(args.seed)
    rng = np.random.default_rng(args.seed)
    model = StageHead(
        len(stage.targets),
        args.rank,
        stage.trigger_layer is not None,
        args.blocks,
        args.loss,
        args.per_layer,
        not args.no_cache,
    )
    if args.warm_start:
        model.load_weights(str(args.warm_start), strict=False)
    optimizer = optim.AdamW(learning_rate=1e-4 if args.warm_start else 3e-4, weight_decay=0.01)
    value_and_grad = nn.value_and_grad(model, objective)
    initial, _ = evaluate(model, validation)
    def selection_score(metrics: dict) -> float:
        if args.selection == "recall":
            return metrics["fixed_top6"]["recall_at_6"]
        budget = args.selection.removeprefix("coverage")
        return metrics["stage_budget"][budget]["coverage"]

    best_score = selection_score(initial)
    best_metrics = initial
    best_epoch = 0
    stale = 0
    history = [{"epoch": 0, "validation": initial}]
    started = time.time()
    model.save_weights(str(args.output / "model.safetensors"))

    manifest = {
        "stage": stage.name,
        "trigger_layer": stage.trigger_layer,
        "target_layers": list(stage.targets),
        "rank": args.rank,
        "blocks": args.blocks,
        "seed": args.seed,
        "loss": args.loss,
        "selection": args.selection,
        "per_layer": args.per_layer,
        "cache_feature": not args.no_cache,
        "warm_start": str(args.warm_start) if args.warm_start else None,
        "train_sequences": sorted(set(train_sequences)),
        "validation_sequences": sorted(set(validation_sequences)),
        "test_opened": False,
        "alignment": "B/C/D row t labels use row t+1 previous_ffn as exact row t trigger state",
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2))

    for epoch in range(args.epochs):
        order = rng.permutation(len(train[0]))
        train_loss = 0.0
        for start in range(0, len(order), 32):
            indices = order[start : start + 32]
            batch = [mx.array(value[indices]) for value in train[:6]]
            loss, gradients = value_and_grad(model, *batch)
            optimizer.update(model, gradients)
            mx.eval(model.parameters(), optimizer.state, loss)
            train_loss += loss.item() * len(indices)
        metrics, _ = evaluate(model, validation)
        score = selection_score(metrics)
        item = {
            "epoch": epoch + 1,
            "train_loss": train_loss / len(order),
            "validation": metrics,
            "seconds": time.time() - started,
        }
        history.append(item)
        if score > best_score:
            best_score = score
            best_metrics = metrics
            best_epoch = epoch + 1
            stale = 0
            model.save_weights(str(args.output / "model.safetensors"))
        else:
            stale += 1
        (args.output / "history.json").write_text(json.dumps(history, indent=2))
        print(
            json.dumps(
                {
                    "stage": stage.name,
                    "epoch": epoch + 1,
                    "recall_at_6": metrics["fixed_top6"]["recall_at_6"],
                    "coverage48": metrics["stage_budget"]["48"]["coverage"],
                    "coverage64": metrics["stage_budget"]["64"]["coverage"],
                    "selection": args.selection,
                    "selection_score": score,
                }
            ),
            flush=True,
        )
        if stale >= 5:
            break

    model.load_weights(str(args.output / "model.safetensors"))
    frozen_metrics, scores = evaluate(model, validation, keep_scores=True)
    np.savez_compressed(
        args.output / "validation-scores.npz",
        scores=scores,
        resident=validation[4],
        truth=validation[5],
        top6=validation[6],
    )
    result = {
        "best_epoch": best_epoch,
        "selection_metrics": best_metrics,
        "frozen_validation": frozen_metrics,
        "train_rows": len(train[0]),
        "validation_rows": len(validation[0]),
        "parameters": sum(value.size for _, value in tree_flatten(model.parameters())),
        "weight_bytes": (args.output / "model.safetensors").stat().st_size,
        "seconds": time.time() - started,
    }
    (args.output / "result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
