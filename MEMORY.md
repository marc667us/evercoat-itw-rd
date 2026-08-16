# MEMORY.md — EvercoatITWRD APP

Durable project facts. Not a debug log — temporary work belongs in `TODO.md` and `CHANGELOG.md`.

---

## Identity

- Display name **EvercoatITWRD APP**; slug `evercoat-itw-rd`; DB id `evercoat_itw_rd`; Docker project `evercoat-itw-rd`.
- Fixed by the source amendment at `ITWRD App.txt` L29,736–29,817, which explicitly forbids renaming to ITERDRD or a generic R&D name. The operator's phrasing "ITW Evercoat RD App" was not adopted — flagged, non-blocking, reversible in branding strings only.
- The AI assistant is **MSD — Material Science & Development Assistant**, module `msd`. "R&D Copilot" is a retired synonym; telemetry keeps a `copilot` alias in case earlier records use it.

## Where things live

- Workspace `C:\Users\USER\Documents\evercoat-itw-rd-workspace\`; app in `EvercoatITWRD APP\`; read-only reference copies in `ITERDRD App\`.
- Canonical source originals stay untouched at `C:\Users\USER\Documents\evercoatRD App\`.
- Reuse donor: `C:\Users\USER\Desktop\solar-pv-designer-lite` — see `REUSE.md`.

## Source-document facts

- Two documents only: `EvercoatRD App1.txt` (944 lines, UPDATED CONCEPT NOTE, introduces MSD) and `ITWRD App.txt` (29,862 lines).
- `ITWRD App.txt` is **fifteen** concatenated iterative passes, not ten. Verified line anchors are in `IMPLEMENTATION_PLAN.md` §A.
- The **MASTER CLAUDE CODE PROMPT** at L27,909 plus its two amendments is the highest authority. Then Expanded Requirements, then topic narratives, then the original Blueprint.
- **The messaging module appears verbatim twice**: L18,447–19,884 and L19,887–**21,329**. The next section begins at **L21,330** — not 21,336. Getting that boundary wrong discards the paragraph mandating dashboards as core MVP components.
- **There is no source code in the reference folder.** The master prompt's instructions about reusing the reference application are void.

## Decisions that will not change

- Seven non-negotiable rules (`CLAUDE.md` §3): Postgres owns facts · Python owns calculation · testing verifies and models only predict · humans approve · released formulations immutable · traffic light derived and passing-but-unapproved stays YELLOW · zero-cost open-source core.
- Authorization is by **permission**, never role name. Ten seeded realm roles are defaults; QA, compliance and regulatory are separate permissions that may be assigned to one person or three.
- **NUMERIC never float** for controlled quantities. **RESTRICT never CASCADE** on R&D history. Retire via status, never `DELETE`.
- Every tenant-scoped table declares `UNIQUE (id, organization_id)`; child→parent FKs are composite. Without that unique constraint the first composite-FK migration fails outright.
- All codes are tenant-scoped, including `lab_batch_number` and `sample_number`.
- Test status is five stored axes — `execution_status`, `validity_status`, `calculated_result`, `review_state`, `approval_state` — with `display_color`/`final_status`/`final_confirmed` **derived and server-owned**. Derivation is an ordered algorithm, first match wins. Do not reintroduce `approved_result`, `technical_status` or `calculated_status`.
- Ports for contested or heavy dependencies: `WorkflowPort`, `AgentOrchestrationPort`, `ObjectStoragePort`, `EmailPort`. Business logic never imports a vendor.
- Docker Compose is the deployment path. Render is optional demo staging and **must never hold real R&D records** — its free Postgres expires after 30 days.

## Review history

- **Pass 1, 2026-08-16.** Plan v1 → Codex **FAIL**, 43 findings, 5 BLOCKER → Supervisor **FAIL upheld**, 40 upheld / 3 overturned-or-narrowed / 1 escalated → plan v2 → Supervisor code-review, 13 further findings, **9 new** → plan v3. Full record in `docs/REVIEW_PASS1_ADJUDICATION.md`.
- Confirmed again that **neither reviewer alone is enough**: Codex found the tenancy BLOCKER and the missed Concept-Note/Master-Prompt contradiction; the Supervisor independently found the unimplementable composite-FK rule, the missing Administration write path, the ambiguous traffic-light precedence, and the inconsistent status column names.
- **Reviewers are not oracles.** Three Codex findings were overturned or narrowed after checking against source. Verify before acting.

## Lessons already paid for

- **The Administration write path.** Both plan versions said configuration was "editable in Administration" while no slice built it. *Ask of every role and every config value: which production path **writes** it?*
- **Two literals in two files cannot be type-checked into agreement.** The test-status column names drifted across four documents before anyone noticed.
- **A status file lies as easily as it informs.** `CONTEXT.md` claimed `MEMORY.md` and `DECISIONS.md` existed when they did not. Measure the repo; do not quote the handover.
- **Synthetic data cannot validate scientific correctness.** Hypothesis proves internal consistency, not chemistry. The calculation engine needs review by a formulation chemist before production trust.
- Solar's RLS is **tenant-scoped only** — reusing it unchanged would import this project's single highest risk instead of retiring it.

## Environment

- Windows 10, PowerShell 5.1 primary (no `&&`/`||`/`??`), Bash available for POSIX. Node at `C:\Users\USER\nodejs`, not on default PATH. `gh.exe` at `%USERPROFILE%\bin`.
- **Not installed:** pandoc, wkhtmltopdf, reportlab, WeasyPrint. PDF generation uses `markdown-pdf`.
- PowerShell pipes add a UTF-16 BOM to secrets — write secret files with explicit UTF-8.
- Docker memory is the binding constraint once Ollama arrives; Slice 1 measures headroom before Slice 7 adds model weights.

## Settled by the operator, 2026-08-16

- **AI framework: LangGraph OSS** (ADR-002). Chosen after being shown both the governance conflict and Codex's contrary recommendation. This is an **explicit, operator-granted exception to root `CLAUDE.md` §0.1**, which makes Google ADK the only permitted agent framework platform-wide. Recorded loudly, not followed silently — the root file treats a silent contradiction as a defect.
  Codex's leak analysis stands and is acted on: domain tools are framework-neutral plain Python with Pydantic signatures; the conversation/event model and checkpoints are ours, not LangGraph's; streamed events are normalized to our own shape; contract tests run against the tool layer with no orchestrator. The leak is bounded to `app/agents/graphs/`.
  **§0.2 (orchestration-first) and §0.3 (reusability) are retained in full** — they are framework-independent. Only §0.1 is waived. Root Orchestrator + department Conductors still apply; specialists never call agents; routes never call specialists.
- **Schedule: full depth, gate by gate** (ADR-024). Every slice to the Definition of Done, in dependency order. Nothing cut; the source's defer order is not used. A slice ships when its gate passes, not when a day ends. The 45 h / 14-day figures stay recorded as source requirements, never as commitments.

## Still open

- **Git remote** — local repo only; no remote until the operator names one.
- **Repository hosting policy** — GitHub Actions assumed, CI logic kept in `scripts/*.sh` so the runner stays swappable.
