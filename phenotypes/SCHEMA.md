# Phenotype schema reference

Two JSON files define a phenotype's machine-readable surface. Both are validated by
`scripts/phenotypes/phenotypes.py` (`validate_phenotype`, and the `validate` CLI subcommand).

## `phenotype.json`

```jsonc
{
  "schema_version": 1,                       // REQUIRED int
  "label": "user-management",                // REQUIRED str — MUST equal the containing dir name
  "name": "User Management (backend + frontend + OpenTofu)",  // REQUIRED str
  "version": "1.0.0",                        // REQUIRED str — semver of the phenotype
  "kind": "pair",                            // REQUIRED — "pair" | "singleton"
  "summary": "…",                            // REQUIRED str — one line
  "components": {                            // REQUIRED object — present keys describe shipped parts
    "backend":  { "language": "…", "framework": "…", "datastore": ["…"] },
    "frontend": { "language": "…", "framework": "…", "ui": "…" },
    "deploy":   { "iac": "opentofu", "target": "…" }
  },
  "match": {                                 // REQUIRED — drives matching + reuse-first auto-suggest
    "keywords": ["…"],                       //   REQUIRED non-empty list (single words match whole tokens; multi-word/hyphenated match as substrings)
    "trigger_phrases": ["…"]                 //   OPTIONAL list (substring match, weighted higher)
  },
  "variation_points": [                      // OPTIONAL — the documented knobs
    { "id": "auth_method", "options": ["session-token", "jwt", "oidc"], "default": "session-token" }
  ],
  "when_to_use": ["…"],                       // OPTIONAL
  "when_not": ["…"],                          // OPTIONAL
  "contract_surface": {                      // OPTIONAL — the stable, generalized contract
    "entities": ["…"], "key_endpoints": ["…"]
  },
  "provenance": {                            // REQUIRED object
    "absorbed_from": ["…"],                  //   source repos generalized from
    "absorbed_by": "human",                  //   "human" | "absorb-tool"
    "absorbed_at": "YYYY-MM-DD",
    "generalized": true
  },
  "scaffold": {                              // OPTIONAL (required to emit) — points at the manifest + declares params
    "manifest": "scaffold/scaffold.manifest.json",
    "parameters": [ { "name": "service_name", "required": true, "description": "…" } ]
  },
  "blueprint": "blueprint.md"                // REQUIRED str — the blueprint filename
}
```

**Required keys** (enforced): `schema_version`, `label`, `name`, `version`, `kind`, `summary`,
`components`, `match` (with a non-empty `match.keywords`), `provenance`, `blueprint`. `kind` must be
`pair` or `singleton`. `label` must equal the directory name.

## `scaffold/scaffold.manifest.json`

```jsonc
{
  "schema_version": 1,
  "parameters": [                            // declared params; provided value > default; required-without-either errors
    { "name": "service_name", "required": true },
    { "name": "db_name", "default": "app" }
  ],
  "files": [                                 // each src (relative to scaffold/) is copied to target/dest
    { "src": "backend/app/main.py.tmpl", "dest": "backend/app/main.py" },
    { "src": "deploy/main.tf.tmpl",      "dest": "deploy/{{service_name}}/main.tf" }
  ],
  "post_emit_notes": ["…"]                    // human follow-ups (migrations, secrets, etc.)
}
```

- Placeholders are `{{param_name}}` and are substituted in **both** file contents and `dest` paths.
- An unresolved placeholder (no provided value, no declared default) is an error.
- Template files conventionally carry a `.tmpl` suffix.

## Blueprint (`blueprint.md`) section contract

Verbatim H2 headings (consumers + the absorb tool target them): `## Overview`, `## Architecture`,
`## Components`, `## Data model`, `## Contract / API surface`, `## How the parts interrelate`,
`## Deployment`, `## Variation points`, `## When to use / When NOT`, `## Reuse-Decision hooks`.
