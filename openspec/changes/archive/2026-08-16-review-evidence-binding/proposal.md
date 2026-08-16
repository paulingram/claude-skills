# review-evidence-binding (v3.62.0)

## Why

A field report measured one defect in both directions on a live run:
`reviews/<id>.json` keyed by a reused small-integer task id. A manifest
pointed at "17" rode another lane's clean review to exit 0 (false pass —
unsound), and a task 20 was refused on a different lane's failing review
under the same id (false block — unusable). The reporter raised both as SRs
with a regression test required per polarity.

## What

Evidence binding via `task_subject` + variant filenames, enforced in the
gate's evidence selection; legacy unbound evidence keeps current behaviour
(the named migration boundary); writers updated to bind on write. Full
detail in the delta spec and CHANGELOG.
