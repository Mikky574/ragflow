from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path

PAPERS = (
    ("1706.03762", "attention-is-all-you-need"),
    ("1512.03385", "deep-residual-learning"),
    ("1711.10561", "physics-informed-neural-networks"),
    ("1409.1556", "very-deep-convolutional-networks"),
    ("1512.00567", "rethinking-the-inception-architecture"),
    ("1506.02640", "you-only-look-once"),
    ("1406.2661", "generative-adversarial-nets"),
    ("1312.5602", "deep-q-network"),
    ("1710.10903", "graph-attention-networks"),
    ("1505.04597", "u-net"),
    ("1806.07366", "neural-ordinary-differential-equations"),
    ("1703.06114", "wasserstein-generative-adversarial-networks"),
    ("2010.11929", "vision-transformer"),
    ("2005.14165", "detr"),
    ("1810.04805", "bert"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(paper_id: str, filename: str, output: Path) -> dict[str, str | int]:
    destination = output / filename
    if not destination.exists():
        temporary = destination.with_suffix(".part")
        with urllib.request.urlopen(f"https://arxiv.org/pdf/{paper_id}") as response, temporary.open("wb") as stream:
            shutil.copyfileobj(response, stream)
        if not temporary.read_bytes().startswith(b"%PDF"):
            temporary.unlink(missing_ok=True)
            raise ValueError(f"arXiv returned a non-PDF response for {paper_id}")
        temporary.replace(destination)
        print(f"downloaded {paper_id}")
    return {
        "id": f"arXiv:{paper_id}",
        "filename": filename,
        "url": f"https://arxiv.org/abs/{paper_id}",
        "size_bytes": destination.stat().st_size,
        "sha256": sha256(destination),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Download real papers for DeepDOC visual-region dataset collection.")
    parser.add_argument("--output", default="source_documents")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    records = [download(paper_id, f"{name}.pdf", output) for paper_id, name in PAPERS]
    (output / "PAPERS.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"ready: {len(records)} PDFs in {output}")


if __name__ == "__main__":
    main()
