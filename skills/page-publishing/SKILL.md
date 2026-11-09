---
name: page-publishing
description: Use whenever a run or a user wants a PAGE rather than terminal text -- a report, dashboard, explainer, the project homepage, a visual someone else will read -- and to decide where that page lives. Carries the plugin's own page contract (one self-contained HTML file, light + dark color tokens, inline SVG diagrams, responsive at 400px, pinned-CDN libraries only, no data leaves the page, no secrets, under 16 MB) so the page is portable to any host. Two publish modes read from the human-owned .architect-team-publish.json -- claude (default, hand the file to the Claude Artifact tool) and private-url (scripts/publish/publish.py mints a token and places the page through the local-port / gcp-signed-url / gcp-cloud-run / nominated-host adapter under <base_url>/<slug>/p/<token>/<page>.html). Covers the one setup question, token TTL, revoke and list, and the honest boundary printed with every private link.
user-invocable: false
---

# Page Publishing — a page someone else can open

CT6 produces evidence as JSON verdicts and markdown reports. Some of that is
better read as a page: a run summary with its phase durations drawn, a data
dictionary someone browses, a delivery manifest a stakeholder opens on a phone,
the per-project homepage. This skill says WHEN to make a page, WHAT a page must
be so it survives any host, and WHERE it goes — the Claude Artifact tool by
default, or a private URL the human chose at setup.

## When to make a page

Make a page when the reader would USE it rather than only read it, or when the
content is visual: a diagram that explains a mechanism, a dashboard of recorded
numbers, a comparison someone scrolls on a phone, a document meant to be passed
along. Do not make a page for a one-line answer, a code diff, or advice the
user will act on right away in their editor. A page is finished work for a
reader; the report of a run is still the terminal summary and the delivery
manifest (`skills/delivery-manifest/SKILL.md`), and a page carries that
content, never replaces it.

Inside a Claude Code session the native Artifact guidance is also available and
is the better DESIGN reference; defer to it for design, and hold the page to the
contract below so it stays portable off Claude.

## The page contract (read `skills/page-publishing/references/page-contract.md`)

One self-contained HTML file; color tokens for light and dark via
`prefers-color-scheme` AND `data-theme`; inline SVG for diagrams; responsive at
400px with 16px gutters; libraries only from pinned cdnjs / jsdelivr / unpkg
URLs; no data leaves the page; no secrets rendered; under 16 MB. The engine
lints it:

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/publish/publish.py" check <file.html>
```

Errors refuse a publish (`--force` overrides contract errors, never a
secret-shaped string); warnings print with the result. The worked example is
`tests/fixtures/publish/page.html`.

## Two modes, one human-owned setting

The mode comes from `hooks/publish_config.py` reading two human-owned files —
`~/.architect-team/publish.json` (machine-wide defaults: `base_url`, adapter,
GCP project) under `<project>/.architect-team-publish.json` (per checkout,
gitignored; template `.architect-team-publish.example.json`). A `null` means
"inherit"; an absent, malformed or unknown value resolves to `claude`. The
files are IMMUTABLE TO AGENTS: read them, never create, edit or delete them —
the setup question writes the project file once with the human's answer, and
the PreToolUse override guard blocks everything else.

### `claude` (default)

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/publish/publish.py" publish <file.html> [--name N]
```

The engine copies the page to `<workspace>/.architect-team/publish/outbox/<name>.html`
and prints the instruction: hand that file to the Claude Artifact tool. No URL
is minted, nothing listens, nothing is uploaded. The artifact's own private link
is the share link, with every Claude-native feature intact.

### `private-url`

The same command. The engine mints a token (`secrets.token_urlsafe(24)`), hands
the page to the configured adapter, records the link with its expiry in
`~/.architect-team/publish/registry.json`, and prints the URL WITH its honest
boundary. Layout on every adapter:

```
<base_url>/<project_slug>/p/<token>/<page-name>.html
<base_url>/<project_slug>/p/<token>/            <- the homepage, when --name index
```

`project_slug` defaults to the repo directory name, so many projects share one
address with a shelf each. The homepage lands at its token directory, never at
a token-free `<base_url>/<slug>/`: a path without a live token is 404 on every
adapter that checks tokens, by design.

