# Code Wiki — blueprint

A generalized, self-hosted **documentation wiki** that renders pre-generated codebase maps as a
browsable, visually-rich site: a left navigation tree, a constrained markdown content pane, and
client-rendered Mermaid diagrams, with dark/light theming. Absorbed from
[`deepwiki-open`](https://github.com/AsyncFuncAI/deepwiki-open.git) (MIT) — its **presentation
pattern** is the absorption product; its LLM machinery (9 providers, RAG, WebSocket chat, Ask/Deep
Research, slides/workshop generation) is the strip boundary. The content source is swapped from
"generate with an LLM at view time" to "ingest already-written `*_MAP.md` files".

## Overview

The phenotype is a single Next.js (App Router, `output: 'standalone'`) application — **no backend
process, no database, no LLM**. It reads a `codebases.json` registry of `{name, maps_dir}` entries,
transforms each registered codebase's `docs/*_MAP.md` files into the wiki content shape, and serves
them as a wiki: codebase selector -> per-codebase page tree -> markdown content with embedded Mermaid.

What deepwiki-open used LLMs for (the **stripped-LLM delta**):

- **Wiki generation** — deepwiki composed structure/page prompts in the browser, streamed completions
  over `ws://.../ws/chat` to a FastAPI backend doing repo-RAG (clone -> embed -> FAISS retrieve ->
  provider dispatch), parsed the result, and POSTed the finished wiki JSON to a cache endpoint. **Dies.**
- **Ask chat + Deep Research** (`Ask.tsx` -> `/ws/chat`), **slides + workshop** generation, the
  **model/provider picker** UI (`/models/config`), the **9 provider clients** (OpenAI, OpenRouter,
  LiteLLM, Bedrock, Azure, DashScope, Google, Ollama + embedders), the **embedding/RAG pipeline**
  (`rag.py`, `data_pipeline.py`, faiss/adalflow/tiktoken), and **every API key** (`GOOGLE_API_KEY`,
  `OPENAI_API_KEY`, `AWS_*`, `AZURE_OPENAI_*`, `DASHSCOPE_*`, `OLLAMA_HOST`, ...). **All die.**

**What replaces it:** the CT6 pipeline (or any author) writes `*_MAP.md` files; a thin filesystem
ingestion layer (`lib/maps-loader`) turns them into the wiki content shape at request time. The map
markdown already carries Mermaid in fenced ` ```mermaid ` blocks, so diagrams ride inside the content
exactly as deepwiki's LLM-produced pages did — the renderer is unchanged.

**What survives the strip (the body of this phenotype):** wiki **viewing** — the recursive nav tree,
the markdown -> styled-HTML pipeline with code-block copy buttons, client-side Mermaid render-to-SVG,
dark/light theming, the multi-codebase selector with search, and the two-pane elevated-card shell.

## Architecture

```
codebases.json  ->  lib/maps-loader  ->  WikiStructure + pages  ->  Next.js App Router pages
[{name,maps_dir}]   (server-side fs)     (in-memory content shape)   (RSC reads; client leaves)
                                                                         |
   docs/*_MAP.md  --(read verbatim)----------------------------------->  Markdown -> Mermaid / code
```

- **Framework**: Next.js App Router, React, TypeScript, `output: 'standalone'` (single-binary Docker).
- **Rendering split**: the page shells + ingestion are **React Server Components** that read the
  filesystem directly (no `/api/wiki_cache` round-trip — the deepwiki cache endpoint collapses into a
  server-side `maps-loader` call). `Markdown`, `Mermaid`, and `WikiTreeView` are **client leaves**
  (`'use client'`) because Mermaid renders to SVG in the browser and the tree holds expand/collapse
  + selection state.
- **Styling backbone**: a **10-variable CSS custom-property palette** defined twice (`:root` light +
  `[data-theme='dark']`) — `--background`, `--foreground`, `--accent-primary`, `--accent-secondary`,
  `--border-color`, `--card-bg`, `--highlight`, `--muted`, `--link-color`, `--shadow-color`. Every
  component consumes `var(--*)`; theming is pure CSS. This is generalized from deepwiki's `globals.css`
  (the shipped "washi/Fuji-purple" hexes become the default preset; branding stripped). The scaffold
  uses **plain CSS, not Tailwind** — dropping the postcss/Tailwind-v4 toolchain keeps the dependency
  set minimal and the starter buildable out of the box.
- **No second process**: deepwiki's whole `api/` Python tree (FastAPI, providers, RAG) is removed; its
  two surviving non-LLM reads (wiki-cache GET, projects list GET) become server-component filesystem
  reads. The `SERVER_BASE_URL` indirection + `next.config.ts` rewrites + `src/app/api/*` proxies all
  collapse (which also fixes deepwiki's non-`NEXT_PUBLIC_` env bug by removal).

## Components

| Component | Absorbed from | Role | Notes |
|---|---|---|---|
| **App shell** (`layout`, `globals.css`) | `src/app/layout.tsx`, `src/app/globals.css` | theme provider (`data-theme` attribute) + the 10-var palette + base type | branding removed; palette parameterized |
| **Codebase selector** (index page) | `src/components/ProcessedProjects.tsx` pattern | card grid + client-side search filter over the registry | "open a wiki", not "generate" |
| **Wiki viewer** (`/wiki/[codebase]/[pageId]`) | `src/app/[owner]/[repo]/page.tsx` JSX 1941-2205 | two-pane elevated card: sidebar (identity + tree) / constrained content pane | **URL-backed** navigation (deepwiki's known gap — it kept the current page in `useState` only) |
| **`WikiTreeView`** | `src/components/WikiTreeView.tsx` | recursive collapsible nav: importance dots + selected state + flat-list fallback | generic already; palette + dot hexes parameterized |
| **`Markdown`** | `src/components/Markdown.tsx` | `react-markdown` + `remark-gfm`, fenced-code highlight + copy button, **mermaid fence dispatch** | ReAct chat `h2` special-case (LLM-only) stripped; `remark-math`/katex dropped to stay lean |
| **`Mermaid`** | `src/components/Mermaid.tsx` | client `mermaid.render` -> SVG string, palette-matched `themeCSS` (light + dark inside the SVG), error/loading states, optional pan-zoom + fullscreen | Japanese strings translated to English; dark keyed to the resolved theme (deepwiki keyed it to `prefers-color-scheme`, a wart) |
| **`lib/maps-loader`** | replaces `api/api.py:403-457, 577-634` (cache + projects reads) | reads `codebases.json`, enumerates each codebase's `docs/*_MAP.md`, builds `WikiStructure` | the new content source; pure `fs` |
| **Health route** (`/health`) | `api.py:540` `/health` | Docker healthcheck target | a tiny Next route handler |

## Data model

The content contract is deepwiki's `WikiCacheData` shape (`api/api.py:40-99` == `src/types/wiki/*`),
kept verbatim so the viewer is unchanged — only the **source** changes (filesystem maps, not an LLM):

```ts
interface WikiPage {
  id: string;
  title: string;
  content: string;            // ONE markdown string per page, with ```mermaid blocks inline
  filePaths: string[];        // source files the page documents (here: the map's own path)
  importance: 'high' | 'medium' | 'low';
  relatedPages: string[];     // page ids -> chip links
}
interface WikiSection { id: string; title: string; pages: string[]; subsections?: string[]; }
interface WikiStructure {
  id: string; title: string; description: string;
  pages: WikiPage[]; sections: WikiSection[]; rootSections: string[];
}
```

**Maps-ingestion mapping** (`lib/maps-loader`): for each `{name, maps_dir}` in `codebases.json`,
enumerate `<maps_dir>/*_MAP.md` (any `*_MAP.md` — the five CT6 map kinds plus any future ones). Build:

- one **section** per codebase (`section.id = <codebase>`, `section.title = <name>`); the codebase is
  a `rootSection`;
- one **page** per map file (`page.id = <codebase>__<MAP_BASENAME>`, `page.title` = the map kind
  humanized, `content` = the map markdown **verbatim**, `filePaths = [<relative map path>]`);
- **importance** by map kind: `CODEBASE_MAP` / `ARCHITECTURE` -> `high`; `INTEGRATION_MAP` /
  `API` / `DATA` -> `medium`; everything else -> `low`. (Drives the nav importance dot.)

Diagrams are **not** a separate channel: they are fenced ` ```mermaid ` blocks inside `content` that
the `Markdown` component intercepts and hands to `Mermaid`.

## Contract / API surface

This phenotype exposes **no HTTP API for callers** (it is a viewer). Its stable contracts are:

- **`codebases.json` registry** (the post-emit fill): a JSON array of `{ "name": string, "maps_dir":
  string }`. `maps_dir` points at a directory containing `docs/*_MAP.md` (or any dir with `*_MAP.md`).
  "Any number of codebases" = the array is a list; the UI gets a selector.
- **`WIKI_CONTENT_DIR`** (env): the directory holding `codebases.json` (default `./content`). Mounted
  as a Docker volume for local hosting; the generalization of deepwiki's `~/.adalflow/wikicache/`.
- **The wiki content shape** (`WikiStructure` + `WikiPage`, above): the in-memory payload
  `lib/maps-loader` produces and the viewer consumes. An alternate content producer (not just the maps
  loader) only has to emit this shape.
- **Routes**: `/` (selector), `/wiki/[codebase]` (first page), `/wiki/[codebase]/[pageId]` (deep
  link), `/health` (200 JSON for the compose healthcheck).

## How the parts interrelate

1. A request to `/` runs the index server component, which calls `lib/maps-loader` to list the
   registered codebases (reads `codebases.json` under `WIKI_CONTENT_DIR`) and renders the card grid +
   client-side search filter.
2. A request to `/wiki/[codebase]/[pageId]` runs the viewer server component: `maps-loader` builds the
   `WikiStructure` for `[codebase]` (enumerating its `*_MAP.md`), selects `[pageId]` (or the first
   page), and passes `{ structure, page }` to the client leaves.
3. `WikiTreeView` (client) renders the recursive nav from `structure.sections`/`rootSections` (flat
   `pages[]` fallback when a codebase has no hierarchy); selecting a page navigates the **URL**
   (`router.push('/wiki/<codebase>/<pageId>')`) — deep-linkable, back-button-friendly.
4. The content pane renders `<Markdown content={page.content} />`. `Markdown` walks the markdown;
   for each fenced block it dispatches: ` ```mermaid ` -> `<Mermaid chart=... />`; other languages ->
   highlighted code with a copy button; inline -> a mono chip.
5. `Mermaid` (client) runs `mermaid.render(id, chart)` in a `useEffect`, sets the SVG string in state,
   and injects it; its module-level `themeCSS` restyles every diagram type to the palette (with
   `[data-theme="dark"]` overrides inside the SVG) so diagrams match light/dark.
6. The theme toggle flips `data-theme` on `<html>`; the palette swap is pure CSS; `Mermaid` re-keys to
   the resolved theme.

deepwiki's generation boot-flow (cache-miss -> fetch repo tree -> WebSocket structure/page prompts ->
cache write) is **entirely removed**: there is no cache miss because the content is the maps on disk.

## Deployment

`hosting ∈ {local, aws, gcp}`, default `local`.

- **local** — `Dockerfile` (multi-stage node build -> `node:alpine` final running only
  `node server.js` from the standalone output) + `docker-compose.yml` (one service, one port
  `{{port}}`, a **content volume** mapping the host maps dir to `WIKI_CONTENT_DIR`, a `/health`
  healthcheck). This is deepwiki's single-image Docker pattern **generalized**: the Python stage, the
  Node-on-python-slim hack, the git install, the tiktoken pre-warm, the dual-process `start.sh`, and
  `wait -n` all drop (no second process). Demo path: `npm install && npm run build && npm run start`.
- **aws / gcp** — `iac/<cloud>/` ship **service-layer plug-ins only**, shaped to the
  **`config-management` phenotype's** `contract_surface`: a thin `module "this"` call into
  config-management's `microservice` module reading the platform layer via remote state, plus
  `variables.tf` and an `env.tfvars.example` (module inputs `project` / `service` / `env` / `image` /
  `enable_*`; naming `${project}-${service}-${env}`). The cross-seed is declared on the manifest as
  `components.deploy.via = "config-management phenotype"` (the **ai-management precedent** — no schema
  extension). To host on a cloud you first **emit the `config-management` phenotype** for the
  platform / load-balancer / registry layers, then apply `iac/<cloud>/`.

Each `iac/<cloud>/` set is **`tofu validate`-able after rendering** (the templates carry `{{param}}`
placeholders; render with dummy params into a temp dir, `tofu init -backend=false && tofu validate`).

## Variation points

- **`hosting`** — `local` (Docker / docker-compose) | `aws` | `gcp` (config-management service-layer
  plug-ins). Default `local`.
- **`theme_default_mode`** — `system` | `light` | `dark`. Default `system` (deepwiki's
  zero-flash default).
- **Palette** — the 10 CSS-var hexes are a default preset; overridable in `globals.css`
  (the shipped values are the unbranded "warm paper + soft purple" default).
- **`port`** — scaffold parameter, default `3000` (deepwiki's hardcoded 3000, now a knob).

## When to use / When NOT

**When to use**

- You have pre-generated codebase documentation (CT6 `*_MAP.md`, or any markdown maps) and want a
  visually appealing, navigable, self-hosted wiki for one or many codebases.
- You want Mermaid diagrams, a navigation tree, and dark/light theming without standing up an LLM,
  a database, or a second backend process.
- You want a static-content site you can run locally via Docker or push to a cloud through the
  config-management phenotype.

**When NOT**

- You need **live LLM generation / Q&A** over the code (that is exactly the stripped capability — use
  deepwiki-open itself, or the `ai-management` phenotype for an LLM control plane).
- The content is not markdown maps (this phenotype ingests `*_MAP.md`; a different content shape needs
  a different loader).
- A single static README suffices — the wiki shell is more than that one file warrants.

## Reuse-Decision hooks

- **Deploy** — `components.deploy.via = "config-management phenotype"`. For cloud hosting, reuse the
  `config-management` phenotype for the platform/LB/registry layers; this phenotype ships only the
  service-layer module-call (the ai-management precedent). Do not author a parallel IaC stack.
- **Content producers** — the `*_MAP.md` artifacts are produced by the CT6 map skills (CODEBASE_MAP /
  INTEGRATION_MAP / etc.) unchanged; this phenotype only **reads** them. Reuse those producers; do not
  re-derive maps here.
- **Wiki UI** — when a build needs a documentation/wiki surface, reuse this phenotype's scaffold rather
  than re-implementing a markdown+Mermaid+tree viewer. Extend the loader for a new content shape; keep
  the `WikiStructure`/`WikiPage` contract.
- **Engine + schema** — emit / validate / match via `scripts/phenotypes/phenotypes.py` unchanged; the
  record conforms to `phenotypes/SCHEMA.md`. No engine or schema changes are introduced.
