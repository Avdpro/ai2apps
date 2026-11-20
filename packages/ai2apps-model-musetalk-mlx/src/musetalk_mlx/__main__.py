"""Local MuseTalk inference with explicitly prepared face regions."""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from .pipeline_mlx import MuseTalkPipeline
from .template import FaceRegion, render_template


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("weights", "template", "audio", "regions", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()
    entries = json.loads(args.regions.read_text())
    regions = []
    inputs = {args.template.resolve(), args.audio.resolve(), args.regions.resolve()}
    for entry in entries:
        path = args.regions.parent / entry["mask"]
        inputs.add(path.resolve())
        with Image.open(path) as image:
            mask = np.asarray(image.convert("L"), dtype=np.float32) / 255
        regions.append(FaceRegion(tuple(entry["box"]), mask))
    if args.output.resolve() in inputs:
        parser.error("Output must differ from inputs")
    model = MuseTalkPipeline.from_pretrained_mlx(args.weights)
    result = render_template(
        model,
        args.template,
        args.audio,
        args.output,
        regions,
        batch_size=args.batch_size,
    )
    print(json.dumps({"output": str(result)}))


if __name__ == "__main__":
    main()
