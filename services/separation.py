# -*- coding: utf-8 -*-
"""The service-tier separation manifest + the separability invariant (REPO-1…4) — stdlib-only.

REPO-1/2: the plan is to split into TWO repos — the open core (this repo) and a
separate, separately-distributed repo for the paid/closed pieces (the SEC-4
project-unique attestation algorithm; the SMP-4 phenotype purchase/billing). REPO-3:
for now the features stay in `services/` but are DESIGNED so they can later be
separated. REPO-4: "separated out" means each service is an effectively independent
unit that the core can opt to use or not, reaching every external/closed capability
through an INJECTED ADAPTER rather than a hard dependency.

This module is the machine half of that design:
- `SEPARATION_MANIFEST` documents the boundary: each service (separable), the
  ADAPTER SEAMS the closed/paid pieces plug into, and the paid/closed pieces.
- `check_separation(...)` ENFORCES REPO-4 deterministically: it parses every
  `services/**/*.py` and asserts each is IMPORT-CLEAN — only stdlib + in-repo
  modules at module load; any external/third-party top-level import is a violation
  (external + closed capabilities MUST be injected, never hard-imported). That
  import-cleanliness IS what makes a service liftable into its own repo.

HONEST BOUNDARY: this DESIGNS + validates the boundary. The actual repo SPLIT (and
the closed repo's contents) is a future operation, not performed here.
"""
from __future__ import annotations

import ast
import pathlib
import sys
from typing import Any, Optional

SCHEMA = "service-separation/v1"

# The two cross-directory in-repo reuse points services import by bare name (they
# live OUTSIDE services/ and are reused per the extend>reuse ladder, loaded via the
# per-module sys.path.insert pattern): scripts/phenotypes/phenotypes.py (SMP-4) and
# scripts/helpdesk/logit.py (the privacy engine). Everything else a service imports
# by bare name is a services/ sibling.
_EXTRA_INREPO_MODULES = ("phenotypes", "logit")

SEPARATION_MANIFEST: dict[str, Any] = {
    "schema": SCHEMA,
    "repos": {
        "open_core": "claude-team-6 (this repo) — services/ written separable (REPO-3)",
        "paid_closed": "a separate, separately-distributed repo for the paid/closed pieces (REPO-1/2)",
    },
    "services": [
        {"name": "common", "dir": "services/common", "separable": True,
         "role": "the shared substrate (Ed25519 + handshake + bg_runtime + config)"},
        {"name": "librarian", "dir": "services/librarian", "separable": True,
         "reuses": ["services/common"]},
        {"name": "triage", "dir": "services/triage", "separable": True,
         "reuses": ["services/common", "scripts/helpdesk/logit"]},
        {"name": "session_review", "dir": "services/session_review", "separable": True,
         "reuses": ["services/common", "services/triage"]},
        {"name": "seeded_mempalace", "dir": "services/seeded_mempalace", "separable": True,
         "reuses": ["services/common", "scripts/phenotypes/phenotypes"]},
    ],
    # The adapter SEAMS — every external/closed capability is reached through one of
    # these injected interfaces, so the open core never hard-depends on it (REPO-4).
    "seams": [
        {"seam": "attestation_verifier", "requirement": "SEC-4", "paid": True,
         "open_stub": "handshake.make_hmac_attestation_verifier (HMAC stub)",
         "closed": "the project-unique genuine-logger algorithm (cannot be copied)"},
        {"seam": "entitlements_for", "requirement": "SMP-4", "paid": True,
         "open_stub": "an injected lookup keyed on the verified public key",
         "closed": "the entitlement / billing system"},
        {"seam": "LLMClient", "requirement": "LIB-1 / EVAL-1 / SR-1", "paid": False,
         "open_stub": "FakeLLMClient", "closed": "the real Anthropic adapter (SDK + network)"},
        {"seam": "Source", "requirement": "LIB-6", "paid": False,
         "open_stub": "StaticSource", "closed": "the real web / attached-API scraper"},
        {"seam": "IssueSink / poster", "requirement": "EVAL-2", "paid": False,
         "open_stub": "InMemorySink / poster=None", "closed": "the real GitHub issues API poster"},
        {"seam": "transport", "requirement": "SMP-2", "paid": False,
         "open_stub": "an injected callable (handle_bundle_request in-process)",
         "closed": "the real HTTP fetch to the project's server"},
        {"seam": "bg_runtime daemon", "requirement": "BG-1…4", "paid": False,
         "open_stub": "generated per-OS install descriptors",
         "closed": "the actual OS daemon install + the off-machine log ship"},
    ],
    "paid_closed_pieces": [
        {"piece": "SEC-4 project-unique attestation algorithm", "seam": "attestation_verifier",
         "why": "REPO-2 — a unique signature that proves a GENUINE logger cannot be open "
                "(anyone could copy it); the open core ships the pluggable hook + an HMAC stub"},
        {"piece": "SMP-4 phenotype purchase / entitlement + billing", "seam": "entitlements_for",
         "why": "REPO-2 — the purchasable phenotype catalog model is the chargeable feature"},
    ],
}


