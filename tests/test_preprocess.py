"""Tests for DocAI.preprocess, the OCR character-correction step.

preprocess repairs two kinds of OCR mistake in nutrition cells: the letter "o"
or "O" read in place of a zero, and a unit suffix "g" read as a digit. The
"o" -> "0" repairs behave correctly and are pinned below. The suffix repair does
not: it also fires on values that are already valid numbers, which is the data
corruption reported in issue #13.
"""

import pytest

from DocAI import preprocess


def test_letter_o_is_corrected_to_zero_when_processing():
    assert preprocess("2o", True) == "20"


def test_letter_o_is_corrected_to_zero_when_not_processing():
    assert preprocess("1O0", False) == "100"


def test_decimal_value_is_left_alone():
    assert preprocess("5.2", True) == "5.2"


def test_process_and_non_process_fallbacks_are_identical():
    """The ValueError branch and the else branch run the same replacement."""
    for value in ("lo", "O", "ab"):
        assert preprocess(value, True) == preprocess(value, False)


@pytest.mark.xfail(
    reason="issue #13: when the cell already parses as a number, preprocess "
    "still rewrites a trailing 9 or 0 into 'g', so valid values are corrupted"
)
@pytest.mark.parametrize("value", ["1200", "129", "90", "120"])
def test_valid_numbers_should_survive_unchanged(value):
    assert preprocess(value, True) == value
