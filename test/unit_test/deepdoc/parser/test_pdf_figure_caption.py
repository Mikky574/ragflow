from deepdoc.parser.pdf_parser import _figure_caption_text


def test_figure_caption_text_excludes_figure_ocr(monkeypatch):
    def is_caption(box):
        return box.get("text", "").startswith("Fig.")

    monkeypatch.setattr(
        "deepdoc.parser.pdf_parser.TableStructureRecognizer.is_caption",
        is_caption,
    )

    text = _figure_caption_text(
        [
            {"text": "60", "layout_type": "figure"},
            {"text": "Efficiency [%]", "layout_type": "figure"},
            {"text": "Fig. 2. Full schematic of the class-F PA.", "layout_type": "text"},
        ]
    )

    assert text == "Fig. 2. Full schematic of the class-F PA."


def test_figure_caption_text_accepts_layout_caption_without_pattern(monkeypatch):
    monkeypatch.setattr(
        "deepdoc.parser.pdf_parser.TableStructureRecognizer.is_caption",
        lambda box: False,
    )

    assert _figure_caption_text([{"text": "Fig. 4. Circuit topology", "layout_type": "figure caption"}]) == "Fig. 4. Circuit topology"


def test_figure_caption_text_rejects_ambiguous_merged_captions(monkeypatch):
    monkeypatch.setattr(
        "deepdoc.parser.pdf_parser.TableStructureRecognizer.is_caption",
        lambda box: True,
    )

    assert _figure_caption_text(
        [{"text": "Fig. 2. Circuit\nFig. 3. Measurement", "layout_type": "text"}]
    ) == ""


def test_figure_caption_text_prefers_caption_over_body_reference(monkeypatch):
    monkeypatch.setattr(
        "deepdoc.parser.pdf_parser.TableStructureRecognizer.is_caption",
        lambda box: box.get("text", "").startswith("Fig."),
    )

    text = _figure_caption_text(
        [
            {"text": "Fig. 1(a) shows the conventional amplifier.", "layout_type": "text"},
            {"text": "Fig. 1. Schematic of the conventional amplifier.", "layout_type": "figure caption"},
        ]
    )

    assert text == "Fig. 1. Schematic of the conventional amplifier."
