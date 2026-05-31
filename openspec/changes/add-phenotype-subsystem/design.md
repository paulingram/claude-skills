# Design — the phenotype subsystem

## 1. Concept & terminology

A **phenotype** is a labeled, generalized, deployable application-architecture pattern, captured once
and reusable across projects. It is three things together:

| Part | File(s) | What it is |
|---|---|---|
| **Blueprint** | `blueprint.md` | The generalized architecture doc — components, data model, contract surface, how-they-interrelate, how-deployed, variation points, when-to-use / when-NOT. The *understanding*. |
| **Scaffold** | `scaffold/` + `scaffold.manifest.json` | Parameterized starter code + OpenTofu templates the pipeline emits and customizes. The *material*. |
| **Metadata** | `phenotype.json` | The machine-readable manifest — label, domain, stack, provenance, match keywords, variation points, scaffold parameters. The *index entry*. |

A phenotype is **not** a live deployment. Using one yields a blueprint + an emitted, parameter-filled
scaffold that the pipeline then customizes and drives through its normal build/review phases.

## 2. Storage layout

```
phenotypes/
├── README.md                      # human-facing index + "how phenotypes work"
├── SCHEMA.md                      # the phenotype.json + scaffold.manifest.json schema reference
└── <label>/                       # one dir per phenotype, label == kebab-case id (e.g. user-management)
    ├── phenotype.json             # the manifest (see §3)
    ├── blueprint.md               # the generalized architecture doc (see §4)
    └── scaffold/
        ├── scaffold.manifest.json # file list + parameter declarations (see §5)
        ├── backend/…              # generalized backend templates (when kind includes a backend)
        ├── frontend/…             # generalized frontend templates (when kind includes a frontend)
        └── deploy/…               # generalized OpenTofu module templates
```

Discovery is by globbing `phenotypes/*/phenotype.json` — no central registry file to drift. (A
derived index is offered by the helper's `list`/`discover`, and the records are additionally mined
into MemPalace for semantic recall; see §7.)

## 3. `phenotype.json` schema (v1)

```jsonc
{
  "schema_version": 1,
  "label": "user-management",              // kebab-case; MUST equal the containing dir name
  "name": "User Management (backend + frontend + OpenTofu)",
  "version": "1.0.0",                       // semver of the phenotype itself
  "kind": "pair",                           // "pair" | "singleton"
  "summary": "Production user-management system: async API backend + SPA frontend, OpenTofu-deployed.",
  "components": {                            // present keys describe the parts this phenotype ships
    "backend":  { "language": "python", "framework": "fastapi", "datastore": ["postgres", "redis"] },
    "frontend": { "language": "typescript", "framework": "react+vite", "ui": "shadcn+tailwind" },
    "deploy":   { "iac": "opentofu", "target": "cloud-run|ecs|k8s (parameterized)" }
  },
  "match": {                                // drives reuse-first auto-suggest + the helper's matcher
    "keywords": ["user management", "auth", "authentication", "login", "signup", "rbac",
                 "accounts", "identity", "sso", "sessions", "permissions", "organizations"],
    "trigger_phrases": ["i want a user management system", "build a user management backend",
                        "add authentication", "we need login and accounts"]
  },
  "variation_points": [                     // the knobs a consumer chooses; each has a default
    { "id": "auth_method", "options": ["session-token", "jwt", "oidc"], "default": "session-token" },
    { "id": "multi_tenancy", "options": ["orgs", "single-tenant"], "default": "orgs" },
    { "id": "deploy_target", "options": ["cloud-run", "ecs", "k8s"], "default": "cloud-run" }
  ],
  "when_to_use": ["A product needs accounts, login, roles/permissions, and org/tenant structure."],
  "when_not":    ["A single hardcoded admin suffices, or auth is delegated entirely to a 3rd party."],
  "contract_surface": {                     // the stable shape, generalized
    "entities": ["User", "Organization", "Role", "Permission", "Session", "Invitation", "AuditLog"],
    "key_endpoints": ["POST /auth/login", "GET /auth/session", "POST /users", "GET /users",
                      "POST /organizations", "POST /roles", "POST /invitations"]
  },
  "provenance": {
    "absorbed_from": ["globalUserManagement-Backend", "globalUserManagementFrontEnd", "confgigs"],
    "absorbed_by": "human",                 // "human" | "absorb-tool"
    "absorbed_at": "2026-05-30",
    "generalized": true
  },
  "scaffold": {
    "manifest": "scaffold/scaffold.manifest.json",
    "parameters": [                          // surfaced to the consumer; substituted on emit
      { "name": "service_name", "required": true,  "description": "kebab-case service id" },
      { "name": "db_name",      "required": false, "default": "app", "description": "Postgres DB name" }
    ]
  },
  "blueprint": "blueprint.md"
}
```

**Required keys:** `schema_version`, `label`, `name`, `version`, `kind`, `summary`, `components`,
`match.keywords`, `provenance`, `blueprint`. `validate_phenotype()` (§6) enforces these + types +
`label == dirname`.

