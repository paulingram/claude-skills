# architect-team

Spec-to-production multi-agent coding pipeline for Claude Code. Takes a requirements folder (OpenSpec / Superpowers / plain markdown), drives it through a 100%-coverage planning loop with reuse-first design, spawns parallel agent teams for backend/frontend, enforces review gates via hooks, reconciles parallel work, and verifies with live dev-API + Playwright user-flow tests.

**Status:** v0.1.0.

Full design: [`docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md`](docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md).

## What you get

- **8 skills** — orchestrator (`architect-team`), intake-and-mapping, reuse-first-design, frontend-route-mapping, playwright-user-flows, dev-api-integration-testing, coverage-mapping, team-spawning-and-review-gates.
- **10 agents** — system-architect, frontend, backend, reconciler, integration, scaffold-agent, codebase-map-reviewer, integration-explorer, master-synthesizer, route-mapper.
- **2 commands** — `/architect-team <path>` (main), `/architect-team-setup` (one-time).
- **2 hooks** — `PostToolUse(TaskUpdate)` + `SubagentStop` enforce review gates.
- **Cross-platform setup script** — `scripts/setup/setup.py` installs openspec CLI, pytest/httpx, Playwright + chromium.

## Install

### Prerequisites (must already be on your machine)

- Python ≥ 3.10
- Node ≥ 20.19 (npm)
- Claude Code

### Install the plugin

```bash
# 1. Register this repo as a marketplace
/plugin marketplace add <git-url-of-this-repo>

# 2. Install the plugin
/plugin install architect-team@architect-team-marketplace
```

### Install prerequisite Claude plugins (one-time, you run these)

```bash
/plugin install superpowers@claude-plugins-official
/plugin install cartographer@cartographer-marketplace
/plugin install ralph-loop@claude-plugins-official
```

### Install CLI / Python / browser deps

```bash
/architect-team-setup
```

Idempotent. Runs `scripts/setup/setup.py`. Flags:
- `--check-only` — report status, install nothing.
- `--force-reinstall` — reinstall everything managed.

## Usage

```bash
/architect-team <path-to-requirements-folder>
```

The requirements folder may contain OpenSpec artifacts (`proposal.md`, `specs/`, `design.md`, `tasks.md`), a Superpowers-formatted brief, or plain markdown. The orchestrator detects and normalizes.

The pipeline runs end-to-end:
- **Phase −1**: Intake & Mapping — codebase maps (cartographer) + route maps (frontend) + integration map, each gated by 3-agent ralph-loop review.
- **Phase 0-1**: Detection + planning validation (100% coverage required, reuse-first enforced).
- **Phase 2**: Spawn parallel agent teams with non-overlapping file scopes.
- **Phase 3**: Per-team review gates (enforced by hooks).
- **Phase 4**: Reconciliation when parallel work touches shared boundaries.
- **Phase 5**: Live dev-API + Playwright user-flow integration.
- **Phase 6-8**: Outer loop, master review, final report.

## Document conventions

- `<codebase>/docs/CODEBASE_MAP.md` — cartographer's output (`last_mapped` frontmatter).
- `<codebase>/docs/ROUTE_MAP.md` — route-mapper's output for frontends (`last_routed` frontmatter).
- `<workspace>/docs/INTEGRATION_MAP.md` — master-synthesizer's output (`last_synthesized` frontmatter).
- `<workspace>/.architect-team/intake-state.json` — re-entry short-circuit state.
- `<workspace>/.architect-team/reviews/<task-id>.json` — per-task review-gate evidence.
- `<workspace>/.architect-team/teammates/<name>.json` — teammate manifests.
- `openspec/changes/<change>/coverage-map.json` — coverage map.

## Development

```bash
# Run the plugin's self-tests
python -m pytest -v
```

Tests validate: plugin/marketplace JSON, all 8 skill frontmatters, all 10 agent frontmatters (tool names + model names verified), both commands, hooks.json wiring, hook script logic, setup script logic.

## License

MIT — see [`LICENSE`](LICENSE).
