from deepdoc.parser.pdf_parser import RAGFlowPdfParser
from deepdoc.vision.table_structure_recognizer import TableStructureRecognizer
from rag.nlp import _strip_leading_page_range


def test_assign_column_ignores_figure_origins():
    parser = object.__new__(RAGFlowPdfParser)
    boxes = [
        {"page_number": 1, "x0": 40, "x1": 260, "layout_type": "text", "text": "left"},
        {"page_number": 1, "x0": 45, "x1": 265, "layout_type": "text", "text": "left again"},
        {"page_number": 1, "x0": 330, "x1": 550, "layout_type": "text", "text": "right"},
        {"page_number": 1, "x0": 335, "x1": 555, "layout_type": "text", "text": "right again"},
        {"page_number": 1, "x0": 180, "x1": 440, "layout_type": "figure", "text": "axis"},
    ]

    RAGFlowPdfParser._assign_column(parser, boxes)

    assert {boxes[0]["col_id"], boxes[1]["col_id"]} == {0}
    assert {boxes[2]["col_id"], boxes[3]["col_id"]} == {1}


def test_construct_table_discards_figure_reference_from_caption():
    boxes = [
        {"text": "TABLE I RESULTS Fig. 9. Spectrum", "layout_type": "table caption"},
        {"text": "Value", "R": 0, "R_bott": 10, "R_top": 0, "bottom": 10, "top": 0, "x0": 0, "x1": 10, "page_number": 1},
    ]

    html = TableStructureRecognizer.construct_table(boxes, html=True)

    assert "TABLE I RESULTS" in html
    assert "Fig. 9" not in html


def test_strip_page_range_immediately_before_table_html():
    assert _strip_leading_page_range("77-80.\n<table><caption>TABLE I</caption></table>") == "<table><caption>TABLE I</caption></table>"
    assert _strip_leading_page_range("77-80. Results are summarized below.") == "77-80. Results are summarized below."
