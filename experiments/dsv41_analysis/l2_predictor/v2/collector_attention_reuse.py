"""Frozen diagnostic runner: export only at the runner's completed-token boundary."""
import os
from pathlib import Path
import numpy as np
import mlx.core as mx
import run


class Collected(run.Model):
    def __init__(self, *args, **kwargs):
        self.pending = {}
        self.rows = []
        self.previous = None
        self.previous_ffn = None
        super().__init__(*args, **kwargs)

    def emit(self, name, value):
        if name.endswith('.l2_previous_attn'):
            self.pending[('previous_attention', int(name.split('.')[1]))] = value.astype(mx.float32)
        elif name.endswith('.l2_attnreuse'):
            self.pending[('reuse', int(name.split('.')[1]))] = value.astype(mx.float32)
        elif name.endswith('.l2_preattn'):
            self.pending[('preattn', int(name.split('.')[1]))] = value.astype(mx.float32)
        elif name.endswith('.l2_ffn'):
            self.pending[('ffn', int(name.split('.')[1]))] = value.astype(mx.float32)
        elif name.endswith('.l2_rank'):
            self.pending[('rank', int(name.split('.')[1]))] = value[-1]
        elif name.endswith('.gate'):
            self.pending[('ids', int(name.split('.')[1]))] = value[-1]
        elif name == 'l2_embedding':
            self.embedding = value[0, -1]
        elif name == 'l2_final':
            self.hidden = value[0]
        return super().emit(name, value)

    def __call__(self, ids, start=0):
        self.start = start
        if start:
            # Other layers cannot alter this layer's bank. Snapshot before any
            # current-token routing or eviction; no device readback is involved.
            self.resident = np.zeros((40, 384), dtype=np.uint8)
            for layer, bank in self.banks.items():
                self.resident[layer, list(bank.main)] = 1
                self.resident[layer, list(bank.hot)] = 2
        result = super().__call__(ids, start)
        self.hidden = self.hidden.astype(mx.float32)
        self.embedding = self.embedding.astype(mx.float32)
        self.export_arrays = [self.hidden, self.embedding]
        self.export_arrays += [self.pending[('ffn', l)] for l in range(40)]
        self.export_arrays += [self.pending[('preattn', l)] for l in range(40)]
        self.export_arrays += [self.pending[('reuse', l)] for l in range(40)]
        self.export_arrays += [self.pending[('previous_attention', l)] for l in range(40)]
        self.export_arrays += [self.pending[('ids', l)] for l in range(40)]
        if start:
            self.export_arrays += [self.pending[('rank', l)] for l in range(40)]
        return result

    def collection_roots(self):
        return self.export_arrays

    def collection_complete(self):
        # All roots were included in the existing runner mx.eval. Cast on CPU,
        # not via a fresh MLX graph that would introduce another GPU wait.
        hidden = np.array(self.hidden).astype(np.float32)
        top6 = np.stack([np.array(self.pending[('ids', l)]) for l in range(40)]).astype(np.uint16)
        current_ffn = np.stack([np.array(self.pending[('ffn', l)]) for l in range(40)])
        current_preattn = np.stack([np.array(self.pending[('preattn', l)]) for l in range(40)])
        current_reuse = np.stack([np.array(self.pending[('reuse', l)]) for l in range(40)])
        previous_attention = np.stack([np.array(self.pending[('previous_attention', l)]) for l in range(40)])
        if self.start:
            rank = np.stack([np.array(self.pending[('rank', l)]) for l in range(40)]).astype(np.float32)
            embedding = np.array(self.embedding).astype(np.float32)
            self.rows.append(dict(previous_attention=previous_attention,attention_reuse=current_reuse,actual_ffn=current_ffn,preattn=current_preattn, hidden=self.previous, embedding=embedding,
                router_rank=rank, top6=top6, previous_top6=self.previous_top6,
                resident=self.resident, position=np.int32(self.start)))
        self.previous_ffn = current_ffn
        self.previous = hidden
        self.previous_top6 = top6
        self.pending.clear()
        self.export_arrays = []

    def close(self):
        try:
            if self.rows:
                out = Path(os.environ['L2_COLLECT_OUTPUT'])
                np.savez(out / 'supervision.npz', **{
                    key: np.stack([row[key] for row in self.rows]) for key in self.rows[0]})
        finally:
            super().close()


run.Model = Collected
run.main()