def validate_manifest(manifest: Any) -> dict[str, Any]:
    """Validate the separation manifest's shape. Returns `{valid, errors}`."""
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return {"valid": False, "errors": ["manifest is not an object"]}
    if manifest.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA!r}")
    for key in ("repos", "services", "seams", "paid_closed_pieces"):
        if key not in manifest:
            errors.append(f"missing key: {key}")
    for s in manifest.get("services", []):
        if not isinstance(s, dict):
            errors.append(f"a services[] entry is not an object: {s!r}")
            continue
        if not s.get("separable"):
            errors.append(f"service {s.get('name')!r} must be separable (REPO-3)")
    # every paid/closed piece must name a real seam it plugs into (REPO-4)
    seams = {x.get("seam") for x in manifest.get("seams", []) if isinstance(x, dict)}
    for p in manifest.get("paid_closed_pieces", []):
        if not isinstance(p, dict):
            errors.append(f"a paid_closed_pieces[] entry is not an object: {p!r}")
            continue
        if p.get("seam") not in seams:
            errors.append(f"paid/closed piece {p.get('piece')!r} names an unknown seam {p.get('seam')!r}")
    return {"valid": not errors, "errors": errors}


def _services_dir(repo_root: Optional[pathlib.Path] = None) -> pathlib.Path:
    if repo_root is not None:
        root = pathlib.Path(repo_root)
        return root if root.name == "services" else root / "services"
    here = pathlib.Path(__file__).resolve().parent          # this file lives in services/
    return here


def _inrepo_module_names(services_dir: pathlib.Path) -> set[str]:
    names = {p.stem for p in services_dir.rglob("*.py") if "__pycache__" not in p.parts}
    names.update(_EXTRA_INREPO_MODULES)
    return names


def _module_load_imports(tree: ast.Module) -> set[str]:
    """The root module names imported AT MODULE LOAD — recursing through every
    compound statement that executes at import time (`try`/`except`, `if`, `with`,
    `for`, and CLASS bodies), but NOT descending into function bodies (imports there
    are lazy and intentionally allowed — e.g. the deferred `import anthropic` inside
    `service_config.anthropic_client`).

    A body-only scan would miss a module-load import nested in a `try/except` — the
    exact optional-dependency idiom used elsewhere in the tree (the `import bg_runtime`
    fallbacks) — so a hard `try: import chromadb` would slip past as 'clean'. This
    recursion closes that hole while still allowing genuinely-lazy in-function imports."""
    out: set[str] = set()

    def visit(node: ast.AST, in_func: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, True)                       # descend, but its imports are lazy -> ignored
            elif not in_func and isinstance(child, ast.Import):
                for a in child.names:
                    out.add(a.name.split(".")[0])
            elif not in_func and isinstance(child, ast.ImportFrom):
                if child.level == 0 and child.module:    # absolute import only (relative = in-repo)
                    out.add(child.module.split(".")[0])
            else:
                visit(child, in_func)

    visit(tree, False)
    return out


def check_separation(repo_root: Optional[pathlib.Path] = None) -> dict[str, Any]:
    """Enforce REPO-4: every `services/**/*.py` must be IMPORT-CLEAN at module load —
    only stdlib + in-repo modules. Any external/third-party module-load import is a
    violation (it should be injected via a seam). Returns `{clean, checked,
    violations}` with `violations = [{file, module}]`.

    Residual (acceptable, disclosed): the in-repo allow-list is by bare module NAME
    (the services import siblings + the two reuse points by bare name via the
    `sys.path.insert` pattern), so a same-named external package (e.g. PyPI `ed25519`
    / `logit` / `phenotypes`) would be masked. This matches RUNTIME resolution — the
    in-repo module shadows the external one on `sys.path` — so it is not a real gap.
    Requires Python 3.10+ (`sys.stdlib_module_names`)."""
    services_dir = _services_dir(repo_root)
    inrepo = _inrepo_module_names(services_dir)
    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    if not stdlib:  # pragma: no cover - the repo's floor is 3.10+
        raise RuntimeError("check_separation requires Python 3.10+ (sys.stdlib_module_names)")
    violations: list[dict[str, str]] = []
    checked = 0
    for path in sorted(services_dir.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        checked += 1
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as exc:  # pragma: no cover
            violations.append({"file": path.name, "module": f"<unparseable: {exc}>"})
            continue
        for mod in sorted(_module_load_imports(tree)):
            if mod == "__future__" or mod in stdlib or mod in inrepo:
                continue
            violations.append({"file": path.name, "module": mod})
    return {"clean": not violations, "checked": checked, "violations": violations}
