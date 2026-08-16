# BRAIN.md — EvercoatITWRD APP

**What this file is.** `CLAUDE.md` holds the *rules*. `CONTEXT.md` holds the *state*. `MEMORY.md` holds *durable facts*. **BRAIN.md holds the reasoning** — the mental models, invariants and domain judgement needed to make correct decisions in situations no rule anticipated.

If a rule and this file appear to disagree, the rule wins and this file needs updating. If a *situation* is not covered by any rule, reason from here.

---

## 1. The one-sentence mental model

> **The application is a machine for converting laboratory work into defensible, traceable, reusable organizational knowledge — and every design decision is judged by whether it strengthens or weakens that chain of evidence.**

Everything else follows. When a design choice is unclear, ask: *does this preserve the evidence chain, or does it create an orphan?*

---

## 2. The four kinds of truth — never conflate them

This is the single most important distinction in the domain, and the most common source of serious defects.

| Kind | Produced by | Authority | UI treatment |
|---|---|---|---|
| **Measured** | A physical test on a physical sample | Highest. This is evidence | Primary, prominent |
| **Calculated** | Deterministic Python from known inputs (density, total %, batch mass, cost) | High, but derived — only as good as its inputs | Clearly labelled "calculated" |
| **Predicted** | A trained model (scikit-learn), with uncertainty | Advisory only. Never evidence | Visually separated, with confidence, never styled like a measurement |
| **Hypothesised** | A human or MSD proposing a cause or an idea | Zero authority until a human accepts it | Explicitly labelled as a hypothesis/suggestion |

**Test:** if a screenshot of your UI would let a Chemist mistake a prediction for a measurement, the UI is wrong. If a database query could return a predicted value where downstream code expects a measured one, the schema is wrong.

The permitted promotions are one-directional and always human-gated:
```
Hypothesised --(human review + approval)--> Accepted root cause
Predicted    --(physical test)-----------> Measured
Measured     --(multi-level approval)----> Confirmed / GREEN
```
There is no path that skips a step. Ever.

---

## 3. Why YELLOW exists — the concept most likely to be implemented wrongly

A naive implementation has two states: pass and fail. That implementation is *wrong for this domain* and will quietly destroy the value of the system.

YELLOW exists because **a number being inside a limit does not mean the organization may act on it.** All of the following are "the measurement passed" and yet none may proceed:

- the required reviewers have not approved yet
- only 3 of 5 required replicates exist
- the mean passed but the coefficient of variation is wild — the process is not in control
- the result is 6.1 against a 6.0 minimum — technically a pass, practically noise
- the equipment's calibration had expired
- specimen conditioning deviated from the method
- it was a *screening* test and screening is not qualification evidence
- everything is in spec but viscosity has climbed across five consecutive batches

**So: GREEN is not "the number was good." GREEN is "the number was good AND the organization has formally accepted it at the authority level this test claims."** That is why `calculated_result` and `approved_result` are separate columns and `display_color` is derived from both plus deviation state.

Corollary: a YELLOW with no stated reason is a defect, not a status. The user must always be able to see *why it is yellow* and *what happens next*. And because reports get printed and people have colour-vision limitations, status is always colour **plus** icon **plus** text.

---

## 4. Why formula versions are immutable

A formula version is not a record of what a formulation *is*. It is a record of **what was physically made and tested**. Batch LB004 consumed lot RM021-L240716 at exactly 3.00% because version F007 said 3.00%. If someone later edits F007 to 3.50%, then test ADH-T045's 5.3 MPa result now describes a formulation that never existed, and every downstream conclusion silently becomes a lie.

That is why: clone, never edit. `parent_version_id`, never overwrite. And why the FK rules are `RESTRICT` — deleting a formula version with batches attached does not "clean up data", it destroys the meaning of the test results that survive it.

The same reasoning extends to released master formulas being read-only *at the database level*: a UI-only lock is a lock against accidents, not against defects.

**Branches matter.** `F003 → F004-A / F004-B` is not an edge case; it is how chemists actually work — two competing hypotheses tested in parallel. A model that assumes a linear version chain will be wrong within the first real project.

---

## 5. What makes a failure investigation valuable

The failure module's worth is not that it records failures. It is that it records **why we thought what we thought, and whether we were right**.

The chain that must survive:
```
Failed test → evidence → competing hypotheses → accepted root cause
  → corrective action → new formula version → retest → observed effect
```

Two things make this pay off later:

1. **`observed_effect` on the revision.** Every version records the expected effect at creation. Recording the *observed* effect after testing is what converts a version history into knowledge. Without it you have a changelog; with it you have a body of evidence about which interventions actually work.
2. **Recommendation effectiveness.** "Increase adhesion promoter" → F008 → adhesion 5.3 → 7.1 MPa → tag the recommendation **Effective**. Over hundreds of cycles this is the dataset that makes MSD genuinely useful — and it is also the honest measure of whether the AI layer is earning its keep. Acceptance rate is an operational metric; *experimentally verified improvement* is the real one.

The UI puts Evidence before Root Cause in the submenu deliberately: the navigation itself should push people to look at facts before concluding.

---

## 6. How to think about MSD

MSD is **not** a chatbot bolted onto a database. It is a natural-language *view* over controlled data, subject to exactly the same authorization as every other view.

The governance model, which must never be shortcut:
```
MSD recommends → Chemist evaluates → Application calculates
  → Laboratory produces → Physical test verifies → Authorized personnel approve
```

Three failure modes to design against:

1. **The permission leak.** If retrieval happens first and filtering happens after generation, the model has already seen restricted data and can leak it through paraphrase. **Filter before retrieval, always.** This is a security test, not a code-review preference.
2. **The confident invention.** MSD must not name a material, formula or result that it did not retrieve. Every technical claim carries evidence links to source records. "I don't have evidence for that" is a correct and acceptable answer.
3. **The silent promotion.** A useful conclusion said in chat is not organizational knowledge. It becomes knowledge only when a human explicitly promotes it into a Technical Decision, Experiment Proposal, Recommendation, Failure Hypothesis, Corrective Action or Task. Otherwise informal speculation slowly contaminates the knowledge base and future retrieval trusts it.

MSD's authority ceiling: it may analyze, compare, detect patterns, summarize, retrieve and recommend. It may **not** approve a test, change a controlled formula, move a result from YELLOW to GREEN, confirm a root cause, or release a product.

---

## 7. Why the calculation engine is separate from everything else

`apps/api/app/calculations/` is pure functions: numbers in, numbers out. No database, no I/O, no LLM, no request context.

Three reasons:
- **Testability.** Hypothesis can assert invariants across the whole input space — e.g. *for any valid 100% formula and any positive batch quantity, the sum of component masses equals the batch mass within tolerance*. That catches cases no one would think to write by hand.
- **Trust.** Chemists must be able to believe the arithmetic. An LLM cannot be in this path, and neither can an ORM session.
- **Reuse.** The same density function serves the formula workspace, the batch scaler, the pilot scale-up comparison and the DOE run generator.

The LLM may **call** these functions as tools and **explain** their output. It must never produce the number itself.

---

## 8. Why scale-up is not multiplication

A 2 kg lab batch and a 500 kg production batch are not the same process at different sizes. RPM, tip speed, shear, mixing duration, vacuum, heat transfer and addition rates **do not scale linearly**, and the source is explicit that the system must not assume they do.

This is why lab-vs-pilot comparison is a first-class feature rather than a report: the *difference* between lab and pilot performance is the engineering signal. When pilot fails, the diagnostic question is always the same four-way split — process problem, formula problem, raw material problem, or scale effect? The data model must make each of those answerable.

---

## 9. Where the schedule pressure actually lands

The 14-day target survives only through **reuse**, and reuse only works if the shared layer is built *first and properly*. The expensive, irreducible work is concentrated in a small number of places:

- formula scientific calculations
- test analysis correctness
- multi-level workflow correctness
- the relational model itself
- DOE and statistical implementation
- product-model validation
- RBAC and security
- end-to-end integration

Everything else — a new list page, a new detail workspace, a new KPI group, a new approval route, a new discussion integration — should be *composition*, measured in tens of minutes, not new construction.

**The diagnostic:** if the Pilot module needs a new approval system, a new discussion component, a new file system or a new dashboard architecture, that is not new scope. It is a defect in Slices 1–3. Fix it in the shared layer.

---

## 10. Judgement calls — the standing answers

| Situation | Standing answer |
|---|---|
| Two source passes disagree | Later + more explicit + more detailed wins. Safety/security/data-integrity beats convenience. The MASTER PROMPT (end of `ITWRD App.txt`) is highest authority |
| Tempted to add a field to a "misc" or JSON blob | Don't. If it participates in the digital thread it needs a column and a relationship |
| Tempted to soft-delete with a `DELETE` | Never. Status transition to `inactive` / `obsolete` / `archived` |
| Unsure whether something needs audit | If a human decision or a controlled state changed, it needs audit |
| Unsure whether AI may do something | If it changes controlled state or expresses approval, no |
| A dashboard needs a big join | It needs an analytics view, and the view must still be RLS- and membership-scoped |
| A number needs storing | NUMERIC, with an explicit unit, in the canonical unit |
| A test seems to pass but something is off | YELLOW, with a stated reason |
| Feature "works" but you have not opened it in a browser | It is not done |
| CI is green and the deploy succeeded | Still not done. Run the full suite against the deployed site and report passed/failed/skipped |

---

## 11. Standing traps in this environment

Hard-won, from prior work on this machine. Re-reading these costs a minute and has repeatedly saved hours.

- **A green build is not a working feature.** Features have shipped that never once worked, under green gates. Build it, run it, *look at it*.
- **Local is superuser; production is not.** FORCE RLS blocks things that worked locally — dumps, joins, a migration's own backfill and its own orphan check. Test with `SET ROLE`.
- **Measure the repo; do not quote the last handover.** Status files have been wrong in both directions.
- **Two literals in two files cannot be type-checked into agreement.** Nav vs router, landing vs pack, workflow vs workflow. Generate or share the constant.
- **A directory listing is not a measurement.** Neither is a comment — a comment can be stale in either direction, claiming a safety net that does not exist or a gap that has been closed.
- **`curl … || echo 000` yields `000000`;** the command prints *and* exits non-zero. Use `x="$(cmd)" || x=""`. Under `set -e` an unguarded `$(curl)` aborts the whole step.
- **Piping to `tail` masks the exit code** and destroys the head of a review. Redirect to a file.
- **PowerShell pipes add a UTF-16 BOM to secrets.** Write secret files with explicit UTF-8.
- **`CREATE … IF NOT EXISTS` hides schema drift.** An existing table with the wrong shape passes silently.
- **Ask of every role: which production path *writes* it?** A role that can be read but never granted is a role that does not exist. This has caught five separate cases.
- **Neither reviewer alone is enough** — Codex misses what the Supervisor finds and vice versa. But reviewers are not oracles either: verify every finding against the source before acting on it.
