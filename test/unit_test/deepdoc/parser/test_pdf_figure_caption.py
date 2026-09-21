from deepdoc.parser.pdf_parser import _figure_ocr_text


def test_figure_ocr_text_keeps_caption_and_figure_ocr(monkeypatch):
    def is_caption(box):
        return box.get("text", "").startswith("Fig.")

    monkeypatch.setattr(
        "deepdoc.parser.pdf_parser.TableStructureRecognizer.is_caption",
        is_caption,
    )

    text = _figure_ocr_text(
        [
            {"text": "60", "layout_type": "figure"},
            {"text": "Efficiency [%]", "layout_type": "figure"},
            {"text": "Fig. 2. Full schematic of the class-F PA.", "layout_type": "text"},
        ]
    )

    assert text == "Fig. 2. Full schematic of the class-F PA.\n60\nEfficiency [%]"


def test_figure_ocr_text_keeps_layout_caption_without_pattern(monkeypatch):
    monkeypatch.setattr(
        "deepdoc.parser.pdf_parser.TableStructureRecognizer.is_caption",
        lambda box: False,
    )

    assert _figure_ocr_text([{"text": "Fig. 4. Circuit topology", "layout_type": "figure caption"}]) == "Fig. 4. Circuit topology"


def test_figure_ocr_text_drops_ambiguous_caption_but_keeps_ocr(monkeypatch):
    monkeypatch.setattr(
        "deepdoc.parser.pdf_parser.TableStructureRecognizer.is_caption",
        lambda box: box.get("text", "").startswith("Fig."),
    )

    assert _figure_ocr_text(
        [
            {"text": "Fig. 2. Circuit\nFig. 3. Measurement", "layout_type": "text"},
            {"text": "Frequency [GHz]", "layout_type": "figure"},
        ]
    ) == "Frequency [GHz]"


def test_figure_ocr_text_deduplicates_repeated_lines(monkeypatch):
    monkeypatch.setattr(
        "deepdoc.parser.pdf_parser.TableStructureRecognizer.is_caption",
        lambda box: box.get("text", "").startswith("Fig."),
    )

    text = _figure_ocr_text(
        [
            {"text": "Gain [dB]", "layout_type": "figure"},
            {"text": "gain [dB]", "layout_type": "figure"},
            {"text": "Fig. 1. Gain curve", "layout_type": "figure caption"},
        ]
    )

    assert text == "Fig. 1. Gain curve\nGain [dB]"
