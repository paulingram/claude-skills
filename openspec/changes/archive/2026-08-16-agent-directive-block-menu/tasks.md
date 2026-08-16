# Tasks — agent-directive-block-menu

Harness ids in parentheses; both closed with evidence before this file was
committed.

- [x] M1 (#21) agent-directive rewrite: 10 red-first pins (no-relay, --root
      injection, finished-first measured INSIDE the procedure, act-yourself,
      only-user-facing-case), both call sites thread root explicitly with a
      source pin, witnesses W1/W2/W5 caught after the W5 pin-and-mutation
      correction.
- [x] M2 (#22) terse-on-repeat: full at count<2, terse at count>=2 keeping
      the no-relay rule + the qualified exit; `_lock_consecutive` unit-tested
      (absent->0, other-session->0); end-to-end three-Stop run proves the
      feed (full on first, terse on third, blocking throughout); witnesses
      W3 (threshold) + W4 (severed feed) caught.
- [x] Release: bump 3.61.2, docs + map notes, archive-first, measure LAST,
      artifact committed, gate exit 0, merge, publish, verify installed.
