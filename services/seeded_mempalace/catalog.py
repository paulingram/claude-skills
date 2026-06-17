# -*- coding: utf-8 -*-
"""The phenotype catalog (SMP-4) — stdlib-only, REUSING the existing phenotype store.

SMP-4: the seeded MemPalace is where phenotypes are stored, with a future model in
which users PURCHASE a phenotype list/catalog. This builds a browseable catalog
from the repo's existing phenotype subsystem (`scripts/phenotypes/phenotypes.py` +
`phenotypes/<label>/phenotype.json`) — reuse-first, NOT a new phenotype schema —
and gates the FULL records by entitlement so a non-owner browses the metadata but
only downloads what they're entitled to.

HONEST BOUNDARY: the actual purchase / billing / entitlement issuance is an
external system; here entitlement is an injected set, and the catalog is the
deterministic browse + gate contract over it.
"""
from __future__ import annotations

import copy
import pathlib
import sys
from typing import Any, Iterable

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "scripts" / "phenotypes"))
import phenotypes as _phenotypes  # noqa: E402

CATALOG_SCHEMA = "phenotype-catalog/v1"
# the browse-metadata fields shown for EVERY entry (owned or not)
_BROWSE_FIELDS = ("label", "name", "version", "kind", "summary")


def _entry(record: dict[str, Any], *, owned: bool) -> dict[str, Any]:
    label = record.get("label") or record.get("_label_dir")
    e = {k: record.get(k) for k in _BROWSE_FIELDS}
    e["label"] = label
    e["entitlement"] = "owned" if owned else "purchasable"
    # the master catalog keeps the FULL record on every entry; `gate_catalog`
    # strips it from non-entitled entries when serving a specific requester.
    # Strip the discover_phenotypes-injected internal fields (`_dir` / `_label_dir`)
    # so the served record never leaks the operator's absolute filesystem layout.
    e["record"] = {k: v for k, v in record.items() if not str(k).startswith("_")}
    return e


def build_catalog(phenotypes: Iterable[dict[str, Any]], *, owned: Iterable[str] = ()) -> dict[str, Any]:
    """Build the MASTER phenotype catalog (SMP-4) from phenotype records. Every entry
    carries browse metadata + an `entitlement` (owned/purchasable) + the FULL
    `record`. Serving gates it per-requester via `gate_catalog`."""
    owned_set = set(owned)
    entries = []
    for rec in phenotypes:
        label = rec.get("label") or rec.get("_label_dir")
        entries.append(_entry(rec, owned=label in owned_set))
    entries.sort(key=lambda e: e["label"] or "")
    return {"schema": CATALOG_SCHEMA, "entries": entries}


def catalog_from_store(*, owned: Iterable[str] = (), dir=None) -> dict[str, Any]:
    """Build the master catalog from the repo's phenotype store (reuse
    `discover_phenotypes`)."""
    return build_catalog(_phenotypes.discover_phenotypes(dir), owned=owned)


def gate_catalog(catalog: dict[str, Any], entitlements: Iterable[str]) -> dict[str, Any]:
    """Return a copy of `catalog` gated to `entitlements` (the SMP-4 purchase model):
    an entry whose label is entitled keeps `entitlement: owned` + its full `record`;
    any other becomes `purchasable` with `record: None` (browse metadata only)."""
    ent = set(entitlements)
    gated = []
    for e in catalog.get("entries", []):
        owned = e.get("label") in ent
        g = dict(e)
        g["entitlement"] = "owned" if owned else "purchasable"
        # DEEP-copy the served record so a caller mutating it can't write through
        # to the master catalog (which is held + re-served across requests).
        g["record"] = copy.deepcopy(e.get("record")) if owned else None
        gated.append(g)
    return {"schema": catalog.get("schema", CATALOG_SCHEMA), "entries": gated}


def entitled_labels(catalog: dict[str, Any]) -> list[str]:
    """The labels marked `owned` in a (gated) catalog — i.e. the downloadable set."""
    return sorted(
        e.get("label") for e in catalog.get("entries", [])
        if e.get("entitlement") == "owned" and e.get("label")
    )
