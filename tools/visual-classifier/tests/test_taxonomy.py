from visual_classifier.taxonomy import decide, load_taxonomy


def test_taxonomy_has_equation_and_skip_classes():
    taxonomy = load_taxonomy("config/classes.yaml")
    assert taxonomy["equation"].action == "index"
    assert taxonomy["logo"].action == "skip"


def test_low_confidence_requires_review():
    taxonomy = load_taxonomy("config/classes.yaml")
    result = decide({"equation": 0.4, "logo": 0.3}, taxonomy, threshold=0.55)
    assert result["visual_type"] == "equation"
    assert result["index_action"] == "review"


def test_high_confidence_logo_is_skipped():
    taxonomy = load_taxonomy("config/classes.yaml")
    result = decide({"equation": 0.1, "logo": 0.9}, taxonomy, threshold=0.55)
    assert result["index_action"] == "skip"