## 4. Blueprint schema (`blueprint.md` sections)

Every blueprint uses these verbatim H2 headings (the consumer + the absorb tool both target them):

1. `## Overview` — what this architecture is, in one paragraph, plus the canonical use case.
2. `## Architecture` — the layering / module model; a diagram.
3. `## Components` — each part (backend / frontend / deploy) and its stack + responsibilities.
4. `## Data model` — core entities + relationships (generalized; no app-specific tables).
5. `## Contract / API surface` — the stable endpoint + type contract between parts.
6. `## How the parts interrelate` — **the user's explicit ask** — the runtime data/auth flow across
   backend ↔ frontend ↔ datastore (e.g. the login→token→attach→refresh→logout loop).
7. `## Deployment` — **the user's explicit ask** — the OpenTofu module shape, the cloud topology, the
   migrate-then-health-gated deploy flow; what's parameterized.
8. `## Variation points` — the documented knobs (mirrors `phenotype.json.variation_points`) + the
   trade-offs of each.
9. `## When to use / When NOT` — the reuse-first guardrails.
10. `## Reuse-Decision hooks` — how this phenotype plugs into `reuse-first-design`'s ladder + what a
    consumer must still customize (so it's never copy-paste-and-ship).

## 5. Scaffold model

`scaffold/scaffold.manifest.json`:

```jsonc
{
  "schema_version": 1,
  "parameters": [ { "name": "service_name", "required": true }, { "name": "db_name", "default": "app" } ],
  "files": [
    { "src": "backend/app/main.py.tmpl", "dest": "backend/app/main.py" },
    { "src": "deploy/service.tf.tmpl",   "dest": "deploy/{{service_name}}.tf" }
  ],
  "post_emit_notes": ["Run migrations: `alembic upgrade head`", "Fill secrets in the OpenTofu tfvars."]
}
```

- Template files carry the `.tmpl` suffix; placeholders are `{{param_name}}` (in both file *contents*
  and the `dest` *path*).
- `emit_scaffold(label, target_dir, params, dry_run=...)` copies each `src` → `target_dir/dest`,
  substituting placeholders from `params` (falling back to declared `default`s). A required parameter
  with no value is an error. `dry_run=True` returns the would-be-written paths without writing.
- The scaffold is a **generalized starting point, not a finished app** — `## Reuse-Decision hooks` and
  `post_emit_notes` enumerate what the consuming run must still wire/customize. Generated code carries
  no real secrets, account ids, or domains (those are parameters/placeholders).

## 6. The helper — `scripts/phenotypes/phenotypes.py` (stdlib only)

Mirrors the plugin's existing helper convention (`teams_mode.py`, `worktree_lifecycle.py`): a flat,
stdlib-only module imported via `sys.path.insert`, plus a CLI. Public surface:

| Function | Returns | Purpose |
|---|---|---|
| `phenotypes_dir()` | `Path` | Resolve the `phenotypes/` dir (repo-root relative; env override `PHENOTYPES_DIR`). |
| `discover_phenotypes(dir=None)` | `list[dict]` | Glob `*/phenotype.json`, load + validate, return manifests (sorted by label). |
| `validate_phenotype(obj, dirname=None)` | `list[str]` | Schema errors (empty ⇒ valid); checks required keys, types, `label==dirname`. |
| `load_phenotype(label, dir=None)` | `dict` | One manifest by label (raises if absent). |
| `match_phenotype(request_text, dir=None)` | `list[dict]` | Ranked `[{label, score, matched_keywords, matched_phrases}]` — deterministic keyword + trigger-phrase scoring (case-insensitive, whole-word + phrase-substring; phrase hits weighted higher). |
| `emit_scaffold(label, target_dir, params, dir=None, dry_run=False)` | `list[str]` | Emit (or, dry-run, list) the parameter-substituted scaffold files. |

**CLI:** `list` · `show <label>` · `match "<request text>"` · `validate [<label>]` ·
`emit <label> <target> [--param k=v]… [--dry-run]`. Invoked via the polyglot `python3 … || python …`
pattern. Exit 0 / 2 (2 on validation failure or unknown label), per the plugin's hook-exit convention.

The matcher is intentionally **deterministic** (not ML): it is testable, fast, offline, and
demonstrable. MemPalace (§7) layers *semantic* recall on top for fuzzier real-run matching, but the
deterministic matcher is the floor and the demo.

## 7. Discovery, matching & MemPalace recall

- **Deterministic discovery/matching** — the helper, above. The floor; used in tests + the demo.
- **Semantic recall** — `skills/mempalace-integration` already auto-mines artifacts and "searches
  before output." Phenotype records (the `phenotype.json` summary/keywords + the blueprint's
  `## Overview`) are mined into the per-workspace palace, so a fuzzily-worded request
  ("we need accounts and sign-in") surfaces the `user-management` phenotype via semantic search even
  when literal keywords don't overlap. The skill documents the mine + the search-before-build step.

