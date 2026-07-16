"""@prod-safe read-only docs-currency reproduction.

This standalone script is deliberately named ``check_*`` rather than ``test_*``
so pytest never collects the intentionally failing Phase B1 reproduction. Passing
and skipped totals come from the newest CHANGELOG declaration, which each release
verifies with a real suite run; this detector checks living-doc consistency against
those declared release facts, while the test-file total is anchored to disk.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIVING_DOCS = (
    "README.md",
    "CLAUDE.md",
    "docs/CODEBASE_MAP.md",
    "docs/INTEGRATION_MAP.md",
    "CHANGELOG.md",
    "phenotypes/README.md",
    "phenotypes/SCHEMA.md",
)

CHANGELOG_HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+)\]")
RELEASE_HEADING = re.compile(r"^### v(\d+\.\d+\.\d+)\b")
SUITE_TOTALS = re.compile(
    r"\*\*(?:\d+\s*(?:->|→)\s*)?(?P<passing>\d+)\s+passing\s*"
    r"\+\s*(?P<skipped>\d+)\s+skipped\*\*\s*"
    r"\((?P<test_files>\d+)\s+test files\b",
    re.IGNORECASE,
)
DELTA_COUNTS = re.compile(r"\b\d{1,6}\s*(?:->|→)\s*(?:\*\*)?\d{1,6}\b")
CURRENT_ASSERTION_OVERRIDE = re.compile(
    r"\(\s*current\s*\)|\bcurrent\s*:|\bcurrent inventory\b|"
    r"\blive total\b|\blive inventory\b|\bcurrent-state\b|"
    r"\bAs of\s+(?:\*\*)?v\d+\.\d+\.\d+(?:\*\*)?.*\bit ships\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CurrentFacts:
    version: str
    marketplace_version: str
    passing: int
    skipped: int
    test_files: int
    suite_source_version: str
    suite_source_line: int
    skills: int
    agents: int
    commands: int


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    code: str
    excerpt: str


@dataclass(frozen=True)
class Exemption:
    path: str
    line: int
    code: str
    disposition: str
    excerpt: str


def _read_lines(relative_path: str) -> list[str]:
    return (ROOT / relative_path).read_text(encoding="utf-8").splitlines()


def _excerpt(line: str, limit: int = 220) -> str:
    compact = " ".join(line.strip().split())
    return compact if len(compact) <= limit else compact[: limit - 3] + "..."


def _derive_suite_totals(lines: list[str]) -> tuple[int, int, str, int]:
    """Take passing/skipped from the first top-down release totals declaration.

    The CHANGELOG totals are verified by the real suite run at each release. The
    detector checks doc consistency against those declared release facts; the
    test-file count is independently disk-anchored in ``derive_current_facts``.
    """
    entry_version = "unknown"
    for line_number, line in enumerate(lines, start=1):
        heading = CHANGELOG_HEADING.match(line)
        if heading:
            entry_version = heading.group(1)
        totals = SUITE_TOTALS.search(line)
        if totals:
            return (
                int(totals.group("passing")),
                int(totals.group("skipped")),
                entry_version,
                line_number,
            )
    raise ValueError(
        "CHANGELOG.md has no entry stating '**N passing + N skipped** (N test files'"
    )


def derive_current_facts(changelog_lines: list[str]) -> CurrentFacts:
    plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    marketplace = json.loads(
        (ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")
    )
    passing, skipped, source_version, source_line = _derive_suite_totals(
        changelog_lines
    )
    test_files = sum(
        1 for path in (ROOT / "tests").glob("test_*.py") if path.is_file()
    )
    return CurrentFacts(
        version=str(plugin["version"]),
        marketplace_version=str(marketplace["plugins"][0]["version"]),
        passing=passing,
        skipped=skipped,
        test_files=test_files,
        suite_source_version=source_version,
        suite_source_line=source_line,
        skills=sum(1 for path in (ROOT / "skills").glob("*/SKILL.md") if path.is_file()),
        agents=sum(1 for path in (ROOT / "agents").glob("*.md") if path.is_file()),
        commands=sum(1 for path in (ROOT / "commands").glob("*.md") if path.is_file()),
    )


def _readme_history(lines: list[str], version: str) -> dict[int, str]:
    dispositions: dict[int, str] = {}
    old_release = False
    timeline = False
    for number, line in enumerate(lines, start=1):
        release = RELEASE_HEADING.match(line)
        if release:
            old_release = release.group(1) != version
        if "◆  DEVELOPMENT  ◆" in line:
            old_release = False
        if "◆  STATUS  ◆" in line:
            timeline = True
        if "◆  LICENSE  ◆" in line:
            timeline = False
        if old_release:
            dispositions[number] = "README release-history section"
        if timeline:
            dispositions[number] = "README version timeline row"
    return dispositions


def _claude_history(lines: list[str]) -> dict[int, str]:
    dispositions: dict[int, str] = {}
    active = False
    for number, line in enumerate(lines, start=1):
        if line.strip() == "## Recent releases":
            active = True
        elif active and line.startswith("## "):
            active = False
        if active:
            dispositions[number] = "CLAUDE.md Recent releases historical bullet"
    return dispositions


def _changelog_history(lines: list[str]) -> dict[int, str]:
    headings = [
        number
        for number, line in enumerate(lines, start=1)
        if CHANGELOG_HEADING.match(line)
    ]
    if len(headings) < 2:
        return {}
    return {
        number: "CHANGELOG entry below the top entry"
        for number in range(headings[1], len(lines) + 1)
    }


def _codebase_history(lines: list[str]) -> dict[int, str]:
    dispositions: dict[int, str] = {}
    in_tests = False
    versioned_breakdown = False
    for number, line in enumerate(lines, start=1):
        if line.startswith("### Tests"):
            in_tests = True
            versioned_breakdown = False
        elif in_tests and line.startswith("## "):
            in_tests = False
            versioned_breakdown = False
        elif in_tests and re.match(r"^\*\*v\d+\.\d+\.\d+\s+adds\b", line):
            versioned_breakdown = True
        if in_tests and versioned_breakdown:
            dispositions[number] = "CODEBASE_MAP versioned test-history breakdown"
    return dispositions


def _history(path: str, lines: list[str], version: str) -> dict[int, str]:
    if path == "README.md":
        return _readme_history(lines, version)
    if path == "CLAUDE.md":
        return _claude_history(lines)
    if path == "CHANGELOG.md":
        return _changelog_history(lines)
    if path == "docs/CODEBASE_MAP.md":
        return _codebase_history(lines)
    return {}


def _version_surface_findings(facts: CurrentFacts, readme: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    if facts.version != facts.marketplace_version:
        findings.append(
            Finding(
                ".claude-plugin/marketplace.json",
                1,
                "plugin-marketplace-version-mismatch",
                f"plugin.json={facts.version}; marketplace.json={facts.marketplace_version}",
            )
        )

    version_badge: tuple[int, str] | None = None
    tests_badge: tuple[int, int] | None = None
    banner: tuple[int, str] | None = None
    for number, line in enumerate(readme, start=1):
        match = re.search(r"badge/version-(\d+\.\d+\.\d+)-", line)
        if match and version_badge is None:
            version_badge = (number, match.group(1))
        match = re.search(r"badge/tests-(\d+)%20passing-", line, re.IGNORECASE)
        if match and tests_badge is None:
            tests_badge = (number, int(match.group(1)))
        if number <= 60:
            match = re.search(r"\bv\s+(\d+)\s*\.\s*(\d+)\s*\.\s*(\d+)\b", line)
            if match and banner is None:
                banner = (number, ".".join(match.groups()))

    if version_badge is None:
        findings.append(Finding("README.md", 1, "missing-readme-version-badge", "version badge not found"))
    elif version_badge[1] != facts.version:
        findings.append(
            Finding(
                "README.md",
                version_badge[0],
                "readme-version-badge-mismatch",
                f"README badge={version_badge[1]}; plugin.json={facts.version}",
            )
        )
    if tests_badge is None:
        findings.append(Finding("README.md", 1, "missing-readme-tests-badge", "tests badge not found"))
    elif tests_badge[1] != facts.passing:
        findings.append(
            Finding(
                "README.md",
                tests_badge[0],
                "readme-tests-badge-mismatch",
                f"README tests badge={tests_badge[1]}; derived current passing={facts.passing}",
            )
        )
    if banner is None:
        findings.append(Finding("README.md", 1, "missing-readme-banner-version", "ASCII banner version not found"))
    elif banner[1] != facts.version:
        findings.append(
            Finding(
                "README.md",
                banner[0],
                "readme-banner-version-mismatch",
                f"README banner={banner[1]}; plugin.json={facts.version}",
            )
        )
    return findings


def _header_blockquote_findings(facts: CurrentFacts, lines: list[str]) -> list[Finding]:
    for number, line in enumerate(lines[:30], start=1):
        if not line.startswith(">"):
            continue
        match = re.search(r"\*\*v(\d+\.\d+\.\d+)", line)
        if not match:
            continue
        actual = match.group(1)
        if actual != facts.version:
            return [
                Finding(
                    "docs/CODEBASE_MAP.md",
                    number,
                    "header-blockquote-version-mismatch",
                    f"leading version v{actual} != plugin.json v{facts.version}; {_excerpt(line)}",
                )
            ]
        return []
    return [
        Finding(
            "docs/CODEBASE_MAP.md",
            1,
            "missing-header-blockquote-version",
            "no leading **vX.Y.Z header version found in first 30 lines",
        )
    ]


def _first_count_issue(
    line: str, label: str, pattern: re.Pattern[str], expected: int
) -> str | None:
    match = pattern.search(line)
    if not match:
        return None
    actual = int(match.group("count"))
    return None if actual == expected else f"{label}={actual}, expected {expected}"


def _line_issues(line: str, facts: CurrentFacts) -> list[str]:
    issues: list[str] = []
    version_patterns = (
        ("current-version", re.compile(r"\bcurrent\s*:\s*v(?P<version>\d+\.\d+\.\d+)", re.IGNORECASE)),
        (
            "current-inventory-version",
            re.compile(r"\bcurrent inventory\s*\(v(?P<version>\d+\.\d+\.\d+)\)", re.IGNORECASE),
        ),
    )
    for label, pattern in version_patterns:
        match = pattern.search(line)
        if match and match.group("version") != facts.version:
            issues.append(f"{label}=v{match.group('version')}, expected v{facts.version}")

    # "As of" is current-state only when its sentence declares the plugin/live
    # inventory. Historical capability dates such as "ships as of v3.13.0" are
    # narrative facts, not claims that the whole repository is still v3.13.0.
    as_of = re.search(r"\bAs of\s+(?:\*\*)?v(?P<version>\d+\.\d+\.\d+)(?:\*\*)?", line)
    as_of_current = re.search(
        r"\bplugin ships\b|\bit ships\b|\blive inventory\b|\blive total\b|"
        r"\bpytest self-tests\b",
        line,
        re.IGNORECASE,
    )
    if as_of and as_of_current and as_of.group("version") != facts.version:
        issues.append(f"as-of-version=v{as_of.group('version')}, expected v{facts.version}")

    count_patterns = (
        ("passing", re.compile(r"\b(?P<count>\d{2,6})\s+passing\b", re.IGNORECASE), facts.passing),
        ("pytest tests", re.compile(r"\b(?P<count>\d{2,6})\s+pytest\s+(?:self-)?tests\b", re.IGNORECASE), facts.passing),
        ("tests pass", re.compile(r"\b(?P<count>\d{2,6})\s+tests?\s+pass\b", re.IGNORECASE), facts.passing),
        ("tests heading", re.compile(r"\bTests\s*\((?P<count>\d{2,6})\s+PASS\b", re.IGNORECASE), facts.passing),
        ("test files", re.compile(r"\b(?P<count>\d{2,4})\s+test files\b", re.IGNORECASE), facts.test_files),
    )
    for label, pattern, expected in count_patterns:
        issue = _first_count_issue(line, label, pattern, expected)
        if issue:
            issues.append(issue)

    # Count inventory only in a clause explicitly presenting the current plugin
    # or live inventory; use the first count after that marker so older counts
    # later on the same long Markdown line remain historical context.
    context = re.search(
        r"\bcurrent inventory\b|\bplugin ships\b|\blive inventory\b|\bTests validate\b",
        line,
        re.IGNORECASE,
    )
    if context:
        segment = line[context.start() :]
        inventory_patterns = (
            ("skills", re.compile(r"\b(?P<count>\d+)\s+skills?\b", re.IGNORECASE), facts.skills),
            ("agents", re.compile(r"\b(?P<count>\d+)\s+(?:named\s+)?agents?\b", re.IGNORECASE), facts.agents),
            ("commands", re.compile(r"\b(?P<count>\d+)\s+(?:slash\s+)?commands?\b", re.IGNORECASE), facts.commands),
        )
        for label, pattern, expected in inventory_patterns:
            issue = _first_count_issue(segment, label, pattern, expected)
            if issue:
                issues.append(issue)
    return issues


def _record_line(
    *,
    path: str,
    number: int,
    line: str,
    history: dict[int, str],
    facts: CurrentFacts,
    findings: list[Finding],
    exemptions: list[Exemption],
) -> None:
    issues = _line_issues(line, facts)
    if not issues:
        return

    # CHANGELOG entries below the top entry are unconditionally historical.
    # Elsewhere, an explicit current marker outranks history/delta disposition.
    disposition: str | None = None
    if path == "CHANGELOG.md" and number in history:
        disposition = history[number]
    elif CURRENT_ASSERTION_OVERRIDE.search(line):
        disposition = None
    elif DELTA_COUNTS.search(line):
        disposition = "historical count delta (old -> new or old → new)"
    elif number in history:
        disposition = history[number]

    if disposition:
        for issue in issues:
            exemptions.append(
                Exemption(
                    path,
                    number,
                    "historical-current-fact",
                    disposition,
                    f"{issue}; {_excerpt(line)}",
                )
            )
        return
    findings.append(
        Finding(
            path,
            number,
            "stale-current-state-assertion",
            f"{'; '.join(issues)}; {_excerpt(line)}",
        )
    )


def scan() -> tuple[CurrentFacts, list[Finding], list[Exemption]]:
    docs = {path: _read_lines(path) for path in LIVING_DOCS}
    facts = derive_current_facts(docs["CHANGELOG.md"])
    findings = _version_surface_findings(facts, docs["README.md"])
    findings.extend(_header_blockquote_findings(facts, docs["docs/CODEBASE_MAP.md"]))
    exemptions: list[Exemption] = []
    for path, lines in docs.items():
        history = _history(path, lines, facts.version)
        for number, line in enumerate(lines, start=1):
            _record_line(
                path=path,
                number=number,
                line=line,
                history=history,
                facts=facts,
                findings=findings,
                exemptions=exemptions,
            )
    order = {path: index for index, path in enumerate(LIVING_DOCS)}
    findings.sort(key=lambda item: (order.get(item.path, 999), item.line, item.code))
    exemptions.sort(key=lambda item: (order.get(item.path, 999), item.line, item.excerpt))
    return facts, findings, exemptions


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        facts, findings, exemptions = scan()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print("DOCS CURRENT-STATE CHECK: ERROR")
        print(f"Unable to derive current facts: {exc}")
        return 2

    print(f"DOCS CURRENT-STATE CHECK: {'FAIL' if findings else 'PASS'}")
    print(f"Plugin version: {facts.version}")
    print(f"Marketplace version: {facts.marketplace_version}")
    print(
        f"Derived current suite: {facts.passing} passing + {facts.skipped} skipped "
        f"from CHANGELOG v{facts.suite_source_version}:{facts.suite_source_line}; "
        f"{facts.test_files} test files from disk count"
    )
    print(
        f"Derived inventory: {facts.skills} skills / {facts.agents} agents / "
        f"{facts.commands} commands"
    )
    print(f"Living docs scanned: {len(LIVING_DOCS)}")
    print(f"Violations: {len(findings)}")
    print()

    if findings:
        print("VIOLATIONS")
        for finding in findings:
            print(f"- {finding.path}:{finding.line} [{finding.code}] {finding.excerpt}")
        print()
        print("VIOLATION COUNTS BY FILE")
        ordered = list(LIVING_DOCS) + sorted(
            {finding.path for finding in findings if finding.path not in LIVING_DOCS}
        )
        for path in ordered:
            count = sum(finding.path == path for finding in findings)
            if count:
                print(f"- {path}: {count}")
    else:
        print("No stale current-state assertions found.")

    print()
    print(f"EXEMPTED HISTORICAL HITS ({len(exemptions)})")
    for exemption in exemptions:
        print(
            f"- {exemption.path}:{exemption.line} [{exemption.code}] "
            f"EXEMPT — {exemption.disposition}: {exemption.excerpt}"
        )
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
