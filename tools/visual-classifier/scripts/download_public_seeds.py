from __future__ import annotations

import argparse
import shutil
import tarfile
import urllib.request
import zipfile
from pathlib import Path

SOURCES = {
    "equation-handwritten": (
        "https://huggingface.co/datasets/Azu/Handwritten-Mathematical-Expression-Convert-LaTeX/resolve/main/data.zip",
        "data.zip",
        "zip",
    ),
    "diagrambank": (
        "https://huggingface.co/datasets/ghzlmc/DiagramBank/resolve/main/data/ICLR_2017_accept_oral.tar.gz",
        "ICLR_2017_accept_oral.tar.gz",
        "tar.gz",
    ),
}


def download(url: str, path: Path) -> None:
    if path.exists():
        print(f"reusing {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    with urllib.request.urlopen(url) as response, temporary.open("wb") as stream:
        shutil.copyfileobj(response, stream)
    temporary.replace(path)
    print(f"downloaded {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download public equation and scientific-schematic seed datasets.")
    parser.add_argument("--output", default="data/source")
    args = parser.parse_args()
    root = Path(args.output)

    equation_url, equation_name, _ = SOURCES["equation-handwritten"]
    equation_root = root / "equation-handwritten"
    equation_archive = equation_root / equation_name
    download(equation_url, equation_archive)
    equation_raw = equation_root / "raw"
    if not equation_raw.exists():
        with zipfile.ZipFile(equation_archive) as archive:
            archive.extractall(equation_raw)
        print(f"extracted {equation_raw}")

    diagram_url, diagram_name, _ = SOURCES["diagrambank"]
    diagram_root = root / "diagrambank"
    diagram_archive = diagram_root / diagram_name
    download(diagram_url, diagram_archive)
    diagram_raw = diagram_root / "raw"
    if not diagram_raw.exists():
        with tarfile.open(diagram_archive, "r:gz") as archive:
            root = diagram_raw.resolve()
            for member in archive:
                destination = (diagram_raw / member.name).resolve()
                if root not in destination.parents and destination != root:
                    raise ValueError(f"unsafe archive member: {member.name}")
                archive.extract(member, diagram_raw)
        print(f"extracted {diagram_raw}")


if __name__ == "__main__":
    main()
