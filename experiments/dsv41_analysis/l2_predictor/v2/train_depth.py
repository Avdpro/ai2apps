"""Validation-only residual-depth ablation, using the same causal state features."""
import argparse
import hashlib
import json
import time
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
import numpy as np
from mlx.utils import tree_flatten
from train_state import ROOT, StateHead, load, objective, evaluate


class ResidualBlock(nn.Module):
    def __init__(self, width):
        super().__init__()
        self.up = nn.Linear(width, 2 * width)
        self.down = nn.Linear(2 * width, width)
        self.down.weight = mx.zeros_like(self.down.weight)
        self.down.bias = mx.zeros_like(self.down.bias)

    def __call__(self, x):
        normed = x * mx.rsqrt(mx.mean(x * x, axis=-1, keepdims=True) + 1e-6)
        return x + self.down(nn.gelu(self.up(normed)))


class DeepStateHead(StateHead):
    def __init__(self, rank=512, blocks=0):
        super().__init__(rank)
        self.blocks = [ResidualBlock(rank) for _ in range(blocks)]

    def __call__(self, local, token, final, resident):
        def norm(x):
            return x * mx.rsqrt(mx.mean(x * x, axis=-1, keepdims=True) + 1e-6)
        h = nn.gelu(self.local(norm(local)) + self.token(norm(token))[:, None]
                    + self.final(norm(final))[:, None]
                    + self.cache((resident > 0).astype(mx.float32)) + self.layer)
        for block in self.blocks:
            h = block(h)
        return mx.matmul(h.transpose(1, 0, 2), self.out).transpose(1, 0, 2) + self.bias


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--epochs', type=int, default=15)
    ap.add_argument('--seed', type=int, default=17)
    ap.add_argument('--blocks', type=int, choices=[0, 1, 3], required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    plan = json.loads((ROOT / 'plan.json').read_text())
    families = {s: {r['family_id'] for r in plan['samples'] if r['split'] == s}
                for s in ('train', 'validation')}
    assert not families['train'] & families['validation']
    tr, trids = load(plan, 'train'); va, vaids = load(plan, 'validation')
    mx.random.seed(args.seed); rng = np.random.default_rng(args.seed)
    m = DeepStateHead(blocks=args.blocks)
    warm = ROOT / 'extended-r512/model.safetensors'
    m.load_weights(str(warm), strict=False)
    opt = optim.AdamW(learning_rate=1e-4, weight_decay=.01)
    vg = nn.value_and_grad(m, objective)
    initial = evaluate(m, va)
    baseline = json.loads((warm.parent / 'result.json').read_text())['validation']['budgets']['64']['coverage']
    assert abs(initial['budgets'][64]['coverage'] - baseline) < 1e-9, 'Residual initialization must preserve the original predictor'
    manifest = dict(blocks=args.blocks, rank=512, seed=args.seed, epochs=args.epochs,
                    train_sequences=trids, validation_sequences=vaids,
                    warm_start=str(warm), warm_sha256=hashlib.sha256(warm.read_bytes()).hexdigest(),
                    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    selection='best validation cap64 coverage; no final-test access', test_opened=False)
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    best = initial; best_epoch = 0; stale = 0; history = [dict(epoch=0, validation=initial)]
    m.save_weights(str(args.output / 'model.safetensors')); start = time.perf_counter()
    for epoch in range(1, args.epochs + 1):
        ids = rng.permutation(len(tr[0])); loss = 0.
        for begin in range(0, len(ids), 32):
            ix = ids[begin:begin + 32]
            v, g = vg(m, *[mx.array(x[ix]) for x in tr])
            opt.update(m, g); mx.eval(m.parameters(), opt.state, v)
            loss += v.item() * len(ix)
        ev = evaluate(m, va)
        history.append(dict(epoch=epoch, train_loss=loss / len(ids), validation=ev))
        if ev['budgets'][64]['coverage'] > best['budgets'][64]['coverage']:
            best = ev; best_epoch = epoch; stale = 0
            m.save_weights(str(args.output / 'model.safetensors'))
        else:
            stale += 1
        (args.output / 'history.json').write_text(json.dumps(history, indent=2))
        print(json.dumps(dict(epoch=epoch, blocks=args.blocks, coverage64=ev['budgets'][64]['coverage'])), flush=True)
        if stale >= 5:
            break
    m.load_weights(str(args.output / 'model.safetensors'))
    inputs = [mx.array(x[:1]) for x in va[:4]]
    for _ in range(5): mx.eval(m(*inputs))
    timings = []
    for _ in range(50):
        begin = time.perf_counter(); mx.eval(m(*inputs)); timings.append(time.perf_counter() - begin)
    params = sum(x.size for _, x in tree_flatten(m.parameters()))
    result = dict(best_epoch=best_epoch, validation=best, parameters=params,
                  estimated_fp16_weight_bytes=params * 2, checkpoint_bytes=(args.output / 'model.safetensors').stat().st_size,
                  single_sample_gpu_eval_median_ms=1000 * float(np.median(timings)),
                  seconds=time.perf_counter() - start, train_rows=len(tr[0]), validation_rows=len(va[0]))
    (args.output / 'result.json').write_text(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
