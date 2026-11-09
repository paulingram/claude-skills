"""API: imports pricing (relative) and models (two hops from the leaf)."""
from . import models
from .pricing import price_for

ROUTES = {"items": "/api/items", "checkout": "/api/checkout"}


def list_items(raw_items):
    return [models.parse_item(r) for r in raw_items]


def checkout_total(raw_items, quantity):
    return sum(price_for(item, quantity) for item in list_items(raw_items))
