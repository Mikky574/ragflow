from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from .classifier import SiglipZeroShotClassifier
from .taxonomy import load_taxonomy

IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


def json_lines(path: Path) -> Iterable[dict]:
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f"{path}:{line_number}: invalid JSON") from error


def write_json_lines(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def create_manifest(args: argparse.Namespace) -> None:
    image_root = Path(args.images).resolve()
    rows = []
    for image_path in sorted(image_root.rglob("*")):
        if image_path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        relative_path = image_path.relative_to(image_root).as_posix()
        rows.append({
            "id": relative_path.replace("/", "__"),
            "image_path": str(image_path),
            "source_file": "",
            "page": None,
            "bbox": None,
            "ocr_text": "",
            "label": "",
        })
    write_json_lines(Path(args.output), rows)
    print(f"wrote {len(rows)} candidates to {args.output}")


def predict(args: argparse.Namespace) -> None:
    taxonomy = load_taxonomy(args.taxonomy)
    classifier = SiglipZeroShotClassifier(taxonomy, args.model, args.device)
    rows = []
    for row in json_lines(Path(args.input)):
        result = dict(row)
        result.update(classifier.classify(row["image_path"], args.threshold))
        rows.append(result)
    write_json_lines(Path(args.output), rows)
    print(f"wrote {len(rows)} predictions to {args.output}")


def export_review(args: argparse.Namespace) -> None:
    rows = list(json_lines(Path(args.input)))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["id", "image_path", "source_file", "page", "bbox", "ocr_text", "visual_type", "visual_score", "index_action", "label"]
    with output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} review rows to {output}")


def import_review(args: argparse.Namespace) -> None:
    known_labels = set(load_taxonomy(args.taxonomy))
    labels: dict[str, str] = {}
    with Path(args.review).open(newline="", encoding="utf-8-sig") as stream:
        for line_number, row in enumerate(csv.DictReader(stream), start=2):
            identifier = (row.get("id") or "").strip()
            label = (row.get("label") or "").strip()
            if not identifier or not label:
                continue
            if label not in known_labels:
                raise ValueError(f"{args.review}:{line_number}: unknown label {label!r}")
            if identifier in labels:
                raise ValueError(f"{args.review}:{line_number}: duplicate id {identifier!r}")
            labels[identifier] = label

    rows = []
    for row in json_lines(Path(args.input)):
        result = dict(row)
        if label := labels.get(result.get("id", "")):
            result["label"] = label
        rows.append(result)
    write_json_lines(Path(args.output), rows)
    print(f"wrote {len(rows)} rows with {len(labels)} manual labels to {args.output}")


def evaluate(args: argparse.Namespace) -> None:
    rows = [row for row in json_lines(Path(args.input)) if row.get("label")]
    if not rows:
        raise ValueError("manifest has no manually assigned labels")
    correct = sum(row.get("visual_type") == row["label"] for row in rows)
    by_label = Counter(row["label"] for row in rows)
    report = {
        "samples": len(rows),
        "accuracy": round(correct / len(rows), 4),
        "labels": dict(sorted(by_label.items())),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and evaluate a visual-region classification dataset.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest_parser = subparsers.add_parser("create-manifest", help="scan local image crops into a JSONL manifest")
    manifest_parser.add_argument("--images", required=True)
    manifest_parser.add_argument("--output", required=True)
    manifest_parser.set_defaults(handler=create_manifest)

    predict_parser = subparsers.add_parser("predict", help="zero-shot classify a JSONL manifest")
    predict_parser.add_argument("--input", required=True)
    predict_parser.add_argument("--output", required=True)
    predict_parser.add_argument("--taxonomy", default="config/classes.yaml")
    predict_parser.add_argument("--model", default="google/siglip2-base-patch16-224")
    predict_parser.add_argument("--device", default="cuda:0")
    predict_parser.add_argument("--threshold", type=float, default=0.55)
    predict_parser.set_defaults(handler=predict)

    review_parser = subparsers.add_parser("export-review", help="export predictions for manual labels")
    review_parser.add_argument("--input", required=True)
    review_parser.add_argument("--output", required=True)
    review_parser.set_defaults(handler=export_review)

    import_parser = subparsers.add_parser("import-review", help="merge manually assigned CSV labels back into JSONL")
    import_parser.add_argument("--input", required=True)
    import_parser.add_argument("--review", required=True)
    import_parser.add_argument("--output", required=True)
    import_parser.add_argument("--taxonomy", default="config/classes.yaml")
    import_parser.set_defaults(handler=import_review)

    evaluate_parser = subparsers.add_parser("evaluate", help="report accuracy for a labelled prediction JSONL")
    evaluate_parser.add_argument("--input", required=True)
    evaluate_parser.set_defaults(handler=evaluate)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
