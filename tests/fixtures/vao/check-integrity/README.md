# check-integrity fixtures

Inputs for `verify-check-can-fail` (`hooks/vao/check_integrity.py`), the 21st
Layer-3 VAO tool. Consumed by `tests/test_vao_check_can_fail.py`; the two
top-level artifacts double as the CLI demo pair.

| Artifact | Expected |
|---|---|
| `vacuous-and-unproven-checks.json` | exit 2 — 7 gaps across all three severities |
| `proven-checks-clean.json` | exit 0 — no gaps |

Cited `output_path` / `tsconfig_path` values are relative to THIS directory, so
callers pass `repo_root=<this dir>` (CLI: `--repo-root`).

## Encoding fixtures — provenance

Two fixtures exist specifically to pin the A5/A7 encoding-evasion fix, where
reading every cited output as UTF-8 let a UTF-16 log defeat the entire scan.
Both were generated on **Windows PowerShell 5.1.26100.8875** and their bytes
were measured, not assumed:

```powershell
$lines = @(
  "============================= test session starts =============================",
  "platform win32 -- Python 3.12.4, pytest-8.2.0, pluggy-1.5.0",
  "collected 0 items",
  "",
  "============================ no tests ran in 0.04s ============================"
)

# (a) the documented PS 5.1 Unicode form -> TRUE UTF-16LE
$lines | Out-File -FilePath .\pytest-collected-0-utf16le.txt -Encoding Unicode

# (b) plain `>` redirection
& { $lines | ForEach-Object { $_ } } > .\pytest-collected-0-utf8bom.txt
```

| Fixture | Leading bytes | NUL ratio | Encoding |
|---|---|---|---|
| `pytest-collected-0-utf16le.txt` | `255,254` (`ff fe`) | 0.498 | UTF-16LE + BOM |
| `pytest-collected-0-utf8bom.txt` | `239,187,191` (`ef bb bf`) | 0.000 | UTF-8 + BOM |

**Measured caveat, recorded because it contradicts a common assumption.**
PowerShell 5.1 is widely documented as defaulting `>` redirection to UTF-16LE.
On this machine it did **not** — `>` produced UTF-8-BOM (row b above, zero NUL
bytes), which the pre-fix code already read correctly. The genuinely evading
file is row (a), produced by `Out-File -Encoding Unicode`. The hole is real and
reachable — a stock PS 5.1 install whose redirection default has not been
overridden, any UTF-16-emitting tool, or an explicit `-Encoding Unicode` — but
it is **not** reachable through `>` in this environment. Fixture (b) is kept as
the negative control: it must decode cleanly and its BOM must not leak into the
text as a stray leading character.

Handled by `_decode_output_bytes`: explicit BOM wins (`utf-8-sig` / `utf-16`);
otherwise a NUL ratio at or above one third triggers a `utf-16-le` then
`utf-16-be` retry; otherwise `utf-8` with replacement, which never raises.

## Runner-output fixtures

`outputs/` holds captured console logs in the shapes real runners emit.
Zero-work signatures (`pytest-collected-0*`, `playwright-no-tests-found`,
`playwright-zero-total`, `jest-no-test-files`, `vitest-no-tests-found`,
`tsc-noemit-*`) must be flagged; genuine reds (`pytest-red-*`,
`make-test-red-tb-no`, `npm-vitest-red-wrapped`) must be accepted; greens
(`pytest-green-*`, `tsc-build-clean`) must not be flagged.

Three precision fixtures exist to keep the detectors honest, each pinning a
false-positive the tool must NOT produce:

- `pytest-green-quoting-the-signature.txt` — a 57-test green run that *echoes*
  `collected 0 items` in captured stdout. Not vacuous; only line-anchored
  matching separates it from the real thing.
- `pytest-collected-0-buried-in-padding.txt` — the mirror: a REAL
  `collected 0 items` collection line at line start, buried under 88 lines of
  passing-looking padding and a fabricated `1847 passed` summary. Still vacuous.
- `pytest-green-with-xfail.txt` / `pytest-green-names-contain-failed.txt` —
  green runs containing `xfailed` and test names containing `failed`. Neither
  may satisfy a red run; this is why failure evidence is count-aware.

`tsconfig-solution/`, `tsconfig-solution-jsonc/` (with `//` comments, so the
JSON parse fails and the text-shape fallback is exercised) and
`tsconfig-normal/` back the repo-state predicate.
