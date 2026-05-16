---
description: Spec-to-production multi-agent coding pipeline. Takes a requirements folder (OpenSpec / Superpowers / plain markdown) and drives it end-to-end to tested, integrated production code.
argument-hint: <path-to-requirements-folder>
---

# Architect-Team Orchestration

You are starting the architect-team multi-agent coding pipeline.

**Requirements folder:** $ARGUMENTS

If `$ARGUMENTS` is empty, ask the user for the requirements folder path. Do nothing else until they provide it.

**IMPORTANT — path binding:** The Claude Code harness does NOT propagate command `$ARGUMENTS` into skill bodies automatically. You MUST treat the value of `$ARGUMENTS` shown above as `$REQ_DIR` for every reference to `$REQ_DIR` in the `architect-team-pipeline` skill. Before invoking the skill, bind this value explicitly: wherever the skill body refers to `$REQ_DIR` or "the requirements folder", substitute the path provided above. Do NOT re-prompt the user for the requirements folder path when the skill body's own `$ARGUMENTS` or `$REQ_DIR` placeholder appears empty — you already have it.

Invoke the `architect-team-pipeline` skill from this plugin (use the Skill tool with `skill: architect-team-pipeline`) and follow its pipeline exactly against the requirements folder above. The skill begins at Phase −1 (Intake & Mapping) and proceeds through Phase 8 (Final Report).
