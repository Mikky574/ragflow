from argparse import Namespace
from pathlib import Path
import csv
import json

from PIL import Image

from visual_classifier.__main__ import create_manifest, export_review, import_review


def test_manifest_and_review_round_trip(tmp_path, monkeypatch):
    image_root = tmp_path / "images"
    image_root.mkdir()
    Image.new("RGB", (8, 8)).save(image_root / "equation.png")
    manifest = tmp_path / "candidates.jsonl"

    create_manifest(Namespace(images=image_root, output=manifest))
    row = json.loads(manifest.read_text(encoding="utf-8").strip())
    assert row["bbox"] is None
    assert row["label"] == ""

    prediction = tmp_path / "prediction.jsonl"
    row.update(visual_type="equation", visual_score=0.9, index_action="index")
    prediction.write_text(json.dumps(row) + "\n", encoding="utf-8")
    review = tmp_path / "review.csv"
    export_review(Namespace(input=prediction, output=review))

    with review.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    rows[0]["label"] = "equation"
    with review.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    monkeypatch.chdir(tmp_path)
    taxonomy = Path(__file__).parents[1] / "config" / "classes.yaml"
    labelled = tmp_path / "labelled.jsonl"
    import_review(Namespace(input=prediction, review=review, output=labelled, taxonomy=taxonomy))
    assert json.loads(labelled.read_text(encoding="utf-8").strip())["label"] == "equation"
