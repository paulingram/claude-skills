"""Models: no in-repo imports -- the leaf of the fixture import graph."""
from dataclasses import dataclass


@dataclass
class Item:
    sku: str
    cents: int


def parse_item(raw: str) -> Item:
    sku, cents = raw.split(":")
    return Item(sku=sku, cents=int(cents))
