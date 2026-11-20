import bootstrap
from bootstrap import UPSTREAM_ROOT, CHECKPOINT_ROOT
import ast, sys, math
from pathlib import Path
from typing import Union, Tuple, Optional, List
from functools import partial
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F
from einops import rearrange
import mlx.core as mx

from flashhead_mlx.ltx_vae import Encoder, Decoder

root = Path(UPSTREAM_ROOT / "flashhead/flash_head/ltx_video/models/autoencoders")
ns = dict(
    torch=torch,
    nn=nn,
    F=F,
    np=np,
    Union=Union,
    Tuple=Tuple,
    Optional=Optional,
    List=List,
    partial=partial,
    rearrange=rearrange,
)


def load(file, names):
    tree = ast.parse((root / file).read_text())
    tree.body = [
        n
        for n in tree.body
        if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names
    ]
    exec(compile(tree, str(root / file), "exec"), ns)


load("causal_conv3d.py", {"CausalConv3d"})
load("pixel_norm.py", {"PixelNorm"})
load("conv_nd_factory.py", {"make_conv_nd", "make_linear_nd"})
load(
    "causal_video_autoencoder.py",
    {
        "Encoder",
        "Decoder",
        "UNetMidBlock3D",
        "ResnetBlock3D",
        "LayerNorm",
        "DepthToSpaceUpsample",
        "patchify",
        "unpatchify",
    },
)
blocks = [("res_x", 1), ("compress_all", 1), ("res_x_y", 1), ("res_x", 1)]
mlblocks = [("res", 1), ("down", 1), ("grow", 1), ("res", 1)]
torch.manual_seed(23)
rng = np.random.default_rng(12)
for name in ["encoder", "decoder"]:
    if name == "encoder":
        ref = ns["Encoder"](
            dims=3,
            in_channels=3,
            out_channels=4,
            blocks=blocks,
            base_channels=4,
            patch_size=4,
            norm_layer="pixel_norm",
            latent_log_var="uniform",
        ).eval()
        model = Encoder(base=4, latent=4, blocks=mlblocks)
        x = rng.normal(size=(1, 3, 9, 16, 16)).astype("float32")
    else:
        ref = ns["Decoder"](
            dims=3,
            in_channels=4,
            out_channels=3,
            blocks=blocks,
            base_channels=4,
            patch_size=4,
            norm_layer="pixel_norm",
            causal=False,
        ).eval()
        model = Decoder(base=4, latent=4, blocks=mlblocks)
        x = rng.normal(size=(1, 4, 3, 2, 2)).astype("float32")
    weights = {
        k: mx.array(v.detach().numpy()).transpose(0, 2, 3, 4, 1)
        if v.ndim == 5
        else mx.array(v.detach().numpy())
        for k, v in ref.state_dict().items()
    }
    model.load_weights(list(weights.items()), strict=True)
    with torch.no_grad():
        expected = (
            ref(torch.from_numpy(x))
            if name == "encoder"
            else ref(torch.from_numpy(x), target_shape=x.shape)
        ).numpy()
    result = model(mx.array(x).transpose(0, 2, 3, 4, 1))
    if name == "encoder":
        result = mx.concatenate(result, axis=-1)
    actual = np.array(result.transpose(0, 4, 1, 2, 3))
    print(name, actual.shape, float(np.max(np.abs(expected - actual))))
    np.testing.assert_allclose(actual, expected, atol=2e-5, rtol=2e-5)
print("PASS: LTX encoder and decoder match upstream")
