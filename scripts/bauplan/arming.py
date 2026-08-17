# -*- coding: utf-8 -*-
"""The Bauplan arming decision (spec ``project-trait-arming``).

One pure function. Given what the run knows about its target - was the project
marker DETECTED on disk, did the request STATE the intent, and has the user
answered the arming confirmation - it decides whether the Bauplan capability is
armed for this run, and whether the run still owes the user a question.

The asymmetry is the whole point: "Deterministic signals arm silently and
inferred signals require one confirmation."

- A detected marker is proof on disk. It arms with no user interaction, and no
  answer carried in from elsewhere can disarm it, because no question was ever
  surfaced on that path.
- Stated intent is an inference, and it is the ONLY signal available before a
  project exists. It surfaces exactly one confirmation before the first
  bauplan-specific dispatch and arms only on an affirmative answer. That
  confirmation is a DOMAIN gate, not process ceremony - the user's answer
  determines what gets built - so it fires regardless of any process-gate
  opt-out. Enforcing that is the caller's job; this function's contribution is
  to report ``requires_confirmation`` truthfully so the caller cannot skip it
  by accident.
- A decline degrades the run to generic behavior and is RECORDED, never
  silent: ``disposition`` is what the run report prints.

Purity (no I/O, no filesystem, no clock, no side effects) is deliberate. It is
what lets this truth table run in the DEFAULT key-free suite; the
model-behavior claims that a real run actually reaches a bauplan skill live in
the opt-in eval tier behind ``CT6_EVALS=1`` (D7).
"""
from __future__ import annotations

#: Which evidence armed - or would have armed - the run.
SIGNAL_MARKER = "marker"
SIGNAL_INTENT = "intent"
SIGNAL_NONE = "none"

#: The recordable outcome. The run report prints this verbatim, so a declined
#: or degraded run always names what happened rather than staying silent.
DISPOSITION_ARMED_BY_MARKER = "armed-by-marker"
DISPOSITION_AWAITING_CONFIRMATION = "awaiting-confirmation"
DISPOSITION_ARMED_BY_CONFIRMED_INTENT = "armed-by-confirmed-intent"
DISPOSITION_DECLINED = "declined"
DISPOSITION_NOT_ARMED_NO_SIGNAL = "not-armed-no-signal"


def resolve_bauplan_arming(
    marker_detected: bool,
    stated_intent: bool,
    confirmation: bool | None,
) -> dict[str, object]:
    """Resolve whether the Bauplan capability is armed for this run.

    Args:
        marker_detected: the deterministic signal - a `bauplan_project.yml`
            was found in the workspace (see
            ``hooks.discipline_registry._has_bauplan_markers``).
        stated_intent: the inferred signal - the request says it targets the
            Bauplan platform. The only signal available on a greenfield run,
            where no marker can yet exist.
        confirmation: the user's answer to the arming confirmation - ``True``
            affirmative, ``False`` declined, ``None`` not yet asked.

    Returns:
        ``{armed, signal, requires_confirmation, disposition}``.
        ``armed`` and ``requires_confirmation`` are never both true: a run is
        either cleared to dispatch or still owes the question.
    """
    # 1. Deterministic signal. Proof on disk arms silently - no question is
    #    surfaced here, so `confirmation` is not this path's to consume and a
    #    stray value must not be able to disarm a proven trait.
    if marker_detected:
        return _result(True, SIGNAL_MARKER, False, DISPOSITION_ARMED_BY_MARKER)

    # 2. Inferred signal. Exactly one confirmation, then arm only on yes.
    if stated_intent:
        if confirmation is None:
            return _result(False, SIGNAL_INTENT, True, DISPOSITION_AWAITING_CONFIRMATION)
        if confirmation:
            # The greenfield cell. `bauplan-data-pipeline` creates a project
            # from scratch, so no marker CAN exist yet; this is the only route
            # by which that skill is ever reachable.
            return _result(True, SIGNAL_INTENT, False, DISPOSITION_ARMED_BY_CONFIRMED_INTENT)
        # Declined: proceed generically, and say so in the run report.
        return _result(False, SIGNAL_INTENT, False, DISPOSITION_DECLINED)

    # 3. No signal. Nothing is asked and nothing is dispatched - a confirmation
    #    with no signal behind it is an answer to a question never posed.
    return _result(False, SIGNAL_NONE, False, DISPOSITION_NOT_ARMED_NO_SIGNAL)


def _result(
    armed: bool,
    signal: str,
    requires_confirmation: bool,
    disposition: str,
) -> dict[str, object]:
    return {
        "armed": armed,
        "signal": signal,
        "requires_confirmation": requires_confirmation,
        "disposition": disposition,
    }
