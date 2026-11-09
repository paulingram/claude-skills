---
description: Publish a self-contained HTML page where the project's human-owned publish config says pages live -- claude mode (default) hands the file to the Claude Artifact tool, private-url mode mints a tokened link through the local-port / gcp-signed-url / gcp-cloud-run / nominated-host adapter and records it in the publish registry. Also revokes a token, lists recorded tokens, and reports the local server's status. Drives the page-publishing skill.
argument-hint: "<file.html> [--name <page-name>] [--slug <project-slug>] [--force] | --revoke <token> | --list | --status | --check <file.html>"
---

# /architect-team:publish

Publish ONE page, or manage the links already published. The destination is the
human's recorded choice (`.architect-team-publish.json`, written once by
`architect-team-setup`); this command never changes it.

**Raw arguments:** $ARGUMENTS

## Argument parsing

Strip the recognised flags from `$ARGUMENTS`; what remains is the page path.

- `--name <page-name>` → the served name (`index` makes the page the project's
  homepage, landing at `<base_url>/<slug>/p/<token>/`).
- `--slug <project-slug>` → override the project slug (default: the repo
  directory name).
- `--force` → publish despite page-contract **errors** (never despite a
  secret-shaped string -- the engine refuses that regardless).
- `--revoke <token>` → revoke that token; no page path expected.
- `--list` → list every recorded token with `live` / `expired` / `revoked`.
- `--status` → the local-port server's status (pid, host, port, scheme, logs).
- `--check <file.html>` → lint the page against the page contract only.

Natural-language equivalents: *"revoke this link"* → `--revoke`; *"what have I
published"* / *"list the links"* → `--list`; *"is the page server running"* →
`--status`; *"make this the homepage"* → `--name index`.

## Invoke the skill

Invoke the **`page-publishing` skill** (Skill tool: `page-publishing`) and
follow it. The engine is `scripts/publish/publish.py`; the interpreter is
selected ONCE via `$(command -v python3 || command -v python)` (the v2.16.0
detect-once form).

Publish:

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/publish/publish.py" publish "<file.html>" [--name <page-name>] [--slug <project-slug>] [--force]
```

Revoke / list / status / check:

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/publish/publish.py" revoke "<token>"
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/publish/publish.py" list
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/publish/publish.py" serve-status
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/publish/publish.py" check "<file.html>"
```

## What to surface

- **claude mode** → the outbox path the engine wrote and its instruction: hand
  that file to the Claude Artifact tool. Say plainly that no URL was minted.
- **private-url mode** → the URL, the token, the expiry, the registry path, every
  `WARNING:` line and the **Honest boundary** block the engine printed --
  verbatim, all of it. For `gcp-cloud-run` also the generated `deploy.sh` path
  and that NOTHING was deployed.
- **REFUSED** → the error, the remediation and the error findings verbatim. A
  missing `gcloud` / `ssh` is a remediation line, not a reason to switch
  adapters on your own; a secret-shaped string is never published.
- Exit codes: `0` ok, `1` refused, `2` usage error, `3` internal error -- a `3`
  is a bug to report, never a refusal to paper over.

## No publish config yet

If the engine resolves `mode: claude` because no config exists, publish in
claude mode and say in one line that `/architect-team:architect-team-setup`
asks the one setup question ("where should shareable pages live?") and records
the answer. Do not ask it here, do not write the config here: it is
human-owned and written once by setup.

## Cross-references

- `skills/page-publishing/SKILL.md` -- the contract this command drives (the
  page contract, the two modes, the adapters, the honest boundary).
- `scripts/publish/publish.py` -- the engine (publish / revoke / list /
  serve-status / check).
- `hooks/publish_config.py` -- the read-only config reader; the committed
  template is `.architect-team-publish.example.json`.
