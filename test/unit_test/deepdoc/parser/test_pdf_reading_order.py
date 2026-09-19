"""Reading order after OCR and layout detection, without loading model weights."""

from copy import deepcopy

import pytest

from rag.app.naive import Pdf


def _box(text, page, column, top):
    left = 45 if column == 0 else 315
    return {
        "text": text,
        "page_number": page,
        "col_id": column,
        "x0": left,
        "x1": left + 254,
        "top": top,
        "bottom": top + 12,
        "layoutno": text,
        "layout_type": "text",
    }


@pytest.mark.parametrize("separate_tables_figures", [False, True])
@pytest.mark.parametrize("two_columns", [False, True])
def test_pdf_sections_follow_columns_across_pages(monkeypatch, separate_tables_figures, two_columns):
    parser = Pdf.__new__(Pdf)
    # Page 2's left column begins below two figures, while its right column
    # begins higher up. Page 1 ends in the right column.
    boxes = [
        _box("previous page ends as well", 1, 1 if two_columns else 0, 700),
        _box("as the efficiency at large BOP", 2, 0, 1233),
        _box("power consumption can be reduced and", 2, 0, 1500),
        _box("high efficiency can be achieved", 2, 1 if two_columns else 0, 1035 if two_columns else 1520),
    ]
    parser.boxes = deepcopy(list(reversed(boxes)))
    parser.mean_height = [12, 12]
    parser.mean_width = [6, 6]
    parser.is_english = True
    monkeypatch.setattr(parser, "__images__", lambda *args: None)
    monkeypatch.setattr(parser, "_layouts_rec", lambda *args: None)
    monkeypatch.setattr(parser, "_table_transformer_job", lambda *args: None)
    monkeypatch.setattr(parser, "_extract_table_figure", lambda *args: ([], []) if separate_tables_figures else [])
    monkeypatch.setattr(parser, "_line_tag", lambda box, zoom: str(box["page_number"]))

    result = parser("example.pdf", callback=lambda *args, **kwargs: None, separate_tables_figures=separate_tables_figures)

    assert [text for text, _ in result[0]] == [box["text"] for box in boxes]
    assert [tag for _, tag in result[0]] == ["1", "2", "2", "2"]
    # Sorting must preserve the coordinates used for source highlighting.
    assert parser.boxes == boxes


def test_reading_order_keeps_spanning_blocks_and_short_paragraph_lines():
    parser = Pdf.__new__(Pdf)
    title = _box("full-width title", 1, 0, 10)
    title["x1"] = 570
    footer = _box("full-width footer", 1, 0, 760)
    footer["x1"] = 570
    left = [_box(f"left {i}", 1, 0, 430 + i * 20) for i in range(3)]
    right = [_box(f"right {i}", 1, 1, 230 + i * 20) for i in range(3)]
    for box in right:
        box["layoutno"] = "right-paragraph"
    fragment = _box("indented short line", 1, 3, 240)
    fragment.update(x0=523, x1=567, layoutno="right-paragraph")
    parser.boxes = [footer, fragment, *reversed(right), *reversed(left), title]

    parser._final_reading_order_merge()

    assert parser.boxes == [title, *left, right[0], fragment, *right[1:], footer]
