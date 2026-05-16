## Context

The `architect-team` plugin v0.2.3 has three execution surfaces that invoke the Python interpreter:

1. **`commands/architect-team-setup.md`** — a markdown slash command whose body contains a `python "${CLAUDE_PLUGIN_ROOT}/scripts/setup/setup.py" $ARGUMENTS` block. The harness extracts the `command` and runs it through `/bin/bash` (Linux/macOS) or `cmd.exe` / PowerShell (Windows).
2. **`hooks/hooks.json`** — two hooks (`PostToolUse(TaskUpdate)` and `SubagentStop`) whose `command` fields are `python "${CLAUDE_PLUGIN_ROOT}/hooks/review-gate-task.py"` and `python "${CLAUDE_PLUGIN_ROOT}/hooks/teammate-idle-check.py"` respectively. Same shell invocation path.
3. **`scripts/setup/setup.py`** — the script itself uses `#!/usr/bin/env python3` shebang AND calls `python -m pip show` / `python -m pip install` internally when checking and installing dependencies.

The bug is in surfaces 1 and 2: they assume the bare name `python` resolves to a Python 3 interpreter. Surface 3 also has a latent issue — its internal `subprocess.run([sys.executable, "-m", "pip", ...])` is correct, but the *initial* invocation of setup.py from the slash command is what fails (surface 1).

## Approach

Replace bare `python` with `python3` in surfaces 1 and 2. This is the canonical invocation on all three supported platforms (see proposal § Why). Surface 3 already uses `sys.executable` for its internal calls — once setup.py is reachable, it is portable.

### Why `python3` and not a shell-detection shim

Alternatives considered:

| Option | Pros | Cons | Decision |
|---|---|---|---|
| `python3` everywhere | Single token, works on Linux + macOS + modern Windows | Requires `python3.exe` on Windows PATH (typical default) | ✅ Chosen |
| Shell shim: `command -v python3 \|\| python` | Maximum compatibility | Quoting nightmare in JSON; breaks on Windows cmd; fragile | ❌ |
| Per-OS wrapper script (`run-python.sh` + `.cmd`) | Robust | Two new files; increases surface area; violates extend-first | ❌ |
| `py -3` (Windows launcher) | Native Windows | Doesn't exist on Linux/macOS | ❌ |
| Document the `python` requirement in README | Zero code change | Doesn't fix the bug; just shifts blame to the user | ❌ |

`python3` is chosen for being the minimum-diff fix that follows existing convention (the `#!/usr/bin/env python3` shebang in every Python file in the repo is already `python3`-explicit).

### Why a `python3-on-PATH` detection branch in setup.py

When setup.py *is* reachable (manual invocation via `python3 setup.py`) but the slash command can't reach it (because hooks.json still uses `python`), users get cryptic hook failures. The new detection branch in setup.py raises this explicitly with one-liner remediation per OS:

- Linux (apt): `sudo apt install python-is-python3` (creates `/usr/bin/python` → `python3` alias)
- macOS (homebrew): `brew install python` (creates `python3` symlink; `python` is intentionally absent post-Monterey)
- Windows: re-run python.org installer with "Install for all users" + "Add to PATH" + "py launcher" checked; or use the Microsoft Store stub

The detection is non-fatal — it warns but does not block. The setup completes regardless, because the *current* invocation of setup.py proves Python 3 is installed *somewhere*. The warning serves the cross-shell hook path.

### Hook command robustness

We are not introducing fallback chains, error handling, or retry logic in hook commands. If `python3` isn't on PATH the hook will fail loudly with `python3: command not found` and the user will see it in the next `TaskUpdate` event. That's the correct behavior — the alternative (silent fallback) hides misconfiguration.

## Test Strategy

- **REQ-001 (command)**: structural test in `tests/test_commands.py` already verifies frontmatter validity. Add an explicit assertion that the body contains `python3` (not bare `python`).
- **REQ-002 (hooks)**: existing `tests/test_hooks_structure.py` verifies hooks.json schema. Add explicit assertion that both `command` fields use `python3`.
- **REQ-003 (setup)**: new unit tests in `tests/test_setup_script.py` for the new `_python3_on_path()` helper using `unittest.mock.patch` on `shutil.which`.
- **REQ-004 (tests)**: covered by tests added under REQ-003 acceptance.
- **REQ-005 (README)**: no test; visual review during PR.
- **REQ-006 (release)**: standard release verification — `python -m pytest -v` clean (54 → 57+ PASS), version strings match, tag exists.

Full suite expectation: existing 54 tests + 3 new (REQ-003) + 2 new (REQ-001/REQ-002 assertions) = **59 tests minimum**.

## Rollout

Single-version release v0.2.4 to the existing `paulingram/claude-skills` marketplace. No migration. Users on v0.2.3 with manually-aliased `python` continue working; users without the alias begin working. `/plugin update architect-team` is the upgrade path.

## Open Questions

None. The fix is mechanical, the platform matrix is enumerated, and the test plan covers all REQs.
