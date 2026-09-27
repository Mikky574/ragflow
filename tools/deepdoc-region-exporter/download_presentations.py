from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path

PRESENTATIONS = (
    ("sample-5-slides.pptx", "https://cdn.truefilesize.com/powerpoint/sample-5-slides.pptx", "CC0"),
    ("sample-20-slides.pptx", "https://cdn.truefilesize.com/powerpoint/sample-20-slides.pptx", "CC0"),
    ("sample-50-slides.pptx", "https://cdn.truefilesize.com/powerpoint/sample-50-slides.pptx", "CC0"),
    ("sample-with-charts.pptx", "https://cdn.truefilesize.com/powerpoint/sample-with-charts.pptx", "CC0"),
    ("sample-with-transitions.pptx", "https://cdn.truefilesize.com/powerpoint/sample-with-transitions.pptx", "CC0"),
    ("business-template.pptx", "https://cdn.truefilesize.com/powerpoint/business-template.pptx", "CC0"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download CC0 PPTX fixtures for visual-region labelling.")
    parser.add_argument("--output", default="source_presentations")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for filename, url, license_name in PRESENTATIONS:
        target = output / filename
        if not target.exists():
            temporary = target.with_suffix(".part")
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request) as response, temporary.open("wb") as stream:
                shutil.copyfileobj(response, stream)
            if not temporary.read_bytes().startswith(b"PK"):
                temporary.unlink(missing_ok=True)
                raise ValueError(f"download is not a PPTX ZIP container: {url}")
            temporary.replace(target)
        records.append({"filename": filename, "url": url, "license": license_name, "size_bytes": target.stat().st_size, "sha256": sha256(target)})
        print(f"ready: {filename}")
    (output / "SOURCES.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
