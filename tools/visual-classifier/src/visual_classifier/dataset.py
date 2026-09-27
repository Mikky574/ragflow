from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

COLUMNS = (
    "id", "image_path", "source_file", "page", "bbox", "ocr_text", "visual_type",
    "visual_score", "index_action", "label",
)


def connect(path: str | Path) -> sqlite3.Connection:
    database = Path(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("""
        CREATE TABLE IF NOT EXISTS visual_candidates (
            id TEXT PRIMARY KEY,
            image_path TEXT NOT NULL,
            source_file TEXT NOT NULL DEFAULT '',
            page INTEGER,
            bbox TEXT,
            ocr_text TEXT NOT NULL DEFAULT '',
            visual_type TEXT,
            visual_score REAL,
            index_action TEXT,
            label TEXT NOT NULL DEFAULT ''
        )
    """)
    return connection


def upsert_rows(path: str | Path, rows: Iterable[dict]) -> int:
    connection = connect(path)
    count = 0
    try:
        for row in rows:
            payload = {column: row.get(column) for column in COLUMNS}
            payload["bbox"] = None if payload["bbox"] is None else json.dumps(payload["bbox"])
            payload["source_file"] = payload["source_file"] or ""
            payload["ocr_text"] = payload["ocr_text"] or ""
            payload["label"] = payload["label"] or ""
            connection.execute("""
                INSERT INTO visual_candidates (id, image_path, source_file, page, bbox, ocr_text, visual_type, visual_score, index_action, label)
                VALUES (:id, :image_path, :source_file, :page, :bbox, :ocr_text, :visual_type, :visual_score, :index_action, :label)
                ON CONFLICT(id) DO UPDATE SET
                    image_path = excluded.image_path,
                    source_file = excluded.source_file,
                    page = excluded.page,
                    bbox = excluded.bbox,
                    ocr_text = excluded.ocr_text,
                    visual_type = excluded.visual_type,
                    visual_score = excluded.visual_score,
                    index_action = excluded.index_action,
                    label = CASE WHEN excluded.label <> '' THEN excluded.label ELSE visual_candidates.label END
            """, payload)
            count += 1
        connection.commit()
    finally:
        connection.close()
    return count


def export_rows(path: str | Path) -> list[dict]:
    connection = connect(path)
    try:
        rows = [dict(row) for row in connection.execute("SELECT * FROM visual_candidates ORDER BY id")]
    finally:
        connection.close()
    for row in rows:
        if row["bbox"]:
            row["bbox"] = json.loads(row["bbox"])
    return rows
