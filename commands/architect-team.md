---
description: Spec-to-production multi-agent coding pipeline. Takes a requirements folder (OpenSpec / Superpowers / plain markdown) and drives it end-to-end to tested, integrated production code.
argument-hint: <path-to-requirements-folder>
---

# Architect-Team Orchestration

You are starting the architect-team multi-agent coding pipeline.

**Requirements folder:** $ARGUMENTS

Invoke the `architect-team-pipeline` skill from this plugin (use the Skill tool with `skill: architect-team-pipeline`) and follow its pipeline exactly against the requirements folder above. The skill begins at Phase −1 (Intake & Mapping) and proceeds through Phase 8 (Final Report).

If `$ARGUMENTS` is empty, ask the user for the requirements folder path. Do nothing else until they provide it.
