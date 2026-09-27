from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from PIL import Image

LAYOUT_TYPES = {"figure", "table", "equation"}


def area(rect: tuple[float, float, float, float]) -> float:
    left, top, right, bottom = rect
    return max(0.0, right - left) * max(0.0, bottom - top)


def overlap_ratio(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    intersection = area((left, top, right, bottom))
    smallest = min(area(first), area(second))
    return intersection / smallest if smallest else 0.0


def crop_region(image: Image.Image, rect: tuple[float, float, float, float], zoomin: int) -> Image.Image | None:
    left, top, right, bottom = (round(value * zoomin) for value in rect)
    left = max(0, left)
    top = max(0, top)
    right = min(image.width, right)
    bottom = min(image.height, bottom)
    if right <= left or bottom <= top:
        return None
    return image.crop((left, top, right, bottom))


def slug(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return clean or "document"


def unique_layouts(layouts: Iterable[dict[str, Any]], requested_types: set[str]) -> list[dict[str, Any]]:
    priority = {"equation": 0, "table": 1, "figure": 2}
    candidates = [layout for layout in layouts if layout.get("type") in requested_types]
    candidates.sort(key=lambda item: (priority[item["type"]], item["top"], item["x0"]))
    selected = []
    for layout in candidates:
        rect = (layout["x0"], layout["top"], layout["x1"], layout["bottom"])
        if any(overlap_ratio(rect, (chosen["x0"], chosen["top"], chosen["x1"], chosen["bottom"])) >= 0.95 for chosen in selected):
            continue
        selected.append(layout)
    return selected


def ocr_text_for_region(boxes: Iterable[dict[str, Any]], page_number: int, rect: tuple[float, float, float, float]) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for box in boxes:
        text = (box.get("text") or "").strip()
        for position in box.get("positions") or []:
            if len(position) != 5 or int(position[0]) != page_number:
                continue
            candidate = tuple(float(value) for value in position[1:])
            if overlap_ratio(rect, candidate) < 0.1:
                continue
            normalized = re.sub(r"\s+", " ", text).strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                lines.append(text)
            break
    return "\n".join(lines)


def export_pdf(pdf_path: Path, output_root: Path, zoomin: int, requested_types: set[str], min_edge: int) -> list[dict[str, Any]]:
    from deepdoc.parser.pdf_parser import RAGFlowPdfParser

    parser = RAGFlowPdfParser()
    boxes = parser.parse_into_bboxes(str(pdf_path), zoomin=zoomin)
    document_id = f"{slug(pdf_path.stem)}-{hashlib.sha1(str(pdf_path.resolve()).encode()).hexdigest()[:8]}"
    document_root = output_root / document_id
    document_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    index = 0
    for page_index, layouts in enumerate(parser.page_layout):
        for layout in unique_layouts(layouts, requested_types):
            rect = (float(layout["x0"]), float(layout["top"]), float(layout["x1"]), float(layout["bottom"]))
            image = crop_region(parser.page_images[page_index], rect, zoomin)
            if image is None or min(image.size) < min_edge:
                continue
            index += 1
            layout_type = str(layout["type"])
            filename = f"p{page_index + 1:03d}_{layout_type}_{index:03d}.png"
            image_path = document_root / filename
            image.save(image_path)
            records.append({
                "id": f"{document_id}__{filename.removesuffix('.png')}",
                "image_path": str(image_path.resolve()),
                "source_file": str(pdf_path.resolve()),
                "page": page_index + 1,
                "bbox": [round(value, 2) for value in rect],
                "layout_type": layout_type,
                "ocr_text": ocr_text_for_region(boxes, page_index + 1, rect),
                "label": "",
            })
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract DeepDOC figure, table and equation regions from a PDF directory.")
    parser.add_argument("--input", default="source_papers", help="PDF directory, searched recursively")
    parser.add_argument("--output", default="candidates")
    parser.add_argument("--zoomin", type=int, default=3)
    parser.add_argument("--min-edge", type=int, default=24)
    parser.add_argument("--types", nargs="+", choices=sorted(LAYOUT_TYPES), default=sorted(LAYOUT_TYPES))
    args = parser.parse_args()

    input_root = Path(args.input)
    pdfs = [input_root] if input_root.is_file() and input_root.suffix.lower() == ".pdf" else sorted(path for path in input_root.rglob("*") if path.suffix.lower() == ".pdf")
    if not pdfs:
        raise SystemExit(f"no PDF files found under {input_root}")
    output_root = Path(args.output)
    output_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for pdf_path in pdfs:
        try:
            exported = export_pdf(pdf_path, output_root, args.zoomin, set(args.types), args.min_edge)
            records.extend(exported)
            print(f"{pdf_path.name}: exported {len(exported)} regions")
        except Exception as error:
            errors.append({"source_file": str(pdf_path), "error": str(error)})
            print(f"{pdf_path.name}: failed: {error}")

    with (output_root / "manifest.jsonl").open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    with (output_root / "errors.jsonl").open("w", encoding="utf-8") as stream:
        for error in errors:
            stream.write(json.dumps(error, ensure_ascii=False) + "\n")
    print(f"finished: {len(records)} regions from {len(pdfs)} PDFs; {len(errors)} failures")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
