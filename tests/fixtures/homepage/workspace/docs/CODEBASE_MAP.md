---
last_mapped: 2026-08-01T08:30:00Z
codebase: shop
confirmed: true
---

# Codebase map: shop

## Layers

- `src/api/` the HTTP layer
- `src/services/` business rules
- `src/repo/` persistence

## Conventions

Stdlib-only Python; one module per concern.

## Gotchas

`totals.py` rounds half-up on purpose.