| Adapter | What it does | Needs | HTTPS |
|---|---|---|---|
| `local-port` | a stdlib `ThreadingHTTPServer` on this machine, detached from the session, serving ONLY live-token paths (everything else 404, never a listing); access log with the token redacted; hourly expired-page prune on `services/common/bg_runtime.py` | a reachable address (`bind.external_ip` behind NAT) | only with `bind.tls_cert` + `bind.tls_key`; plain HTTP prints a warning |
| `gcp-signed-url` | `gcloud storage cp` into `gcp.bucket`, then `gcloud storage sign-url --duration=<ttl>h` | gcloud logged in, a bucket you own | yes |
| `gcp-cloud-run` | GENERATES `Dockerfile` + `deploy.sh` + a copy of the server under `.architect-team/publish/cloud-run/`; deploys NOTHING — a human runs `deploy.sh`; the URL is a PATTERN until `base_url` is recorded | gcloud, `gcp.project` | yes, once deployed |
| `nominated-host` | `ssh mkdir -p` + `scp` into `nominated_host.web_root` on `nominated_host.ssh`; linked under `nominated_host.public_base_url` | key-based ssh to a host you already serve | whatever that host serves |

A missing `gcloud` / `ssh` is a structured error with a remediation line, never
a traceback and never a reason to fall back to a different host on your own:
the human chose the adapter.

### Server helpers (`local-port`)

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/publish/publish.py" serve-status
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/publish/publish.py" serve-stop
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/publish/adapters/local_port.py" descriptor --platform linux
```

`publish` starts the server when nothing is listening (pidfile + state under
`~/.architect-team/publish/`); `descriptor` prints a systemd / launchd /
schtasks boot descriptor and installs nothing — registering it is the
operator's step.

## The setup question (asked ONCE, by `architect-team-setup`)

`scripts/publish/setup_question.py` detects the ecosystem — is `gcloud` on PATH
AND logged in, does the box have a globally routable address (from local
interface info only, no network call), which `Host` aliases `~/.ssh/config`
names — and `question(ecosystem)` yields the exact `AskUserQuestion` payload:

- **Claude artifacts only (default)**
- **GCP signed URL (recommended when gcloud is present)**
- **A port on this machine**
- **A host I nominate**

The question says the security notes out loud: the token sits in the URL and
leaks through history, logs and referrers; a port on a dev box is an attack
surface; a cloud service costs money and needs IAM; plain HTTP leaks the token.
Nothing is opened, uploaded or deployed until the answer is recorded by
`write_config(answers, project_root, home)`. gcloud and ssh are reported
present or absent with remediation and never gate setup — the conditional
posture of `scripts/setup/setup.py`'s `CONDITIONAL_PLUGINS`. An existing
project config is the recorded answer: do not ask again, do not overwrite.

## Tokens: TTL, revoke, list

- `token_ttl_hours` (default 72) sets `expires_at`; the local server and the
  registry refuse an expired token (404), signed URLs expire on their own, and
  a nominated host expires only when the file is removed — say so.
- `publish.py revoke <token>` marks the entry `revoked_at` and asks the adapter
  to remove the file (local store, `gcloud storage rm`, remote `rm -f`). A
  revoked token is 404 at once on the local server; the Cloud Run image keeps
  its snapshot until `deploy.sh` runs again.
- `publish.py list [--json]` prints every recorded token with
  `live` / `expired` / `revoked`.

## The honest boundary — printed with every private link

- A private URL is not a Claude artifact: no comments routed to Claude, no
  shared database, no organization share list, no host theme detection.
- The token IS the secret: anyone holding the link opens the page until it
  expires or is revoked.
- Plain HTTP (no certificate) means the token travels in clear text.
- `gcp-cloud-run` deploys nothing: the URL is a pattern until a human runs the
  generated `deploy.sh` and records `base_url`.

Never state that a page is "shared" or "live" without the URL the engine
printed and its expiry; never claim a Cloud Run page is reachable before the
deploy ran. This is `docs/ETHOS.md` applied to a link: the claim is only what
the engine returned.

## Hard rules

- Read the mode from the config; never switch modes, adapters, ports or hosts
  on your own initiative, and never create or edit `.architect-team-publish.json`.
- Every page passes `publish.py check` before it is published; a secret-shaped
  string is never published.
- Every private link is printed with its token, its expiry and the honest
  boundary; every `--revoke` is confirmed from the registry, not assumed.
- `gcp-cloud-run` generates; a human deploys.

## Reference index

| Section | Reference file | Loaded |
| --- | --- | --- |
| `The page contract` | `skills/page-publishing/references/page-contract.md` | on demand — before authoring or linting a page |
