---
name: frontend-route-mapping
description: Use when the route-mapper agent is producing a ROUTE_MAP.md for a frontend codebase, or when any agent needs to consult an existing route map. Defines the ROUTE_MAP.md schema, the navigation web format, route inventory + dynamic routes + modal routes + API endpoint catalog, and what "complete" means for review.
---

# Frontend Route Mapping

Frontend codebases are not fully knowable from a file-tree map alone. Routes, navigation, and the data dependencies of each page are the actual surface area an agent must reason about when proposing changes or authoring user-flow tests. This skill defines the artifact every frontend codebase gets: `<codebase>/docs/ROUTE_MAP.md`.

## File location and format

- Path: `<codebase>/docs/ROUTE_MAP.md`.
- YAML frontmatter (required):
  ```yaml
  ---
  last_routed: 2026-05-16T10:30:00Z
  codebase: /abs/path/to/frontend
  framework: nextjs-15-app-router  # or react+react-router-6, vue+vue-router-4, etc.
  ---
  ```
- Markdown body following the schema below.

## Schema (every section is required)

### `## Route Inventory`

A table covering every route exposed by the app.

| Route | Type | Auth | Component | File | API calls | Outbound links |
|---|---|---|---|---|---|---|
| `/login` | public | none | `LoginPage` | `src/pages/Login.tsx` | `POST /auth/login` | `/`, `/signup` |
| `/dashboard` | protected | user | `Dashboard` | `src/pages/Dashboard.tsx` | `GET /api/me`, `GET /api/projects` | `/projects/:id`, `/settings` |

Columns:
- **Route** — exact path pattern as the framework defines it.
- **Type** — `public` / `protected` / `admin` / `system`.
- **Auth** — `none` / `user` / `<role>`.
- **Component** — top-level component name rendered.
- **File** — absolute or repo-relative path.
- **API calls** — every endpoint hit by the route's component tree (`METHOD /path`). Empty = `—`.
- **Outbound links** — every other route reachable from this route, via any navigation mechanism (link click, programmatic navigation, form-submit redirect).

### `## Dynamic Routes`

For routes with URL params (`/projects/:id`, `/users/:userId/posts/:postId`):

- Route pattern.
- Each param: name, type/format (UUID, slug, integer), source (URL only / URL + query).
- Data fetched per param (e.g., "`GET /api/projects/:id` returns ProjectDetail").

### `## Navigation Web`

A graph of route → outgoing edges. Use a code-block diagram or mermaid:

```
/login --[POST /auth/login 200]--> /dashboard
/dashboard --[ProjectCard click]--> /projects/:id
/projects/:id --[Edit button]--> /projects/:id/edit
/projects/:id/edit --[Save → PATCH /api/projects/:id 200]--> /projects/:id
/dashboard --[Settings link]--> /settings
```

Each edge labels the trigger (`[<element/event> → <api or condition>]`). Every navigation must appear here, including programmatic redirects from API success/failure.

### `## Entry Conditions`

For every protected/conditional route, list the predicate:

- `/dashboard`: requires session cookie; redirects to `/login` if absent.
- `/admin`: requires `user.role === 'admin'`; renders 403 page otherwise.
- `/projects/:id`: requires the user has membership in the project (server-checked, 404 otherwise).
- `/onboarding`: requires `user.onboarding_completed === false`; redirects to `/dashboard` if true.

### `## Modal & Drawer Routes`

Two kinds:

- **URL-bound** (modal/drawer state lives in the URL): list with selector. Example: `/projects/:id?modal=delete` → `DeleteProjectDialog`.
- **State-bound** (modal/drawer triggered programmatically): list the trigger component(s) → modal ID → component rendered.

### `## API Endpoint Catalog`

Every endpoint hit by the frontend, grouped by route. For each:

- Method + path.
- Where it's called (`file:line` or `file:function`).
- Inferred request shape (from the call site: types, body composition).
- Inferred success response shape (from how the result is consumed).
- Observed error handling (which statuses surface what UI).

## What "complete" means (for the codebase-map-reviewer)

A ROUTE_MAP.md is incomplete if ANY of the following:

- A route exists in the framework's routing config that is not in the Route Inventory.
- A `<Link>` / `<Navigate>` / `router.push()` / `redirect()` / `<Form action>` exists in the code that has no outgoing edge in the Navigation Web.
- A `fetch` / `axios` / query hook / RPC call exists in a route's component tree that is not in the API calls column or the API Endpoint Catalog.
- A protected route has no entry in Entry Conditions.
- A modal/drawer trigger exists in the code that is not in Modal & Drawer Routes.

Reviewers must spot-check by sampling components and confirming claims.

## Freshness

- `last_routed` is set by the route-mapper at write time, ISO 8601 UTC.
- The intake skill compares it against `git -C <codebase> log -1 --format=%cI`. Doc older than the latest commit → re-run the route-mapper. The agent uses git diff to scope the update.

## Anti-patterns to reject

| Rationalization | Rebuttal |
|---|---|
| "Routes are obvious from the file structure" | They're discoverable, not documented. Tests + reuse-first decisions need them in one place. |
| "I'll just list the top-level routes" | Dynamic and nested routes are where bugs live. List them all. |
| "API calls are scattered — too much work to map" | That's exactly why they need mapping. Future agents shouldn't re-discover them every time. |
| "Modals don't have routes" | URL-bound modals do. State-bound modals are still navigation surface — list them. |
