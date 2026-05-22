---
name: dynamic-value-discovery
description: Use when authoring a spec or DESIGN_MAP from a mockup, when implementing any screen that renders values, or when reviewing shipped UI — a cross-role discipline for telling a genuine static literal (a fixed label) from sample data standing in for a dynamic, data-bound value. Classify every displayed value static vs. dynamic FROM CONTEXT (its position, its nature, the requirements/design language) — never from the literal itself, since the same string is static in one place and dynamic in another. Mandates that every dynamic value is bound to a named data source rather than shipped as the design's hardcoded sample, and requires escalation to the human when a classification is genuinely ambiguous. Rejects rationalizations like "the design says John Smith so I'll render John Smith."
---

# Dynamic-Value Discovery — Is This a Fixed Label, or Sample Data for a Value That Varies?

A design mockup is full of sample data. `"John Smith"`, `"$1,234.00"`, `"2 hours ago"`, `"#A4F92C"`, `"Welcome back, Sarah"`, `"3 items"`, `"Shipped"`. Every one of those strings is a concrete literal in the mockup — and a literal implementation that copies them into the code ships **one person's sample data to everyone**. The user named "Sarah" sees "Welcome back, Sarah" when they are not Sarah. The order detail page shows `"$1,234.00"` for every order. That is not a cosmetic gap; it is a feature that does not work.

Every displayed value is exactly one of two things:

- **`static`** — a genuine fixed literal. It is the *same* for every user, every record, every state of the app. A nav label, a button caption, a section heading, fixed instructional text, the brand name. The mockup's literal IS the shipped value.
- **`dynamic`** — sample data standing in for a value that *varies*: per user, per record, per state, per request. The mockup shows ONE sample (`"John Smith"`); the shipped UI must render whatever the real data is. The mockup's literal is a placeholder for a binding to a data source — it must NOT be the shipped value.

Dynamic-value discovery is the discipline of classifying every displayed value into one of those two buckets, deliberately, and binding every `dynamic` one. This skill makes that classification explicit and repeatable so the same value is treated the same way by the architect who specs it, the developer who builds it, and the evaluator who reviews it.

## The core rule: classify FROM CONTEXT, never from the literal

**The value alone never decides. The context decides.** The same string is `dynamic` in one place and `static` in another:

- `"Dashboard"` as the `<h1>` of the user's dashboard — `static` (the page is always called Dashboard). `"Dashboard"` as one row in a list of the user's saved report names — `dynamic` (it is one record's title; the next row is a different name).
- `"$0.00"` as the label on a "Free" pricing-tier card — `static`. `"$0.00"` as an account's current balance — `dynamic`.
- `"Active"` printed in fixed helper text "Only Active members can post" — `static`. `"Active"` rendered as a status badge on a member row — `dynamic`.
- `"Settings"` as a nav-menu item — `static`. `"Settings"` as the name a user gave one of their projects — `dynamic`.
- A person's name in the page chrome next to the signed-in user's avatar — `dynamic` (it is the logged-in user). The literal company name in the footer — `static`.

If you classify by looking at the string, you will be wrong half the time. You classify by asking three context questions:

1. **Position** — where does this value sit? Inside page chrome / navigation / a fixed heading / static helper copy? Or inside a record-detail view, a repeating list/table row, a card bound to one entity, a greeting line, a metric tile?
2. **Nature** — what *kind* of value is it? A name, an amount, a date, a count, a status, an ID — values whose whole purpose is to differ per record? Or a label / caption / instruction whose purpose is to stay the same?
3. **Requirements / design language** — what do the spec and the design say? "Show the user's name", "list the user's orders", "display the order total" describe dynamic, data-bound values. "A "Save" button", "the page header reads Reports" describe static literals. The design's annotations, the data model, and the requirements text are the authority — read them.

A value is `dynamic` when the answers point to "this varies." It is `static` when they point to "this is fixed." When they genuinely conflict or are silent — **escalate** (see below). Do not let the convenience of the mockup literal make the decision for you.

## The dynamic-signal rubric

Treat a value as `dynamic` — sample data standing in for a binding — when ANY of these signals is present. None of these is decided by the literal; each is decided by the value's role:

- **Person names, usernames, display names, emails, avatars/initials** — a name beside the signed-in user's avatar, an author byline, a "created by" / "assigned to" field, a participant in a list. Almost always the user's or a record's identity.
- **Dates, times, timestamps, and relative time** — `"May 21, 2026"`, `"2 hours ago"`, `"Last updated …"`, `"Expires in 3 days"`. A timestamp is per-record by definition.
- **Currency amounts, quantities, counts, percentages, metrics** — `"$1,234.00"`, `"3 items"`, `"87%"`, `"12 unread"`, a balance, a total, a score, a progress figure, a badge count.
- **Statuses, states, badges, labels-on-a-record** — `"Active"`, `"Pending"`, `"Shipped"`, `"Draft"`, a tier name, a role — rendered ON an entity (as opposed to in fixed copy). The badge text varies with the record's state.
- **IDs, slugs, reference numbers, URLs, file names** — `"#INV-0042"`, an order number, a record permalink, an uploaded file's name, a share link.
- **A greeting or any sentence containing an interpolated value** — `"Welcome back, Sarah"`, `"You have 3 new messages"`, `"Hi {name}"`. The sentence frame may be static; the embedded name/count is dynamic. Split it.
- **Any value inside a record / entity detail view** — a screen that shows ONE thing (an order, a profile, a project, an invoice): its title, description, every field, every attribute. The screen exists to display that record's data.
- **Any value inside a repeating list, table row, grid card, or feed item** — if it renders once per item, the per-item values are dynamic. The mockup shows three sample rows; production shows N real rows.
- **User-authored or user-uploaded content** — anything a user typed, wrote, named, picked, or uploaded: comments, descriptions, titles, notes, posts, bios, uploaded images.
- **Anything the requirements/design describe with a data verb** — "show", "list", "display the user's …", "fetch", "render each …", a field annotated with a data binding or a source name in the design.

## The static-signal rubric

Treat a value as `static` — a genuine fixed literal, the mockup string IS the shipped value — when it is one of these AND no dynamic signal overrides it:

- **Navigation labels** — menu items, tab names, breadcrumb roots, sidebar links ("Home", "Settings", "Reports").
- **Button and action text** — "Save", "Cancel", "Add item", "Sign out", "Download". (The button's *label* is static; what it acts on may be dynamic — that is a different concern.)
- **Section headings and fixed page titles** — the `<h1>`/`<h2>` that names a screen or a section and never changes ("Account settings", "Recent activity").
- **Fixed helper, instructional, placeholder, and empty-state text** — "Choose a file to upload", "No results found", form field hints, tooltip copy that is the same for everyone.
- **Brand strings** — the product name, the company name, a tagline, a copyright/legal line in the footer.
- **Legal / boilerplate text** — terms snippets, disclaimers, fixed compliance copy.

A static signal is *overridden* by a dynamic signal in the same value. "Settings" is normally a nav label (static) — but "Settings" as the name a user gave a project is dynamic. Always check: is this string in a fixed-chrome position, or is it bound to a user/record/state? Position and nature win over the category default.

## The rule: every `dynamic` value is bound to a named data source

A value classified `dynamic` MUST be wired to a **named data source** — never shipped as the design's hardcoded sample literal. "Named" means you can state, concretely, where the value comes from:

- the authenticated session / current-user object (`session.user.name`, `currentUser.email`),
- an API response field (`GET /orders/:id` → `order.total`),
- a route or query parameter, a store/context value, a derived computation over other dynamic values (an item count derived from a fetched list),
- a prop passed from a parent that is itself bound to one of the above.

"It comes from the backend somehow" is not a named source. "`order.total` from the `GET /orders/:id` response" is. If a `dynamic` value cannot be traced to a named source, that is itself the gap to report or the question to escalate — the binding does not exist yet.

A `dynamic` value that ships as the mockup's literal is a **`hardcoded-dynamic-value`** defect: the UI shows sample data to every user instead of the real, varying value. It is caught and reported exactly like a broken control — see the cross-role wiring below.

## Escalate, don't guess — when the classification is genuinely ambiguous

Sometimes the position, the nature, and the requirements/design language do not settle whether a value is `static` or `dynamic`. The design shows `"Acme Corp"` in a header and the spec never says whether the app is single-tenant (one fixed company — `static`) or multi-tenant (the value is the current tenant's name — `dynamic`). The mockup shows a `"50% off"` banner and nothing says whether the discount is a fixed promo or a per-user offer.

**Do not default-guess.** A wrong guess ships either a hardcoded value that should vary, or a needless data binding to a fetch that does not exist. Instead, escalate a *structured* question to the human:

```
For the value "<literal>" shown at <where — screen / component / position>, I cannot
determine from the requirements / design / code whether it is:
  - static — a fixed literal, the same for every user/record/state; or
  - dynamic — sample data for a value that varies (per <user / record / state>),
    which must be bound to a data source.
Evidence for static: <…>.  Evidence for dynamic: <…>.
If dynamic, what is the data source?
```

Asking costs minutes. Shipping the wrong classification ships a broken screen. An ambiguous value is a valid, expected outcome of this discipline — not a failure of the person applying it.

## A cross-role discipline — applied at planning, implementation, and review

A hardcoded value that should be dynamic cannot be caught by one gate at one moment. It has to be **prevented at planning**, **avoided at implementation**, and **caught at review**. So this is a discipline every role consults — the same shape as `reuse-first-design`:

- **Architect (planning).** When the `system-architect` and the `design-fidelity-mapping` skill turn a mockup into a spec and a DESIGN_MAP, classify every per-screen value `static` or `dynamic` using the rubrics above, and **name the data source** for each `dynamic` value in the DESIGN_MAP. The Phase 1 spec's acceptance criteria then *require* those bindings — so "render the user's name from the session", not "render John Smith", is in the spec from the start.
- **Developer (implementation).** When the `frontend` and `backend` agents build a screen, apply this skill to every value they render: bind every `dynamic` value to its named data source; ship only genuine `static` literals as literals. Never copy a mockup's sample datum (`"John Smith"`, `"$1,234.00"`, `"2 hours ago"`) into the code as the shipped value.
- **Evaluator (review).** The `interaction-reviewer` agent, guided by this skill and the `interaction-completeness` skill, independently re-classifies the displayed values of the shipped UI. A hardcoded value the context shows should be `dynamic` is reported as a **`hardcoded-dynamic-value`** gap — routed as a solution requirement and surfaced through the `ui_interaction_review` review-gate field, exactly like an `unwired-control` or a `placeholder-page` gap.

The wiring into each specific agent and skill is done elsewhere; this skill is the single shared definition all three roles classify against, so the architect, the developer, and the evaluator reach the *same* verdict for the *same* value.

## Anti-pattern rationalizations to reject

| Rationalization | Rebuttal |
|---|---|
| "The design says `John Smith`, so I'll render `John Smith`." | A mockup shows sample data. `John Smith` next to the signed-in user's avatar is the *logged-in user's* name — a `dynamic` value. The mockup's literal is a placeholder, not the spec. Bind it. |
| "It's just a placeholder amount, it's fine for now." | A balance, a total, or a price hardcoded to the mockup figure is wrong for every user but one. "For now" hardcoded values ship and stay. If it varies, bind it now. |
| "It looks like a label, so it's static." | You classified by appearance. `"Active"` looks like a label but as a status badge on a record it is `dynamic`. Classify by position and nature, not by how the string looks. |
| "The string is the same in all three mockup rows, so it's static." | The mockup has three *sample* rows. Identical sample values across sample rows say nothing — production has N real rows with N real values. A per-row value is `dynamic` regardless of what the samples happen to show. |
| "There's no API for it yet, so I'll hardcode it and wire it later." | A `dynamic` value with no data source is a real gap — report it or escalate it. Hardcoding it hides the gap behind a screen that looks done. "Wire it later" rarely happens. |
| "It's a greeting, the whole line is fixed copy." | `"Welcome back, Sarah"` is a static frame (`"Welcome back, "`) plus a `dynamic` name. Split it and bind the name. Shipping the whole line static greets everyone as Sarah. |
| "I'm not sure if it's per-user, so I'll just hardcode the design value." | Uncertainty is the trigger to **escalate**, not to guess. A wrong guess ships a broken screen. Ask the structured question. |
| "It's a count / date / status — those are obviously dynamic, no need to be deliberate." | Obvious-looking values are exactly the ones quietly shipped as the mockup literal because nobody stopped to bind them. Deliberateness is cheap; a hardcoded `"3 items"` is a bug. |
| "The architect's spec didn't mention a data source, so it must be static." | A spec silent on a value is an `ambiguous` value, not a `static` one. Escalate to confirm — silence is not a classification. |

## Hard rules (non-negotiable)

- **Every displayed value is classified `static` or `dynamic`** — deliberately, before it ships. An unclassified value is an unfinished value.
- **Classify FROM CONTEXT — position, nature, requirements/design language — never from the literal.** The same string is `static` in one place and `dynamic` in another. A classification justified by the value alone is invalid.
- **Every `dynamic` value MUST be bound to a named data source.** It must not be shipped as the design's hardcoded sample literal. A `dynamic` value rendered as the mockup datum is a `hardcoded-dynamic-value` defect.
- **A `dynamic` value with no traceable data source is a gap** — report it or escalate it. Hardcoding it to make the screen look done is forbidden.
- **An ambiguous classification escalates to the human** with a structured question. Never default-guess `static` (or `dynamic`) under time pressure.
- **The discipline applies at all three roles** — the architect classifies and names the source at planning, the developer binds at implementation, the evaluator re-classifies and flags `hardcoded-dynamic-value` gaps at review. One role applying it is not enough.
