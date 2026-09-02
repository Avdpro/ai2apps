#!/usr/bin/env python3
"""Score prompt alignment and create a side-by-side quality review sheet."""

import argparse
import json
from pathlib import Path

import torch
from PIL import Image, ImageDraw
from transformers import CLIPModel, CLIPProcessor


def _feature_tensor(value):
    """Accept both Transformers <=4 tensor and >=5 model-output APIs."""
    return value.pooler_output if hasattr(value, "pooler_output") else value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mlx", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--clip-model-path", default="openai/clip-vit-large-patch14")
    parser.add_argument("--prompts", type=Path, default=Path(__file__).with_name("prompts.json"))
    args = parser.parse_args()
    prompts = json.loads(args.prompts.read_text())
    processor = CLIPProcessor.from_pretrained(args.clip_model_path)
    model = CLIPModel.from_pretrained(args.clip_model_path).to("cuda").eval()
    rows = []
    tiles = []
    for item in prompts:
        images = [Image.open(args.mlx / f"{item['id']}.png").convert("RGB"), Image.open(args.reference / f"{item['id']}.png").convert("RGB")]
        inputs = processor(text=[item["prompt"], item["prompt"]], images=images, return_tensors="pt", padding=True).to("cuda")
        with torch.inference_mode():
            image_features = _feature_tensor(
                model.get_image_features(pixel_values=inputs["pixel_values"])
            )
            text_features = _feature_tensor(
                model.get_text_features(
                    input_ids=inputs["input_ids"], attention_mask=inputs["attention_mask"]
                )
            )
            scores = torch.nn.functional.cosine_similarity(image_features, text_features).cpu().tolist()
        rows.append({"id": item["id"], "mlx_clip": scores[0], "reference_clip": scores[1], "delta": scores[0] - scores[1]})
        tiles.append((item["id"], images))
    metrics = {
        "model": args.clip_model_path,
        "mlx_mean": sum(row["mlx_clip"] for row in rows) / len(rows),
        "reference_mean": sum(row["reference_clip"] for row in rows) / len(rows),
        "rows": rows,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "quality.json").write_text(json.dumps(metrics, indent=2) + "\n")

    tile_size = 512
    sheet = Image.new("RGB", (tile_size * 2, (tile_size + 44) * len(tiles)), "white")
    draw = ImageDraw.Draw(sheet)
    for row, (name, images) in enumerate(tiles):
        top = row * (tile_size + 44)
        draw.text((8, top + 8), f"{name}: MLX", fill="black")
        draw.text((tile_size + 8, top + 8), f"{name}: Diffusers BF16", fill="black")
        for column, image in enumerate(images):
            preview = image.copy()
            preview.thumbnail((tile_size, tile_size))
            sheet.paste(preview, (column * tile_size, top + 44))
    sheet.save(args.output / "comparison.jpg", quality=92)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
