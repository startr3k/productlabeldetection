"""Tests for DocAI.preprocess, the OCR character-correction step."""

from DocAI import preprocess


def test_float_value_is_unchanged_when_processing():
    assert preprocess("5.2", True) == "5.2"


def test_trailing_zero_becomes_g_when_processing():
    assert preprocess("1200", True) == "120g"


def test_trailing_nine_becomes_g_when_processing():
    assert preprocess("129", True) == "12g"


def test_non_numeric_with_process_converts_o_to_zero():
    assert preprocess("2o", True) == "20"


def test_non_numeric_without_process_converts_o_to_zero():
    assert preprocess("1O0", False) == "100"


def test_process_and_non_process_fallbacks_are_identical():
    """The ValueError branch and the else branch run the same replacement."""
    for value in ("lo", "O", "ab"):
        assert preprocess(value, True) == preprocess(value, False)
