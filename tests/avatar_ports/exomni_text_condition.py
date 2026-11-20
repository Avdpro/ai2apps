import bootstrap
from bootstrap import UPSTREAM_ROOT, CHECKPOINT_ROOT

"""Ex-Omni must preserve zero context positions through learned projection."""
import sys
from pathlib import Path
from unittest.mock import patch
import numpy as np
import mlx.core as mx

from exomni_mlx.conditioners import TextEncoder

encoder = TextEncoder.__new__(TextEncoder)
encoder.parameters = None
encoder.tokenizer = None
ids = mx.array([[5, 1, 0, 0]])
mask = mx.array([[1, 1, 0, 0]])
with (
    patch(
        "exomni_mlx.conditioners.wan_t5_tokenize", return_value=(ids, mask)
    ) as tokenize,
    patch(
        "exomni_mlx.conditioners.wan_t5_encode_trimmed",
        return_value=(mx.ones((1, 2, 8)), mx.array([2])),
    ),
):
    result = np.array(encoder("  A\n woman &amp; cat. "))
    assert tokenize.call_args.args[0] == ["A woman & cat."]
assert result.shape == (1, 512, 8)
np.testing.assert_array_equal(result[:, :2], 1)
np.testing.assert_array_equal(result[:, 2:], 0)
print(
    "PASS: 512 context positions, zero padding before projection, whitespace normalization"
)
