from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


def copy_seed(source: Path, destination: Path, label: str, limit: int, source_dataset: str, records: list[dict]) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    images = sorted(path for path in source.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES)
    for index, image in enumerate(images[:limit], start=1):
        copied = destination / f"{index:04d}{image.suffix.lower()}"
        shutil.copy2(image, copied)
        records.append({
            "id": f"seed__{label}__{index:04d}",
            "image_path": str(copied.resolve()),
            "source_file": source_dataset,
            "page": None,
            "bbox": None,
            "ocr_text": "",
            "label": label,
            "seed_source": str(image),
        })


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an initial labelled visual-classification seed manifest.")
    parser.add_argument("--diagram-source", default="data/source/diagrambank/raw")
    parser.add_argument("--images", default="data/images")
    parser.add_argument("--manifest", default="data/manifests/public-seed.jsonl")
    parser.add_argument("--diagrams", type=int, default=200)
    args = parser.parse_args()

    records: list[dict] = []
    image_root = Path(args.images)
    copy_seed(Path(args.diagram_source), image_root / "scientific_schematic", "scientific_schematic", args.diagrams, "ghzlmc/DiagramBank: ICLR 2017 accept oral", records)

    output = Path(args.manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"wrote {len(records)} labelled seed records to {output}")


if __name__ == "__main__":
    main()
