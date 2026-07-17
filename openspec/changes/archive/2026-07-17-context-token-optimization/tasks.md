# Tasks — context-token-optimization

## 1. Census & findings (analysis lane — 3 parallel analysts, disjoint lenses)

- [x] 1.1 A1 cross-file duplication census: agents-boilerplate replication (sync_agent_boilerplate blocks ×39), skills-vs-common-pipeline-conventions restatements (with/without citation), commands-vs-skills wrapper duplication; per-candidate: file, byte extent, canonical home, citation-present flag, estimated saving (bytes/4)
- [x] 1.2 A2 always-loaded surface analysis: CLAUDE.md internal redundancy map (Recent-releases vs CHANGELOG diff, What-this-repo-is accretion), frontmatter-description census (per-class char totals, redundancy-only candidates), run `claude_md_efficiency.assess_claude_md` and record signals
- [x] 1.3 A3 cost model + verbosity ranking: load-frequency weighting (always/per-invoke/per-spawn), per-KB worst offenders, verbosity-without-instruction-value candidates (flagged only — implementation requires the P2 citation test), draft ranked findings table
- [x] 1.4 Lead merges A1-A3 into the ranked findings report at `.architect-team/findings/context-token-optimization/findings.json` + `.md`; each analyst confirms the merge preserves their verified findings; engine-reuse disposition recorded (D1)

## 2. Low-risk remediation (implementation lane — non-overlapping file scopes)

- [x] 2.1 I1 CLAUDE.md dedupe/trim per D3: Recent-releases bounded to 3 entries + CHANGELOG pointer; What-this-repo-is rewritten current-state; all other sections preserved current; before/after bytes recorded; schema-v7 review evidence written
- [x] 2.2 I2 P2 cited-canonical restatement trims across skills/commands/agents per D2's mechanical citation test (only blocks whose canonical section is already cited in the same file); per-file before/after bytes; doubtful candidates deferred to the higher-risk list; schema-v7 review evidence written
- [x] 2.3 Independent task-reviewer verdicts on 2.1 and 2.2 (producer ≠ checker; removed-text-vs-canonical diff check per R1)

## 3. Verification

- [x] 3.1 Full pytest suite green — same pass/skip totals as baseline (5542 + 4) or CHANGELOG-recorded delta; spot-check under PYTHONUTF8=1
- [x] 3.2 instruction-compliance assessment zero findings over the edited set
- [x] 3.3 Post-trim `assess_claude_md` signals recorded in findings (advisory)

## 4. Deferral list & close-out

- [x] 4.1 Higher-risk items enumerated with per-item estimated savings + remediation sketch (pointer-form CLAUDE.md / CPC restructure / description rewrites / boilerplate slimming / command-wrapper dedup) in findings + final report
- [x] 4.2 Version bump (plugin.json + marketplace.json) + CHANGELOG entry (with before/after byte table and any suite-total delta)
- [x] 4.3 Documentation-currency: doc-updater pass over affected inventory docs + independent doc-currency audit pass
- [x] 4.4 Master-review audit, completion audit, commit on architect-team/context-token-optimization, merge --no-ff to main, mark run complete
