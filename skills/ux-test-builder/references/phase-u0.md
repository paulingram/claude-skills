# Phase U0 — Intake

The orchestrator captures the persona description, objectives, target, and credentials reference. Persisted at `<cwd>/.architect-team/ux-tests/<persona-slug>/intake.json`:

```json
{
  "schema_version": 1,
  "persona_slug": "<kebab-case derived from persona description>",
  "persona_description": "<verbatim from user>",
  "objectives": "<verbatim from user>",
  "target": {
    "kind": "url" | "dev",
    "url": "<https://...>" | null,
    "dev_environment_ref": "<from design.md ## Dev Environment>" | null
  },
  "credentials": {
    "env_var": "<UX_TEST_PASSWORD or similar>",
    "username": "<plain — non-secret>" | null,
    "username_env_var": "<UX_TEST_USERNAME>" | null,
    "auth_flow": "<form | sso | oauth | api-token | etc.>"
  },
  "created_at": "<ISO 8601 UTC>"
}
```

**Credential handling — non-negotiable.** The env-var NAME is recorded; the secret VALUE is NEVER persisted in any artifact. The orchestrator (and downstream agents) read `os.environ[<env_var>]` at execution time. Persisting a raw secret in `intake.json` / a verdict file / a trace / a screenshot is a structural failure of this skill.

**Vague-input escalation.** If the persona/objectives lack enough detail to author a literal flow (no clear primary task, no entry point, no expected outcome), the orchestrator emits a structured question to the user:

> *"I have your persona ('\<verbatim\>') and target ('\<URL\>'), but the objectives don't specify enough to author a single literal flow. Specifically: (a) what is the persona's primary task?, (b) what's the entry point — sign in, deep link, navigation from another page?, (c) what does the persona expect to see when they succeed?"*

Domain gate; pause until the user answers.
