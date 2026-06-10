---
description: Absorb any arbitrary codebase into a new labeled phenotype — analyze it (read-only), generalize a blueprint + a parameterized scaffold, write + validate the phenotype.json, and index it for reuse. The generalized form of how the seed phenotypes were authored.
argument-hint: <path-to-codebase> --label <name> [--kind pair|singleton]
---

# Absorb a phenotype

Invoke the `phenotype-absorption` skill from this plugin (use the Skill tool with
`skill: phenotype-absorption`) against the arguments below and follow its phases (P1 → P6) exactly.

## Argument parsing (do this first)

- **First positional** (or `--path <path>`): the target codebase path — a directory; for a pair, the
  parent dir, or pass two explicit paths. REQUIRED.
- **`--label <name>`**: the kebab-case phenotype label (becomes `phenotypes/<name>/`). REQUIRED.
  Refuse if a phenotype with that label already exists.
- **`--kind pair|singleton`**: `pair` (backend + frontend) or `singleton` (one repo / IaC monorepo).
  Default: infer from the target (a BE+FE pair → `pair`; a single repo → `singleton`) and confirm the
  inference with the user.

If `--label` is missing, ask for it (the only thing you may ask for). If `<path>` does not resolve to
a directory, say so and stop.

## What it does (see `skills/phenotype-absorption`)

Recon → parallel deep analysis (READ-ONLY on the source) → synthesize a generalized blueprint → derive
a parameterized scaffold → write + `validate` the `phenotype.json` → mine into MemPalace → report. The
result is a new `phenotypes/<label>/` record consumable via `--phenotype <label>` or reuse-first
auto-suggest (`skills/phenotypes`).

## Safety (non-negotiable)

- NEVER modify or execute the target codebase — analysis only.
- NEVER embed secrets / account-ids / domains in the produced record — parameters/placeholders only.
- The new record MUST pass `$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/phenotypes/phenotypes.py" validate <label>` before completion. The `$(command -v python3 || command -v python)` substitution selects the interpreter once (the v2.16.0 detect-once form), and `${CLAUDE_PLUGIN_ROOT}` anchors the script path so it resolves regardless of the cwd.
- The produced record is reviewed by the same gates as any shipped artifact.
