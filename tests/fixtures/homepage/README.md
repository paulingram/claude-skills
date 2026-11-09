# homepage fixture workspace

Small versions of every source `scripts/homepage/build.py` reads. The real
names `.architect-team/` and `.architect-team-*.json` are gitignored in this
repo, so the fixture stores them under neutral names and
`tests/test_homepage.py::make_workspace` materializes them into a tmp dir:

- `workspace/**`          -> `<ws>/**` (docs maps, lineage graph, suite manifest, a source file)
- `configs/<name>.json`   -> `<ws>/.architect-team-<name>.json`
- `state/**`              -> `<ws>/.architect-team/**`

`configs/notify.json` and `configs/publish.json` carry PLANTED secret values
(`PLANTED-SECRET`) that the page must never render.

Test-shaped files (`*.spec.ts`, `test_*.py`) rest here with a `.tmpl` suffix
(`e2e/personas/shopper/checkout.spec.ts.tmpl`) because
`hooks/discipline_registry.py` globs `**/*.spec.ts` repo-wide and would count
a bare fixture spec as an unclassified QA test of THIS repo;
`make_workspace` strips the suffix when it materializes the workspace.
