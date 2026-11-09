"""Pricing: imports models (one hop from the leaf)."""
from fixpkg import models

PRICES_ENDPOINT = "/api/prices"


def price_for(item: models.Item, quantity: int) -> int:
    return item.cents * quantity
