"""Thin, defect-masking tests for the planted fixture.

These cover only ``total`` (which is correct), so the suite is GREEN while the
planted defects in ``add`` / ``average`` / ``apply_discount`` remain latent -
the reviewer must READ the code, not merely run the tests, to find them.
"""
from calc import total


def test_total_sums_prices():
    assert total([1, 2, 3]) == 6


def test_total_empty_is_zero():
    assert total([]) == 0
