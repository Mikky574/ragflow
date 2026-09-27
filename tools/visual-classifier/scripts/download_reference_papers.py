from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path

PAPERS = (
    {
        "id": "arxiv:1706.03762",
        "title": "Attention Is All You Need",
        "filename": "attention-is-all-you-need.pdf",
        "url": "https://arxiv.org/pdf/1706.03762",
    },
    {
        "id": "arxiv:1512.03385",
        "title": "Deep Residual Learning for Image Recognition",
        "filename": "deep-residual-learning.pdf",
        "url": "https://arxiv.org/pdf/1512.03385",
    },
    {
        "id": "arxiv:1711.10561",
        "title": "Physics-informed neural networks",
        "filename": "physics-informed-neural-networks.pdf",
        "url": "https://arxiv.org/pdf/1711.10561",
    },
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download real-paper PDF fixtures for visual classifier dataset building.")
    parser.add_argument("--output", default="data/papers")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    sources = []
    for paper in PAPERS:
        destination = output / paper["filename"]
        if not destination.exists():
            temporary = destination.with_suffix(".part")
            with urllib.request.urlopen(paper["url"]) as response, temporary.open("wb") as stream:
                shutil.copyfileobj(response, stream)
            temporary.replace(destination)
            print(f"downloaded {paper['title']}")
        sources.append({**paper, "sha256": sha256(destination), "size_bytes": destination.stat().st_size})

    (output / "SOURCES.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
