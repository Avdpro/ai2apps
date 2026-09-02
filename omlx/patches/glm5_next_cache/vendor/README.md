# Vendored mlx-vlm GLM5 compatibility modules

These files are copied from `Blaizzy/mlx-vlm` commit
`7c1cf01077f0a938fa36182943a931f3fc863206` (2026-08-27). They provide the
GLM5 Next, DeepSeek V3.2, MLA, gated-delta, MLP, activation, switch-layer, and
RoPE modules missing from (or API-incompatible with) oMLX's pinned mlx-vlm commit
`78b96eb5462141447b9a6b4943ef553891da56dd`.

This coherent snapshot precedes the installed package only for files it supplies;
all other modules still resolve from the pinned mlx-vlm installation. Remove the
compatibility namespace when the project pin reaches this source commit. The
copied code is distributed under the upstream MIT license in `LICENSE`.
