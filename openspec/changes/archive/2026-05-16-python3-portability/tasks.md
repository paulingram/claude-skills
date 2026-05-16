## 1. REQ-001: Fix `python` → `python3` in setup command

- [ ] 1.1 Edit `commands/architect-team-setup.md` line 4: replace `"Bash(python:*)"` with `"Bash(python3:*)"` in the `allowed-tools` frontmatter array.
- [ ] 1.2 Edit `commands/architect-team-setup.md` line 12 (inside the ```! block): replace `python "${CLAUDE_PLUGIN_ROOT}/scripts/setup/setup.py" $ARGUMENTS` with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup/setup.py" $ARGUMENTS`.
- [ ] 1.3 Grep the file: `grep -n '\bpython\b' commands/architect-team-setup.md` — expected: zero matches for bare `python` (all hits should be `python3`).

## 2. REQ-002: Fix `python` → `python3` in hooks

- [ ] 2.1 Edit `hooks/hooks.json` line 9: replace `"command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/review-gate-task.py\""` with `"command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/review-gate-task.py\""`.
- [ ] 2.2 Edit `hooks/hooks.json` line 21: replace `"command": "python \"${CLAUDE_PLUGIN_ROOT}/hooks/teammate-idle-check.py\""` with `"command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/teammate-idle-check.py\""`.
- [ ] 2.3 Validate JSON: `python3 -c "import json; json.load(open('hooks/hooks.json'))"` — expected: no exception.
- [ ] 2.4 Grep the file: `grep -n '"python ' hooks/hooks.json` — expected: zero matches.

## 3. REQ-003: Detection helper in setup.py

- [ ] 3.1 Add `_python3_on_path() -> tuple[bool, str | None]` helper to `scripts/setup/setup.py`: uses `shutil.which("python3")`. Returns `(True, path)` on success, `(False, remediation_string)` on failure. The remediation string is OS-specific per `sys.platform` ("linux", "darwin", "win32"). Documented in proposal Design § "Why a python3-on-PATH detection branch".
- [ ] 3.2 In `main()`, immediately after the existing `check_python_version()` row, append a new `("python3-on-path", "present"|"warn", message)` row to `rows`. Treat absence as a warning (not a failure) — print the message but do not raise.
- [ ] 3.3 Verify by running `python3 scripts/setup/setup.py --check-only` locally — expected: new row appears in the output table.

## 4. REQ-004: Tests for detection helper + command/hook assertions

- [ ] 4.1 Add `test_python3_on_path_returns_true_when_present` to `tests/test_setup_script.py`: patches `shutil.which("python3")` → `/usr/bin/python3`, asserts helper returns `(True, "/usr/bin/python3")`.
- [ ] 4.2 Add `test_python3_on_path_returns_remediation_when_missing_linux` to `tests/test_setup_script.py`: patches `shutil.which` → `None` and `sys.platform` → `"linux"`, asserts helper returns `(False, str)` and `"python-is-python3"` appears in the remediation string.
- [ ] 4.3 Add `test_python3_on_path_returns_remediation_when_missing_windows` to `tests/test_setup_script.py`: patches `shutil.which` → `None` and `sys.platform` → `"win32"`, asserts helper returns `(False, str)` and `"py launcher"` or `"python.org"` appears in the remediation string.
- [ ] 4.4 Add `test_setup_command_uses_python3` to `tests/test_commands.py`: reads `commands/architect-team-setup.md`, asserts it contains `python3` and does NOT contain a bare ` python ` (space-delimited) outside of code-comment context.
- [ ] 4.5 Add `test_hooks_use_python3` to `tests/test_hooks_structure.py`: parses `hooks/hooks.json`, asserts each hook `command` starts with `python3 ` (with trailing space — disambiguates from `python3-foo`).
- [ ] 4.6 Run `python -m pytest tests/test_setup_script.py tests/test_commands.py tests/test_hooks_structure.py -v` — confirm all new tests pass and no existing tests regress.
- [ ] 4.7 Run full suite: `python -m pytest -v` — confirm 59+ PASS (54 prior + 3 from §4.1-4.3 + 1 from §4.4 + 1 from §4.5).

## 5. REQ-005: README prerequisites section

- [ ] 5.1 Edit `README.md`: add a `## Prerequisites` subsection (or extend the existing one) listing: Python 3.10+ available as `python3` on `$PATH`; with per-OS one-liner remediation (Ubuntu/Debian: `sudo apt install python-is-python3`; macOS: `brew install python` if missing; Windows: re-run python.org installer with "Add to PATH" or use `py launcher`).
- [ ] 5.2 Verify README still passes any existing markdown lint via `python -m pytest tests/ -v` (no test gates README content but adding a section should not break anything).

## 6. REQ-006: Release v0.2.4

- [ ] 6.1 Bump `.claude-plugin/plugin.json` `version` field from `"0.2.3"` to `"0.2.4"`.
- [ ] 6.2 Bump `.claude-plugin/marketplace.json` `plugins[0].version` field from `"0.2.3"` to `"0.2.4"`.
- [ ] 6.3 Prepend new entry to `CHANGELOG.md`:
  ```
  ## [0.2.4] — 2026-05-16

  ### Fixed
  - `/architect-team:architect-team-setup` slash command and both review-gate / teammate-idle hooks now invoke `python3` instead of bare `python`. Fixes "python: command not found" on stock Ubuntu / Debian / macOS where only `python3` is on `$PATH`. (python3-portability REQ-001, REQ-002)

  ### Added
  - Setup script reports whether `python3` is resolvable on `$PATH` (separate from in-process version check) with per-OS remediation hints. (python3-portability REQ-003)
  - Test coverage for the new helper (3 tests) plus assertions that the setup command and both hooks use `python3` (2 tests). Suite grows to 59+ PASS. (python3-portability REQ-004)

  ### Documented
  - README now lists `python3` as an explicit prerequisite with one-line OS-specific remediation. (python3-portability REQ-005)
  ```
- [ ] 6.4 Run full suite ONE MORE TIME from a clean state: `python -m pytest -v` — confirm 59+ PASS.
- [ ] 6.5 Commit with explicit author override:
  ```
  git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "v0.2.4: python3 invocations across command + hooks"
  ```
- [ ] 6.6 Tag (annotated) with same author override:
  ```
  git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" tag -a v0.2.4 -m "v0.2.4 — python3 portability"
  ```
- [ ] 6.7 Push `main` and the tag to `origin`:
  ```
  git push origin main
  git push origin v0.2.4
  ```
- [ ] 6.8 Verify by reading `~/.claude/plugins/installed_plugins.json` after `/plugin update architect-team`: expected `"version": "0.2.4"` and a fresh `gitCommitSha` matching the v0.2.4 commit.

## 7. Archive

- [ ] 7.1 After all REQs verified, move `openspec/changes/python3-portability/` to `openspec/changes/archive/2026-05-16-python3-portability/` and merge any spec deltas into `openspec/specs/python3-portability/`.
