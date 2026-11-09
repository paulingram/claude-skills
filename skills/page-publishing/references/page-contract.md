# The page contract

The plugin's own definition of a publishable page. A page that meets it is
portable to every host the `page-publishing` skill knows: the Claude Artifact
tool, a token-checking port on this machine, a signed GCS object, a Cloud Run
service, a nominated web root. `scripts/publish/publish.py check <file>` is the
machine half of this contract; the rest is the author's judgement.

## 1. One self-contained HTML file

- A single `.html` file. Styles inline in `<style>`, scripts inline in
  `<script>`, images as inline SVG or `data:` URIs. No sibling files, no build
  step, nothing the host must serve beside it.
- Under **16 MB** including any `data:` URIs (the engine refuses a larger file).
- Starts with `<!doctype html>`, declares `<meta charset="utf-8">` and the
  viewport meta.

## 2. Color tokens for light AND dark

Define every color as a token on `:root`, redefine the tokens for dark mode
under `@media (prefers-color-scheme: dark)` guarded by
`:root:not([data-theme="light"])`, and again under `:root[data-theme="dark"]`
so a host that sets `data-theme` wins over the OS preference. Give `body` an
explicit `background`. The fixture `tests/fixtures/publish/page.html` is the
minimal worked example. A page with no `prefers-color-scheme` query earns a
warning from the engine, not a refusal.

## 3. Diagrams as inline SVG

Draw diagrams and charts as inline `<svg>` with `viewBox`, `role="img"` and an
`aria-label`; color strokes and fills through the same tokens (`fill:
var(--accent)`) so they follow the theme. No raster screenshots of diagrams,
no diagram-rendering library fetched at view time.

## 4. Responsive at phone width

Readable at **400px** with **16px** side gutters and no horizontal page
scroll: `max-width` containers, `overflow-wrap: anywhere` on long tokens,
tables that wrap or scroll inside their own box, SVGs at `width: 100%`.

## 5. Libraries only from pinned CDN URLs

When a library is genuinely needed, load it from **cdnjs.cloudflare.com**,
**cdn.jsdelivr.net/npm/** or **unpkg.com** only, naming an **exact version**
(`react@18.3.1`, `/ajax/libs/d3/7.9.0/`), never a floating `@18` or `@latest`.
Stylesheets may additionally come from Google Fonts. Any other external
script or stylesheet host is an engine **error**: the page must not depend on
a host the viewer's network might not reach, and an unpinned library changes
under the page.

## 6. No data leaves the page

The page is a document, not a client. No `fetch`, `XMLHttpRequest`,
`sendBeacon`, `WebSocket` or form `action` that sends the viewer's data
anywhere; no analytics snippet. Everything the page shows is in the file. The
engine warns on any network call it can see; the author confirms none sends
data out.

## 7. No secrets rendered

Nothing that would be a credential appears in the page: no API keys, tokens,
private keys, connection strings, internal hostnames the viewer should not
learn. A token-shaped string (`sk-ant-...`, `AKIA...`, a `PRIVATE KEY` block,
`ghp_...`, `xox?-...`) is an engine **error that `--force` cannot override**.
Redact values to `set` / `unset` the way the homepage renders settings.

## 8. Honest about its own data

Every number the page states names its source (the measurement artifact, the
registry, the test run) and its time. A page that cannot name the source for a
figure leaves the figure out. This is the `docs/ETHOS.md` evidence posture
applied to presentation: a green tile proves what it measured.

## Checking a page

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/publish/publish.py" check <file.html>
```

Exit 0 and `page contract: ok` is the bar. Errors refuse a publish; warnings
are printed with it so the author can decide.
