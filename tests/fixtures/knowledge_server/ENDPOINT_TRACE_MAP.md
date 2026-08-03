---
last_traced: 2026-08-01T10:30:00Z
codebase: /repo/shop
scope_subset: [GET /api/orders]
witness_verified: true
map_invalidated: []
---

# Endpoint Trace Map — shop

## GET /api/orders

`list_orders` reads the `orders` asset through `OrderRepo.fetch`.

- func://shop/src/services/orders.py#list_orders
- func://shop/src/repo/order_repo.py#OrderRepo.fetch
