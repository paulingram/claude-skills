---
name: reuse-first-design
description: Use when authoring or refining any OpenSpec proposal/specs/design/tasks artifact, when making architectural decisions, or when proposing a new module/file/dependency. Enforces extend-before-compose-before-reuse-before-build-new, with a mandatory Reuse Decision Log anchored in CODEBASE_MAP.md and INTEGRATION_MAP.md. Rejects rationalizations like "cleaner as a new module" or "faster to just write it fresh."
---

# Reuse-First Design

Every new module, file, component, or dependency degrades the system unless it earns its existence. Reuse-first design is the discipline of proving that earning. This skill makes the proof explicit.

## The Priority Ladder (non-negotiable)

1. **Extend** an existing module — add a method, branch, or component to something that already exists.
2. **Compose** with existing modules via their public interface.
3. **Reuse** an existing module as-is.
4. **Build new** — only when 1-3 are demonstrably insufficient, AND only with a documented Reuse Decision.

Climb the ladder from the top. You cannot skip rungs without naming why.

## Mandatory pre-design audit

Before proposing ANY new module / file / component / dependency:

1. Read `<codebase>/docs/CODEBASE_MAP.md` for every codebase in scope.
2. Read `<workspace>/docs/INTEGRATION_MAP.md`.
3. Enumerate every existing capability that overlaps with what you're proposing. List them by `file:symbol`.
4. For each, ask in order: Can I extend it? Can I compose with it? Can I reuse it? If no — why not, with evidence.

If you have not done this audit, you do not get to propose new code.

## The Reuse Decision Log

Every `design.md` MUST contain a `## Reuse Decisions` section. One entry per proposed new module / file / component / dependency:

```markdown
### <proposed-new-thing>
- **Existing considered:** `src/foo/bar.py:Bar` (from CODEBASE_MAP.md §2.3)
- **Extension attempted:** Add `process_with_retry()` method to `Bar`.
- **Why not sufficient:** `Bar` is a sync class. This work is async-only and would require a parallel async hierarchy on `Bar`. Extending pollutes Bar's single responsibility (sync data normalization).
- **Decision:** New module `src/foo/async_processor.py` that composes `Bar` for sync transforms and adds async I/O around it.
- **Net new files:** `src/foo/async_processor.py`, `tests/foo/test_async_processor.py`
```

No entry → not allowed in the design. The Phase 1 validation loop will reject any new module without a corresponding Reuse Decision and any Reuse Decision that cites a nonexistent file/symbol.

## Best-in-class principles (applied during authoring)

| Principle | Concrete check |
|---|---|
| **DRY** | No new file re-implements logic that exists in CODEBASE_MAP.md. If you see "this is similar to X but…", the answer is "extend X to handle 'but'." |
| **YAGNI** | No abstractions for "future flexibility" — only what the current requirements need. If you can't name the current caller, the abstraction is premature. |
| **SRP** | Each new module has one clear purpose, expressible in one sentence. |
| **Smallest blast radius** | Prefer changes touching the fewest files. Three small targeted edits beat one new file. |
| **Honor existing contracts** | Add new endpoints/methods over changing existing ones, unless requirements explicitly demand a break (cite the requirement). |
| **Stack-canonical libraries** | Use libraries already in `pyproject.toml` / `package.json` / etc. before introducing new ones. |
| **Match existing conventions** | Naming, file organization, error handling, logging, testing — pull from CODEBASE_MAP.md and quote the convention you're matching. |
| **Composition over inheritance** | Where the language allows, compose. Inheritance is a last resort and must be justified. |

## Anti-pattern rationalizations to reject

| Rationalization | Rebuttal |
|---|---|
| "It's cleaner as a new module" | Cleanness is a tradeoff against duplication. Reuse-first wins unless `duplication_cost > coupling_cost`, which you must demonstrate. Subjective "cleaner" doesn't qualify. |
| "The existing one wasn't designed for this" | Then propose an extension. "Wasn't designed for it" ≠ "can't be extended." |
| "It's faster to just write it fresh" | Cost-to-write is one cost. Cost-to-maintain-two-implementations is permanent. The faster choice today is the slower team velocity tomorrow. |
| "I don't want to risk breaking the existing one" | Test coverage that the Phase 3 review gate already requires solves this. If the existing module lacks coverage, add it as part of your extension — that's part of the work. |
| "The existing one is in a different layer/service" | Then the integration map should show the connection. If the capability is genuinely needed in two layers, extract the common piece (still extension, just at the boundary). |
| "The existing one uses an old pattern; I want the new pattern" | Then your change is "migrate X to the new pattern" — a separate, scoped task. Do not silently fork. |
| "I'll mark this as new but it's basically the same logic" | If it's the same logic, it's the same module. Mark it correctly or restructure. |

## Output discipline

When authoring or refining any OpenSpec artifact:

- Cite specific files / symbols from CODEBASE_MAP.md by `file:line` or `file:symbol`.
- Quote the existing convention (snippet) when you're matching it.
- Reject any new dependency that lacks a "why not the existing stack libraries" comparison. New deps go in a `## Dependency Decisions` section with the same Reuse Decision structure: what's already available, what was attempted, why insufficient.
- For Phase 3 review-gate compliance: every file you create or modify must correspond to a Reuse Decision. Grep the diff for new file paths before declaring a task done.

## Read this before you start designing

If you're about to author a `proposal.md` / `design.md` / `tasks.md` / `specs/<requirement>.md`, the order is:

1. Read the relevant CODEBASE_MAP / INTEGRATION_MAP sections.
2. Enumerate overlapping capabilities.
3. Apply the ladder.
4. Document every "build new" with a Reuse Decision.
5. Then write the artifact.

If you skip step 1, you will rationalize new code that already exists somewhere.
