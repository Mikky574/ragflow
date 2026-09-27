from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download

REPOSITORY = "citeseerx/ACL-fig"
RULES = {
    "scientific_plot": ("bar chart", "line graph", "scatter plot", "pie chart", "histogram", "box plot", "pareto"),
    "scientific_schematic": ("neural networks", "flow chart", "trees", "venn diagram", "architecture"),
    "measurement_image": ("maps", "heatmap"),
    "device_photo": ("natural images",),
    "table": ("tables",),
}


def category_for(path: str) -> str | None:
    normalized = path.lower()
    for category, fragments in RULES.items():
        if any(f"/{fragment}/" in normalized for fragment in fragments):
            return category
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Download a balanced ACL-Fig seed set for visual-classifier review.")
    parser.add_argument("--output", default="data/images/acl-fig")
    parser.add_argument("--per-class", type=int, default=60)
    args = parser.parse_args()

    api = HfApi()
    selected: dict[str, list[str]] = defaultdict(list)
    for filename in api.list_repo_files(REPOSITORY, repo_type="dataset"):
        if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        category = category_for(filename)
        if category and len(selected[category]) < args.per_class:
            selected[category].append(filename)

    missing = sorted(set(RULES) - set(selected))
    if missing:
        raise RuntimeError(f"ACL-Fig has no files for: {', '.join(missing)}")

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for category, filenames in sorted(selected.items()):
        for filename in filenames:
            downloaded = Path(hf_hub_download(REPOSITORY, filename, repo_type="dataset", local_dir=output / category))
            records.append({
                "image_path": str(downloaded.resolve()),
                "proposed_label": category,
                "source_dataset": REPOSITORY,
                "source_path": filename,
                "license": "CC-BY-4.0",
            })

    manifest = output / "SOURCE.json"
    manifest.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"downloaded {len(records)} ACL-Fig images to {output}")


if __name__ == "__main__":
    main()
