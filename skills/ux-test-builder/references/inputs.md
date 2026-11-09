# Inputs

`$REQ_DIR` (bound by `/architect-team:ux-test` from the user's argument) is the requirement. It comes in ONE of two forms — both first-class, fully-supported inputs, identical to `/architect-team`:

1. **A requirements folder** — a filesystem path holding a UX brief (persona, objectives, target site, credentials reference).
2. **A plain-language requirement** — prose typed directly: *"a secretary uploading and checking files, against https://app.example.com, using credentials in $UX_TEST_CRED"*.

The v0.9.17 same-input-forms rules apply verbatim — do NOT refuse plain-language prose, do NOT treat the first word of a sentence as a path, ask only when input is genuinely empty.

**Flags passed by the `/architect-team:ux-test` command:**

- `--site <URL>` — the target site URL.
- `--dev` — use the project's dev environment, resolved from `design.md`'s `## Dev Environment` section.
- `--credentials <env-var>` — the env-var NAME holding the auth secret (NEVER the secret itself).
- `--persona <description>` — the persona description (or read from prose).
- `--objectives <text>` — what the persona is trying to do (or read from prose).
- Plus standard flags: `--no-commit`, `--no-push`, `--no-compact`, `--allow-push-to-default`, `--proposal-first`.
