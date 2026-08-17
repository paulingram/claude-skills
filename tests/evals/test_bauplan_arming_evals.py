# -*- coding: utf-8 -*-
"""Live Bauplan arming evals (opt-in; CT6_EVALS=1).

Three behavioral claims a unit test cannot settle, because they are about what
the MODEL reaches for when it meets a project, not about what a function returns:

  1. armed      — a repo carrying `bauplan_project.yml` leads the model to a
                  `bauplan-*` skill rather than generic data-engineering.
  2. not armed  — an ordinary repo with no marker and no stated Bauplan intent
                  leads it to NONE of them (AC4, the no-false-arming claim, and
                  the one that protects every user with no lakehouse).
  3. greenfield — "build me a Bauplan pipeline" with no marker still reaches
                  `bauplan-data-pipeline`. Absent this, the flagship skill ships
                  unreachable in the exact case it was written for.

The arming DECISIONS these rest on are pinned deterministically in the default
suite (`tests/test_bauplan_eval_fixtures.py`), so a failure here means the model
routed differently — not that the logic drifted. That separation is the point:
this tier answers only the question that genuinely needs a live model.

Never collected in the default suite (`tests/conftest.py` `collect_ignore`), and
skipped at runtime when the live prerequisites are absent.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.evals import collector, runner
from tests.evals._support import eval_model, requires_live_claude

pytestmark = requires_live_claude

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bauplan"

_BAUPLAN_SKILLS = (
    "bauplan-explore-data",
    "bauplan-data-assessment",
    "bauplan-data-pipeline",
    "bauplan-safe-ingestion",
    "bauplan-data-quality-checks",
    "bauplan-debug-and-fix-pipeline",
)

# The capability surface shown to the model. Deliberately does NOT say "use these
# when you see bauplan_project.yml" — that inference is exactly what is being
# measured, and stating the trigger would test the prompt instead of the routing.
_CAPABILITY_SURFACE = """\
Skills available in this workspace:
- bauplan-explore-data          : read-only inspection of a Bauplan lakehouse
- bauplan-data-assessment       : can a question be answered with available data
- bauplan-data-pipeline         : create a Bauplan pipeline project, SQL/Python models
- bauplan-safe-ingestion        : ingest from S3 with branch isolation + write-audit-publish
- bauplan-data-quality-checks   : generate expectations.py quality checks
- bauplan-debug-and-fix-pipeline: diagnose a failed Bauplan job
- (plus the ordinary general-purpose tools)
"""

# (name, project-shape description, task, expectation)
_CASES = [
    (
        "bauplan-armed-marker-project",
        "The repository root contains `bauplan_project.yml`, and a `models/` "
        "directory holds a Python model decorated `@bauplan.model()`.",
        "add a new cleaned table derived from the existing `taxi_trips` table, "
        "with a data-quality check on it",
        "any",
    ),
    (
        "bauplan-not-armed-bare-project",
        "The repository is an ordinary Python project: a `main.py` and a README. "
        "There is no lakehouse, no warehouse, and no data platform configured.",
        "add a function that reads a CSV file and prints the row count",
        "none",
    ),
    (
        "bauplan-greenfield-stated-intent",
        "The repository has no Bauplan configuration at all — there is no "
        "`bauplan_project.yml`, because the project does not exist yet.",
        "build a new Bauplan data pipeline here from scratch, reading a raw "
        "table and producing a cleaned one (yes, this project targets Bauplan)",
        "bauplan-data-pipeline",
    ),
]


def _build_prompt(shape: str, task: str) -> str:
    return (
        f"{_CAPABILITY_SURFACE}\n"
        f"{shape}\n\n"
        f"Task: {task}.\n\n"
        "Name the skill or skills you would reach for FIRST, stating each exact "
        "skill name on its own line, then one sentence of justification. If none "
        "of the listed skills apply, say so explicitly. Do not run anything.\n"
    )


def _evidence(transcript) -> str:
    """Every transcript surface a skill name could surface in, lower-cased."""
    parts = [transcript.final_text or ""]
    parts.extend(transcript.texts)
    for tc in transcript.tool_calls:
        parts.append(str(tc.get("name", "")))
        parts.append(str(tc.get("input", "")))
    return "\n".join(parts).lower()


@pytest.mark.parametrize("name,shape,task,expectation", _CASES)
def test_bauplan_arming_routes_as_specified(name, shape, task, expectation, tmp_path):
    cfg = runner.RunnerConfig(
        model=eval_model(),
        max_turns=3,
        max_budget_usd=0.5,
        timeout_s=180,
    )
    transcript = runner.run(_build_prompt(shape, task), cfg)
    evidence = _evidence(transcript)
    hits = [s for s in _BAUPLAN_SKILLS if s in evidence]

    if expectation == "any":
        matched = bool(hits)
        failure = (
            f"a marker-bearing Bauplan project reached for no bauplan-* skill "
            f"(AC3). Evidence:\n{evidence[:1000]}"
        )
    elif expectation == "none":
        matched = not hits
        failure = (
            f"an ordinary non-Bauplan project falsely armed the Bauplan path "
            f"(AC4) — reached for {hits}. Evidence:\n{evidence[:1000]}"
        )
    else:
        matched = expectation in hits
        failure = (
            f"stated Bauplan intent with no marker did not reach {expectation} "
            f"(AC5, the greenfield case) — reached for {hits}. "
            f"Evidence:\n{evidence[:1000]}"
        )

    collector.write_run(
        [
            {
                "name": name,
                "verdict": "pass" if matched else "fail",
                "turns": transcript.num_turns,
                "tool_calls": transcript.tool_count,
                "cost_usd": transcript.cost_usd,
                "duration_s": transcript.duration_s,
            }
        ],
        tmp_path,
    )

    assert matched, failure
