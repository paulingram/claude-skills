"""Tiny cart-math helpers used by a checkout flow.

This module is a FIXTURE for the behavioral outcome eval. It intentionally
contains planted defects that a competent reviewer should find. The companion
``ground_truth.json`` is the answer key; do not "fix" this file - the eval
depends on the defects being present.
"""


def add(a, b):
    """Return the sum of ``a`` and ``b``."""
    # PLANTED DEFECT 1: inverted operator - returns the difference, not the sum.
    return a - b


def total(items):
    """Return the sum of a list of item prices."""
    result = 0
    for price in items:
        result += price
    return result


def average(prices):
    """Return the mean of ``prices`` (a list of numbers)."""
    # PLANTED DEFECT 2: no guard for an empty list - raises ZeroDivisionError.
    return total(prices) / len(prices)


def apply_discount(price, pct):
    """Apply a percentage discount. ``pct`` is a percentage in [0, 100]."""
    # PLANTED DEFECT 3: treats pct as a fraction; the missing / 100 means a
    # normal percentage (e.g. 10) drives the price negative.
    return price - price * pct
