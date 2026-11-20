"""Development-only transfer batching; no cache/replacement or routing change."""
import torch
from torch import nn
from qwen38_flash_backend import DiskExperts, dequantize


class BatchedDiskExperts(DiskExperts):
    def forward(self, hidden, indices, scores):
        output = torch.zeros_like(hidden)
        assert indices.shape[-1] == 10
        experts = indices.unique().tolist()
        for start in range(0, len(experts), 10):
            batch = experts[start:start + 10]
            packed = bytearray()
            spans = {}
            for expert in batch:
                for projection in ('gate_proj', 'up_proj', 'down_proj'):
                    for field, dtype in (('weight', torch.uint32), ('scales', torch.bfloat16), ('biases', torch.bfloat16)):
                        entry = self.metadata[f'language_model.model.layers.{self.layer}.mlp.switch_mlp.{projection}.{field}']
                        assert 0 <= expert < entry['count']
                        begin = len(packed)
                        packed.extend(self.store.read(entry['file'], entry['offset'] + expert * entry['stride'], entry['row_bytes']))
                        spans[(expert, projection, field)] = (begin, len(packed), dtype, entry['shape'][1:])
            # Keep the pinned host owner alive until this batch's work has been enqueued.
            host = torch.frombuffer(packed, dtype=torch.uint8).pin_memory()
            device = host.to('cuda', non_blocking=True)
            def projection_weight(expert, projection):
                parts = []
                for field in ('weight', 'scales', 'biases'):
                    begin, end, dtype, shape = spans[(expert, projection, field)]
                    parts.append(device[begin:end].view(dtype).reshape(shape))
                return dequantize(*parts)
            for expert in batch:
                rows, slots = torch.where(indices == expert)
                x = hidden[rows]
                gate = nn.functional.linear(x, projection_weight(expert, 'gate_proj'))
                up = nn.functional.linear(x, projection_weight(expert, 'up_proj'))
                value = nn.functional.linear(nn.functional.silu(gate) * up, projection_weight(expert, 'down_proj'))
                output.index_add_(0, rows, value * scores[rows, slots, None])
        return output
