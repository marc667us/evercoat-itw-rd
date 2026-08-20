"""MSD — the Material Science & Development Assistant conductor.

🔴 THIS COMPOSES AN ANSWER FROM TOOL RESULTS. IT DOES NOT GENERATE ONE.

Every sentence MSD returns is built here, from values a tool read out of
PostgreSQL on the caller's own RLS-scoped session. The language model —
when one is configured at all — is handed the finished text and may only
reword it (`app/agents/ports.py`).

That is what makes the evidence list honest. `ai.msd_evidence` records
which records an answer was built from, and
`verify_evidence_within_boundary` can later prove every one of them was
readable by the asker. Neither check means anything if the prose was
free-generated: you can prove which rows were RETRIEVED, but nothing can
prove a generated sentence was entailed by them.

It also means MSD degrades honestly. With no model present the answers
are plainer and identical in content — which is the configuration CI runs
in, the configuration the deployed site would run in, and the one the
zero-cost rule (§7: no essential dependency on a paid AI API) requires be
sufficient.

🔴 SPECIALISTS NEVER CALL OTHER AGENTS (§0.2).

This conductor calls TOOLS. It does not call another conductor and it is
not called by a route — `root_orchestrator` is the only caller, and
`tests/test_agent_topology.py` enforces both directions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.agents.ports import LanguageModelPort, NullLanguageModel
from app.agents.tools import (
    compare_formulas,
    explain_the_application,
    find_records,
    formula_figures,
    formulas_containing,
    material_safety,
    pending_work,
)
from app.domains.msd.retrieval import RetrievedRecord

__all__ = ["DISCLAIMER", "MsdAnswer", "answer"]

#: §7, verbatim. The database REFUSES an assistant turn without a
#: disclaimer (`msd_turns_assistant_is_labelled`), so this is not a
#: convention that can lapse — an unlabelled answer cannot be stored.
DISCLAIMER = "AI-generated recommendation — requires technical review."

Intent = Literal[
    "compare_formulas",
    "guidance",
    "pending_work",
    "material_safety",
    "formula_figures",
    "find_records",
    "unsupported",
]


@dataclass(frozen=True, slots=True)
class MsdAnswer:
    """What MSD says, and everything needed to audit why it said it."""

    body: str
    intent: Intent
    disclaimer: str = DISCLAIMER
    evidence: tuple[RetrievedRecord, ...] = ()
    #: Recorded into `ai.msd_turns.tool_calls`, so a turn can be replayed
    #: and questioned. Which tools ran is part of the answer's provenance.
    tool_calls: tuple[dict[str, Any], ...] = ()
    #: Where in the product to go next, when the answer has a destination.
    href: str | None = None
    suggestions: tuple[str, ...] = field(default_factory=tuple)


#: Concept Note §33's suggested actions, offered when MSD cannot help.
_SUGGESTIONS: tuple[str, ...] = (
    "What is waiting for me?",
    "What does yellow mean on a test?",
    "Show me the batches on the bench",
    "How do I create a formula revision?",
)


def classify(question: str) -> Intent:
    """Which capability this question needs.

    🔴 DETERMINISTIC, AND NOT A MODEL'S JOB.

    Routing by a model would make the same question reach different
    capabilities on different days, and there is no version of that which
    is debuggable. It also puts a model on the path of a question that
    might need no model at all.

    Ordered deliberately: an application-guidance question like "what
    does yellow mean" must NOT fall through to record retrieval, where
    "yellow" would be matched against formula names and return confident
    nonsense.
    """
    lowered = question.lower().strip()
    if not lowered:
        return "unsupported"

    # Guidance first — it is the only intent with written answers, and a
    # written answer always beats a search.
    if explain_the_application(lowered) is not None:
        return "guidance"

    if any(
        phrase in lowered
        for phrase in (
            "waiting for me",
            "my work",
            "assigned to me",
            "my tasks",
            "my queue",
            "waiting on me",
            "my approval",
            "awaiting my",
        )
    ):
        return "pending_work"

    # Comparison is checked before the single-formula equations: "compare
    # F018 and F023 on density" names a property, and answering it with
    # ONE formula's density would be a confident non-answer to the
    # question actually asked (Concept Note §9).
    if any(
        word in lowered
        for word in ("compare", "comparison", "versus", " vs ", "difference between")
    ):
        return "compare_formulas"

    # 🔴 SAFETY BEFORE SEARCH. Concept Note §11's questions -- "which
    # components in this formula are restricted?", "are any material
    # safety documents missing?" -- all contain search words, so a
    # generic record search swallows them and answers a SAFETY question
    # with a list of names carrying no safety state at all.
    if any(
        word in lowered
        for word in (
            "sds",
            "safety",
            "hazard",
            "restricted",
            "coshh",
            "contain",
            "contains",
            "used in",
        )
    ):
        return "material_safety"

    # The equations (§17, rule 2). Same reasoning: "what is the density of
    # FRM-014" has no search intent worth honouring, and answering it with
    # a list of matching formulas is a non-answer.
    if any(
        word in lowered
        for word in (
            "density",
            "solids",
            "voc",
            "binder",
            "filler ratio",
            "total percentage",
            "cost per kg",
            "figures",
            "calculate",
        )
    ):
        return "formula_figures"

    if any(
        word in lowered
        for word in ("show", "find", "which", "list", "search", "formula", "material", "batch")
    ):
        return "find_records"

    return "unsupported"


def answer(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role_codes: frozenset[str],
    question: str,
    project_id: uuid.UUID | None = None,
    permissions: frozenset[str] = frozenset(),
    model: LanguageModelPort | None = None,
) -> MsdAnswer:
    """Answer one question, inside the caller's boundary.

    `session` MUST be the caller's own RLS-scoped session — every tool
    that touches records depends on that, and none of them re-checks
    permissions in Python.
    """
    model = model or NullLanguageModel()
    intent = classify(question)

    if intent == "guidance":
        entry = explain_the_application(question)
        assert entry is not None  # noqa: S101 - classify() just proved it
        return MsdAnswer(
            body=model.rephrase(composed=entry.body, question=question),
            intent=intent,
            href=entry.href,
            tool_calls=({"tool": "explain_the_application", "topic": entry.topic},),
        )

    if intent == "pending_work":
        tasks = pending_work(
            session,
            organization_id=organization_id,
            user_id=user_id,
            role_codes=role_codes,
        )
        composed = _compose_work(tasks)
        return MsdAnswer(
            body=model.rephrase(composed=composed, question=question),
            intent=intent,
            href="/my-work",
            tool_calls=({"tool": "pending_work", "returned": len(tasks)},),
        )

    if intent == "material_safety":
        subject = _subject_of(question)
        # "Which formulas contain RM-104?" is a USAGE question wearing a
        # safety hat, and it is the one asked when a material is
        # restricted or a supplier recalls a lot. It needs the component
        # join: the record search would have looked for "RM-104" in
        # formula NAMES, found nothing, and said so confidently.
        if any(w in question.lower() for w in ("contain", "contains", "used in")):
            usage = formulas_containing(
                session, organization_id=organization_id, material_query=subject
            )
            return MsdAnswer(
                body=model.rephrase(composed=_compose_usage(subject, usage), question=question),
                intent=intent,
                href="/formulations",
                tool_calls=({"tool": "formulas_containing", "returned": len(usage)},),
            )

        materials = material_safety(session, organization_id=organization_id, query=subject)
        return MsdAnswer(
            body=model.rephrase(composed=_compose_safety(materials), question=question),
            intent=intent,
            href="/materials",
            tool_calls=({"tool": "material_safety", "returned": len(materials)},),
        )

    if intent == "compare_formulas":
        # Two records, resolved SEPARATELY. Searching the whole sentence
        # would look for "compare FRM-014 and FRM-021" as one string and
        # match nothing at all.
        targets = _resolve_versions(
            session,
            organization_id=organization_id,
            question=question,
            project_id=project_id,
        )
        if len(targets) < 2:
            return MsdAnswer(
                body=(
                    "I need two formula versions you have access to, named by "
                    "their codes - for example 'compare FRM-014 and FRM-021'. "
                    f"I could resolve {len(targets)}."
                ),
                intent=intent,
                evidence=tuple(targets),
                tool_calls=({"tool": "find_records", "resolved": len(targets)},),
            )

        left, right = targets[0], targets[1]
        diff = compare_formulas(
            session,
            organization_id=organization_id,
            left_version_id=left.entity_id,
            right_version_id=right.entity_id,
            include_cost="formula.view_cost" in permissions,
        )
        return MsdAnswer(
            body=model.rephrase(
                composed=_compose_comparison(left.label, right.label, diff),
                question=question,
            ),
            intent=intent,
            evidence=(left, right),
            href="/formulations",
            tool_calls=(
                {
                    "tool": "compare_formulas",
                    "left": str(left.entity_id),
                    "right": str(right.entity_id),
                },
            ),
        )

    if intent == "formula_figures":
        # Resolve the formula the question names, through the SAME
        # boundary-enforcing retrieval every other record answer uses.
        found = find_records(
            session,
            organization_id=organization_id,
            question=_subject_of(question),
            project_id=project_id,
            entity_types=("formula_version",),
        )
        if not found:
            return MsdAnswer(
                body=(
                    "I could not find a formula version you have access to matching "
                    "that. Name it by its code, for example FRM-014."
                ),
                intent=intent,
                tool_calls=({"tool": "find_records", "returned": 0},),
            )
        target = found[0]
        evaluation = formula_figures(
            session,
            organization_id=organization_id,
            version_id=target.entity_id,
            # 🔴 The caller's own permission. Asking MSD is not a way
            # around `formula.view_cost` (§7).
            include_cost="formula.view_cost" in permissions,
        )
        return MsdAnswer(
            body=model.rephrase(
                composed=_compose_figures(target.label, evaluation), question=question
            ),
            intent=intent,
            evidence=(target,),
            tool_calls=({"tool": "formula_figures", "version": str(target.entity_id)},),
        )

    if intent == "find_records":
        records = find_records(
            session,
            organization_id=organization_id,
            question=question,
            project_id=project_id,
        )
        composed = _compose_records(records)
        return MsdAnswer(
            body=model.rephrase(composed=composed, question=question),
            intent=intent,
            evidence=tuple(records),
            tool_calls=({"tool": "find_records", "returned": len(records)},),
        )

    return MsdAnswer(
        body=(
            "I cannot answer that yet. In this version I can explain how the "
            "application works, tell you what is waiting for you, and find "
            "controlled records you have access to."
        ),
        intent="unsupported",
        suggestions=_SUGGESTIONS,
    )


def _compose_work(tasks: list[dict[str, Any]]) -> str:
    """The inbox, in sentences. Overdue named first because it is."""
    if not tasks:
        # NOT "you are all caught up". This screen's own lesson: an empty
        # result and a failed one must not read the same, and an assistant
        # that congratulates you on an empty list it could not fill is the
        # worst version of that.
        return "Nothing is currently assigned to you or waiting on your role."

    overdue = [t for t in tasks if t.get("is_overdue")]
    lines = [f"You have {len(tasks)} item{'s' if len(tasks) != 1 else ''} needing action."]
    if overdue:
        lines.append(f"{len(overdue)} of them {'is' if len(overdue) == 1 else 'are'} overdue.")
    for task in tasks[:5]:
        where = f" ({task['project_code']})" if task.get("project_code") else ""
        due = f", due {task['due_date']}" if task.get("due_date") else ""
        lines.append(f"· {task['title']}{where} — {task['status']}{due}")
    if len(tasks) > 5:
        lines.append(f"…and {len(tasks) - 5} more on My Work.")
    return "\n".join(lines)


def _compose_records(records: list[RetrievedRecord]) -> str:
    """What was found, grouped by kind, with nothing inferred.

    🔴 THE EMPTY CASE IS A SENTENCE ABOUT THE SEARCH, NOT ABOUT THE WORLD.

    "There are no formulas matching that" is a claim MSD cannot make: the
    caller's boundary may simply exclude them, and saying nothing exists
    would disclose the shape of what does. "I found nothing you have
    access to" is both true and non-disclosing.
    """
    if not records:
        return (
            "I found no records you have access to that match that. If you expect "
            "something here, you may not be a member of the project it belongs to."
        )

    by_type: dict[str, list[RetrievedRecord]] = {}
    for record in records:
        by_type.setdefault(record.entity_type, []).append(record)

    lines = [f"I found {len(records)} record{'s' if len(records) != 1 else ''} you can open."]
    for entity_type, group in by_type.items():
        lines.append(f"{entity_type.replace('_', ' ')} ({len(group)}):")
        lines.extend(f"· {r.label}" for r in group[:5])
    return "\n".join(lines)


def _subject_of(question: str) -> str:
    """The thing being asked about, with the question words removed.

    Crude on purpose, and bounded: it strips a small set of interrogative
    and filler words so "what is the density of FRM-014" searches for
    "FRM-014" rather than for the whole sentence. It is not parsing and
    does not pretend to be — a question it cannot reduce simply searches
    for more words and finds less, which fails toward "I found nothing"
    rather than toward a confident wrong record.
    """
    noise = {
        "what",
        "whats",
        "what's",
        "is",
        "are",
        "the",
        "of",
        "for",
        "in",
        "on",
        "show",
        "me",
        "find",
        "which",
        "list",
        "search",
        "tell",
        "about",
        "a",
        "an",
        "any",
        "does",
        "do",
        "have",
        "has",
        "this",
        "that",
        "current",
        "sds",
        "safety",
        "data",
        "sheet",
        "hazard",
        "restricted",
        "density",
        "solids",
        "voc",
        "binder",
        "filler",
        "ratio",
        "total",
        "percentage",
        "cost",
        "per",
        "kg",
        "figures",
        "calculate",
        "components",
        "missing",
        "documents",
        "formula",
        "formulas",
    }
    words = [w for w in question.lower().replace("?", " ").split() if w not in noise]
    return " ".join(words).strip() or question.strip()


def _compose_safety(materials: list[dict[str, Any]]) -> str:
    """Safety-record STATE, never a hazard assessment.

    🔴 THE LAST LINE IS NOT BOILERPLATE.

    Concept Note §11: *"MSD should not replace formal Compliance/QA
    review. Safety and regulatory decisions should remain controlled
    through the appropriate Compliance or Quality workflow."* A chemist
    who asks an assistant whether a material is safe and receives a
    confident sentence has been handed a regulatory opinion by a text
    generator. So every safety answer says what is ON FILE and says who
    decides.

    A MISSING safety data sheet is reported first and plainly, because it
    is the one fact here that is actionable — and because §8 makes it a
    hard block on submission that cannot be waived.
    """
    if not materials:
        return (
            "I found no materials you have access to matching that. Name the "
            "material by its code, for example RM-104."
        )

    lines: list[str] = []
    for m in materials:
        parts = [f"{m['material_code']} — {m['name']}"]
        parts.append(f"status: {m['status']}")
        if m["status"] == "restricted" and m.get("restriction_reason"):
            parts.append(f"restriction on file: {m['restriction_reason']}")
        if m["requires_sds"] and (m["sds_count"] or 0) == 0:
            # Named as an absence, not softened.
            parts.append(
                "SAFETY DATA SHEET REQUIRED AND NONE IS ON FILE — this blocks "
                "submission of any formula containing it"
            )
        elif (m["sds_count"] or 0) > 0:
            issued = m.get("sds_issued_on")
            parts.append(f"SDS on file{f' (issued {issued})' if issued else ''}")
        else:
            parts.append("no SDS required for this material")
        if m.get("hazard_summary"):
            parts.append(f"hazard summary on file: {m['hazard_summary']}")
        lines.append("· " + "; ".join(parts))

    lines.append("")
    lines.append(
        "This is the safety information RECORDED against these materials. It is "
        "not a compliance determination — hazard and regulatory decisions stay "
        "with Compliance/QA."
    )
    return "\n".join(lines)


def _compose_figures(label: str, evaluation: dict[str, Any]) -> str:
    """The engine's numbers, carried through without arithmetic.

    🔴 A PROPERTY IS A VALUE **OR A STATED REASON**, NEVER A BLANK.

    `evaluate_version` returns `{"value": ..., "unavailable_reason": ...}`
    per property precisely so "density unknown for: RM-FIL-07" reaches the
    reader. Rendering that as an empty cell — or omitting the line — would
    tell a chemist the density was calculated and came out empty, which is
    the "absence presenting as a value" failure this codebase keeps
    finding.

    Nothing here rounds, converts or recomputes. Rule 2 gives the
    arithmetic to `app/calculations/`, and this function is the
    "explain" half of *"the engine calculates; MSD interprets"*.
    """
    version = evaluation.get("version") or {}
    header = f"{label} — {evaluation.get('component_count', 0)} component(s)."
    lines = [header]

    readable = {
        "total_percentage": "Total percentage",
        "theoretical_density_g_cm3": "Theoretical density (g/cm³)",
        "binder_to_filler_ratio": "Binder to filler",
        "solids_content_pct": "Solids content (%)",
        "voc_content_g_per_l": "VOC content (g/L)",
        "raw_material_cost_per_kg": "Raw material cost (per kg)",
    }
    for key, name in readable.items():
        prop = evaluation.get("properties", {}).get(key)
        if prop is None:
            # ABSENT, not null. `raw_material_cost_per_kg` is absent when
            # the caller lacks `formula.view_cost`, and saying "cost: not
            # available" would imply no cost data exists.
            continue
        if prop.get("value") is not None:
            lines.append(f"· {name}: {prop['value']}")
        else:
            lines.append(f"· {name}: NOT CALCULATED — {prop['unavailable_reason']}")

    blocks = evaluation.get("submission_blocks") or []
    if blocks:
        lines.append("")
        lines.append(f"{len(blocks)} thing(s) currently block submission:")
        lines.extend(f"· {b['message']}" for b in blocks)
    elif evaluation.get("submittable"):
        lines.append("")
        lines.append(
            "Nothing currently blocks submission. That is a check on the "
            "recorded composition, not an approval — approval is a human "
            "decision recorded against the version."
        )

    if version.get("status"):
        lines.append("")
        lines.append(f"Version status: {version['status']}.")
    return "\n".join(lines)


def _compose_usage(subject: str, usage: list[dict[str, Any]]) -> str:
    """Where a material is used, for the question asked when it matters.

    🔴 THE EMPTY ANSWER IS THE CAREFUL ONE.

    "Nothing uses RM-104" is the sentence somebody acts on when a lot is
    recalled, and MSD cannot know it: a formula in a project the asker is
    not a member of is not returned here at all. So the empty case says
    what was actually established — nothing THEY can see — and names the
    reason, exactly as `_compose_records` does.
    """
    if not usage:
        return (
            f"I found no formula versions you have access to that use "
            f"'{subject}'. That is not the same as none existing: a formula in "
            "a project you are not a member of would not appear here. For a "
            "recall or a restriction, ask Compliance/QA to run it across every "
            "project."
        )

    by_formula: dict[str, list[dict[str, Any]]] = {}
    for row in usage:
        by_formula.setdefault(f"{row['formula_code']} — {row['formula_name']}", []).append(row)

    lines = [
        f"'{subject}' appears in {len(by_formula)} formula"
        f"{'s' if len(by_formula) != 1 else ''} you can open "
        f"({len(usage)} version{'s' if len(usage) != 1 else ''}):"
    ]
    for formula, rows in by_formula.items():
        lines.append(f"· {formula}")
        for row in rows[:5]:
            lines.append(
                f"    {row['version_code']} ({row['version_status']}) — "
                f"{row['material_code']} at {row['percentage']}%"
            )
    lines.append("")
    lines.append(
        "Percentages are as recorded on each version. This is a usage lookup, "
        "not a compliance determination."
    )
    return "\n".join(lines)


def _resolve_versions(
    session: Session,
    *,
    organization_id: uuid.UUID,
    question: str,
    project_id: uuid.UUID | None,
) -> list[RetrievedRecord]:
    """The formula versions a comparison question names, in the order named.

    EACH CODE IS SEARCHED SEPARATELY, AND ONLY TOKENS THAT LOOK LIKE CODES
    ARE SEARCHED.

    `retrieve_for_question` does one ILIKE over the whole string, so
    "compare FRM-014 and FRM-021" matches nothing - the sentence is not a
    formula name. Splitting on codes is what makes the question
    answerable at all.

    A token counts as a code only if it contains a digit. Crude and
    deliberately so: "compare", "and" and "density" contain none, and a
    token that is not a code searches for nothing rather than resolving to
    a confidently wrong formula.

    Order is preserved, because "compare A and B" is not the same question
    as "compare B and A": the second is the revision, and `change_reason`
    reads backwards if they are swapped.
    """
    seen: set[uuid.UUID] = set()
    ordered: list[RetrievedRecord] = []
    for token in question.replace(",", " ").split():
        cleaned = token.strip("?.;:()").strip('"').strip("'")
        if not any(character.isdigit() for character in cleaned):
            continue
        found = find_records(
            session,
            organization_id=organization_id,
            question=cleaned,
            project_id=project_id,
            entity_types=("formula_version",),
        )
        for record in found:
            if record.entity_id not in seen:
                seen.add(record.entity_id)
                ordered.append(record)
                break
    return ordered


def _compose_comparison(left_label: str, right_label: str, diff: dict[str, Any]) -> str:
    """Concept Note section 9's comparison, without computing one number.

    PERCENTAGES ARE SHOWN AS A PAIR, NEVER AS A DELTA.

    `compare_versions` deliberately returns `previous_percentage` and
    `new_percentage` rather than their difference, and says why: "The
    percentage-point delta on a component is a SUBTRACTION OF TWO
    PERCENTAGES and is therefore arithmetic -- so it is not done here."
    Two such conversions were already caught inside React components on
    this project. An assistant is the last place to reintroduce one,
    because a number MSD prints is a number a chemist may quote.

    AND IT REPORTS WHAT SECTION 9 CANNOT ANSWER YET.

    The Concept Note also asks comparison to cover sanding and adhesion
    performance, failure history and statistical significance. Those need
    the test records for both versions, which this comparison does not
    read. Saying nothing would let a reader take a composition diff for a
    performance comparison, which is the more dangerous of the two.
    """
    previous = diff.get("previous") or {}
    new = diff.get("new") or {}
    lines = [f"{left_label} -> {right_label}"]

    if diff.get("change_reason"):
        lines.append(f"Stated reason for the change: {diff['change_reason']}")
    if diff.get("technical_hypothesis"):
        lines.append(f"Hypothesis: {diff['technical_hypothesis']}")
    if diff.get("expected_effect"):
        lines.append(f"Expected effect: {diff['expected_effect']}")
    # Observed effect is recorded only AFTER testing. Its absence is a
    # fact about the version, not a gap in this answer.
    lines.append(
        f"Observed effect: {diff['observed_effect']}"
        if diff.get("observed_effect")
        else "Observed effect: not recorded yet - this revision has not been tested."
    )

    changed = [c for c in diff.get("components", []) if c["change"] != "unchanged"]
    lines.append("")
    if not changed:
        lines.append("No component differs between these two versions.")
    else:
        lines.append(f"{len(changed)} component(s) differ:")
        for component in changed:
            code = f"{component['material_code']} ({component['material_name']})"
            if component["change"] == "added":
                lines.append(f"- ADDED {code} at {component['new_percentage']}%")
            elif component["change"] == "removed":
                lines.append(f"- REMOVED {code}, was {component['previous_percentage']}%")
            else:
                # A pair, not a difference.
                lines.append(
                    f"- {code}: {component['previous_percentage']}% "
                    f"-> {component['new_percentage']}%"
                )

    readable = {
        "theoretical_density_g_cm3": "Theoretical density (g/cm3)",
        "solids_content_pct": "Solids content (%)",
        "voc_content_g_per_l": "VOC content (g/L)",
        "binder_to_filler_ratio": "Binder to filler",
        "total_percentage": "Total percentage",
        "raw_material_cost_per_kg": "Raw material cost (per kg)",
    }
    property_lines: list[str] = []
    for key, name in readable.items():
        before = (diff.get("previous_properties") or {}).get(key)
        after = (diff.get("new_properties") or {}).get(key)
        if before is None or after is None:
            # ABSENT, not null. The cost key is omitted entirely without
            # `formula.view_cost`, and rendering "not available" would
            # state that no cost data exists.
            continue
        if before.get("value") is not None and after.get("value") is not None:
            property_lines.append(f"- {name}: {before['value']} -> {after['value']}")
        else:
            reason = before.get("unavailable_reason") or after.get("unavailable_reason")
            property_lines.append(f"- {name}: NOT COMPARABLE - {reason}")
    if property_lines:
        lines.append("")
        lines.append("Computed properties:")
        lines.extend(property_lines)

    lines.append("")
    lines.append(
        "This compares COMPOSITION and computed properties. It does not "
        "compare test performance, failure history or statistical "
        "significance - those need the test records for both versions, "
        "which this comparison does not read."
    )
    if previous.get("status") and new.get("status"):
        lines.append(f"Statuses: {previous['status']} -> {new['status']}.")
    return "\n".join(lines)
