# Orders service conventions

This document describes how the orders service is built. It is prose first;
the rules are in the sections below.

## Architecture principles

- Every service owns its own tables; no cross-service joins.
- Services talk to billing over its HTTP API, not its database.
- Keep it simple

## Testing standards

1. Tests must run offline with no network access.
2. Test names say the behaviour, not the method name.

## Notes

The team should never log a customer secret. Logging is otherwise fine.
We only deploy on weekdays. Fridays are for cleanup.

```bash
# this must never be extracted
echo "always quoted"
```

## History

The service was extracted from the monolith in 2024. It has always been small.