## 8. Trigger model — explicit + auto-suggest, never silent

| Path | Mechanism |
|---|---|
| **Explicit** | `--phenotype <label>` flag on `/architect-team` (parsed in `commands/architect-team.md` alongside the existing `--no-*` flags), and the natural-language equivalents *"use the `<label>` phenotype"* / *"use phenotypes"*. Binds `$PHENOTYPE = <label>`; the pipeline loads it and uses its scaffold as the starting point. |
| **Auto-suggest** | During `reuse-first-design`, before deciding to build-new, the pipeline runs `match_phenotype(<request>)`. A strong match (score ≥ threshold) is **surfaced to the user as a proposal** (an `AskUserQuestion`-style "I can base this on the `user-management` phenotype — use it?"). It is **never applied silently** — this is a domain-gate, consistent with the plugin's `## Scope discipline`. |

A phenotype is a *form of reuse* (a proven, generalized blueprint) — it sits at the top of the
reuse-first ladder, above extend/compose/reuse-against-the-target-workspace (see §10).

## 9. Consumption flow (how a run uses a phenotype)

```
match (explicit --phenotype OR reuse-first auto-suggest)
  → load_phenotype + read blueprint.md
  → confirm with user (domain gate; choose variation_points + scaffold params)
  → emit_scaffold(label, <change workdir>, params)
  → CUSTOMIZE the emitted scaffold to the specific request (the architect + implementers)
  → drive through the normal pipeline phases (coverage map, review gates, tests, integration)
```

The phenotype gives the run a *correct, proven starting shape*; the normal pipeline rigor still
applies on top. The scaffold is never shipped unexamined — `## Reuse-Decision hooks` +
`post_emit_notes` list the mandatory customizations.

## 10. Reuse-first precedence

`reuse-first-design`'s ladder is **extend > compose > reuse > build-new**, reasoning over the TARGET
workspace. Phenotypes extend it with a cross-project rung evaluated **before build-new**:

> When no extend/compose/reuse option exists in the target workspace, check the phenotype library. A
> matching phenotype IS reuse (of a proven blueprint) and is preferred over building new — but it is
> *proposed*, not imposed, and the consumer still customizes it. With no match, build-new proceeds as
> today.

This keeps phenotypes from short-circuiting genuine in-workspace reuse, and keeps "build from a
phenotype" honest (it's reuse + customization, logged in the Reuse-Decision Log).

## 11. The `absorb` capability (designed here; built post-checkpoint)

Goal: point at any arbitrary codebase and ingest it as a new labeled phenotype.

- **Command:** `/architect-team:absorb-phenotype <path> --label <name> [--kind pair|singleton]`.
- **Skill:** `skills/phenotype-absorption/` — the playbook. It mirrors exactly what this run did by
  hand: dispatch N analysis agents over the target codebase (lean on its existing docs/maps first),
  synthesize a generalized `blueprint.md` (the §4 schema), derive a `scaffold/` by templatizing the
  source (strip/parameterize per the §12 rubric), write a `phenotype.json` (§3), validate via the
  helper, and mine it into MemPalace.
- **Reuse:** the absorb skill is the *generalized, repeatable* form of this vertical slice — the
  user-management phenotype produced here is its first hand-run worked example and golden reference.
- **Guardrails:** absorb is analysis + authoring only (never modifies the source repo); the generated
  scaffold is reviewed by the same gates; `absorbed_by: "absorb-tool"` records provenance.

## 12. Generalization rubric (keep vs. strip/parameterize)

Applied when authoring a blueprint + scaffold from a real codebase:

| KEEP (the reusable pattern) | STRIP or PARAMETERIZE (the instance) |
|---|---|
| Architecture, layering, module boundaries | Company / product / repo names |
| Auth *model* (token scheme, RBAC shape, OIDC adapter pattern) | Identity-provider tenant ids, client ids, secret names |
| Data *model* (entities + relationships + patterns like closure-table hierarchy) | Seeded business data, specific role/permission catalogs |
| Integration *contract* (endpoint shapes, error envelope, token flow) | Concrete base URLs, CORS origins, domains |
| Deployment *shape* (OpenTofu module structure, migrate-then-health-gate flow) | Cloud account ids, ARNs/project ids, region, DNS, real secrets |
| Tech-stack choices + cross-cutting patterns (error hierarchy, event bus, test approach) | Hardcoded sample values standing in for dynamic data |

Every stripped instance value becomes either a `variation_point` (a real choice) or a scaffold
`parameter` (a fill-in). Secrets are NEVER embedded — only referenced by parameter/placeholder.

## 13. Non-goals (this change)

- No auto-deploy (no `tofu apply` against a live cloud) — blueprint + scaffold only.
- No confgigs / AI-management seed phenotypes this run (designed; deferred to post-checkpoint).
- No live `absorb` command this run (designed in §11; built post-checkpoint).
- No change to existing pipeline behavior when no phenotype is requested or matched.
