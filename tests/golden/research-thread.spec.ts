import { expect, test, type Locator, type Page } from "@playwright/test";

/**
 * §39's golden scenario, walked in a browser — the UI half of R4b.
 *
 * `apps/api/tests/db/test_golden_scenario_research.py` walks this chain
 * against PostgreSQL and says so in its own header: *"This is the DATABASE
 * half ... §39's own gate would be the scenario on the deployed instance
 * asserted in UI and database state."* This is the other half.
 *
 * ─────────────────────────────────────────────────────────────────────────
 * 🔴 WHAT THIS FILE DOES NOT CLAIM
 * ─────────────────────────────────────────────────────────────────────────
 *
 * **It does not close §39.** §39 asks for the scenario on the DEPLOYED
 * instance, and this runs in CI. Two reasons, and the first is a correction of
 * an earlier draft of this comment:
 *
 * ⚠️ **THIS WALK STOPS BEFORE THE APPROVAL ENGINE, DELIBERATELY.** An earlier
 * draft justified CI-only by saying the walk reaches
 * `workflow.approval_route_steps`, which is append-only **even to the
 * superuser** — measured: *"approval_route_steps is append-only; DELETE is not
 * permitted"*. That is true of §39's FULL chain and it is exactly why the walk
 * ends at the proposal: submitting a finding for approval writes rows that can
 * never be removed, so a walk that did it would be irreversible on every run,
 * everywhere, CI included. **The chain beyond the proposal is the database
 * half's to own**, and `test_golden_scenario_research.py` owns it.
 *
 * 🔴 **AND WHAT IT DOES WRITE IS STILL PERMANENT.** The research records
 * here are not append-only, but §5 is explicit that R&D history is RETIRED and
 * never deleted, and every FK into it is `RESTRICT`. Against a long-lived
 * deployed database, running this on each deploy accumulates real workspaces,
 * questions, evidence and findings that nothing is allowed to clean up. CI
 * rebuilds its database from migrations on every run, so they go with the
 * runner.
 *
 * That is the trade the owner chose. CI is not "the deployed instance", so the
 * gap is named here rather than quietly closed — what this buys is regression
 * cover on every commit, which the deployed-only reading buys never.
 *
 * **And it walks the RESEARCH vertical**, the hops the Research Center owns
 * and a person can actually press. The competitor/SDS vertical has its own
 * tests and DOE has no module at all.
 *
 * ─────────────────────────────────────────────────────────────────────────
 * 🔴 WHY THE READ-BACK IS A RELOAD AND A COUNT, NOT A GREEN TOAST
 * ─────────────────────────────────────────────────────────────────────────
 *
 * A walk that pressed each control and asserted the button went into a pending
 * state would pass against an application whose every write the API refused —
 * precisely the shape this project shipped on 2026-08-24, when 713 tests were
 * green beside a sign-in that 404'd.
 *
 * So the walk writes everything in one session, then RELOADS, then SIGNS IN
 * AGAIN — because per ADR-025 the reload signs the user out, the token living
 * in memory on purpose. What comes back is a fresh document, a fresh token and
 * a fresh query for every panel, and the workspace row must itself say
 * `1 question(s) · 1 card(s) · 1 finding(s) · 1 proposal(s)`. Those counts are
 * computed by the SERVER from the rows it stored. A count is a better witness
 * than the text echoing back: the text could be rendered from the cache that
 * accepted it, but the count can only come from a row that exists.
 */

// ⚠️ DELIBERATELY NOT A `page.goto` TARGET — kept only to name the screen
// this file walks. Navigating to it directly signs the user out (ADR-025).
const RESEARCH_PATH_FOR_REFERENCE = "/material-safety/research";
void RESEARCH_PATH_FOR_REFERENCE;

/**
 * 🔴 THE WALK SIGNS IN AS A CHEMIST, AND THE ROLE IS NOT INTERCHANGEABLE.
 *
 * Migration 058 grants `research.create` + `experiment.propose` +
 * `experiment.accept` to `product_development_chemist`, and the engineer gets
 * the first two but NOT accept. The lead is granted neither propose nor accept
 * — 058 says so in a comment headed *"THE LEAD DOES NOT GET
 * `experiment.accept`, AND THE PLAN SAID THEY"*. `lead.demo` is the default
 * user of `sign-in.spec.ts` and would reach this screen with the propose form
 * DISABLED, which renders as a control that will not submit rather than as an
 * error — a walk that hung on a disabled button, blaming the form.
 */
const USERNAME = process.env.GOLDEN_USER ?? "chem.demo";
const PASSWORD = process.env.TEST_KEYCLOAK_PASSWORD ?? "";

/** The realm's own login form, whatever theme it is wearing. */
const USERNAME_FIELD = "#username, input[name='username']";
const PASSWORD_FIELD = "#password, input[name='password']";

/** Run-unique, so a re-run never matches the previous run's rows. */
const tag = `g${Date.now().toString(36)}`;
const TITLE = `Filler adhesion loss ${tag}`;

test.describe("§39 — the research thread, in a browser", () => {
  test("a chemist walks from a research question to an experiment proposal", async ({
    page,
  }) => {
    // ⚠️ NO SILENT SKIP. `sign-in.spec.ts` skips without a password because it
    // must run on a laptop with no realm. This walk exists only where a realm
    // exists, so an absent password is a misconfigured job, not a legitimate
    // absence — and a skipped golden scenario reporting green is precisely the
    // "0 failed / 35 skipped" shape that hid 24 dead tests on 2026-08-31.
    expect(
      PASSWORD,
      "TEST_KEYCLOAK_PASSWORD is unset — the golden walk cannot sign in",
    ).not.toBe("");

    await page.goto("/");
    await signIn(page);

    // 🔴 NAVIGATE BY CLICKING, NEVER BY `page.goto`. ADR-025.
    //
    // `auth-provider.tsx` states it in capitals: *"THE TOKEN LIVES IN MEMORY,
    // AND A RELOAD SIGNS YOU OUT ... after a reload the user is ANONYMOUS and
    // must press Sign in. Nothing happens automatically."* A decision, not an
    // omission — a token in browser storage turns one XSS into a stolen
    // session, and the `prompt=none` iframe renew is declined because Safari
    // blocks it and Chrome is removing it.
    //
    // ⚠️ MEASURED 2026-09-01: this walk used `page.goto()` straight after
    // signing in. That is a FULL LOAD, so the module holding the session was
    // re-evaluated, the user was anonymous, and the screen rendered its "No
    // data source" notice with no form on it. CI reported a
    // `getByLabel("Title")` timeout twice — naming the control, never the
    // cause. A person reaches this screen through the sidebar; so does this.
    await openResearchCenter(page);

    // ── §39 "Research Solution" — open the workspace ──────────────────────
    //
    // 🔴 A PROJECT IS SELECTED DELIBERATELY, AND THE SCREEN SAYS WHY:
    // *"A finding from an organization-wide workspace cannot be sent for
    // approval: each project's lead approves for their own work, so the
    // approval route needs a project."* An organization-wide workspace is the
    // easier walk — it needs no seeded project — and it would have dead-ended
    // at exactly the hop §39 cares about. It is chosen from the EXISTING
    // seeded projects, so the walk creates no parallel Project of its own,
    // which is the integration mistake §39 ends on.
    // 🔴 READ THE SCREEN'S OWN REFUSAL BEFORE BLAMING A MISSING CONTROL.
    //
    // `LiveOnlyPage` replaces the whole workspace with a "No data source"
    // note whenever the session is not authenticated or the build has no API,
    // and in that state the form below simply does not exist. Twice now a run
    // has died on `getByLabel("Title")` timing out, which says nothing about
    // WHY. The note names the reason, so read it out.
    const noSource = page.getByTestId("no-data-source");
    if (await noSource.isVisible().catch(() => false)) {
      throw new Error(
        "the Research Center is showing its no-data-source notice, so no " +
          "form exists. The screen says: " +
          (await noSource.innerText()).replace(/\s+/g, " ").trim(),
      );
    }

    const openForm = formTitled(page, "Open a research workspace");
    await openForm.getByLabel("Title").fill(TITLE);
    await openForm
      .getByLabel("Research question")
      .fill(`Does talc loading above 22% reduce adhesion? ${tag}`);

    const project = openForm.getByLabel("Project");
    const projectValues = await project.locator("option").evaluateAll((options) =>
      options.map((option) => (option as HTMLOptionElement).value),
    );
    // Index 0 is "Organization-wide (no project)" — a real choice, not a
    // placeholder, and not the one this walk wants.
    const realProject = projectValues.find((value) => value !== "");
    expect(
      realProject,
      "the seed must provide at least one project — §39's approval hop needs one",
    ).toBeTruthy();
    await project.selectOption(realProject as string);

    await openForm.getByRole("button", { name: "Open workspace" }).click();
    await expect(page.getByText(TITLE)).toBeVisible({ timeout: 30_000 });

    // ── open it, then record the thread ──────────────────────────────────
    await openWorkspace(page);

    // §39 "existing materials searched" — the question, asked and recorded.
    const questions = panelTitled(page, "Questions");
    await questions.getByLabel("Add a question").fill(`Is 22% the knee? ${tag}`);
    await questions.getByRole("button", { name: "Add", exact: true }).click();
    await expect(questions.getByText(`Is 22% the knee? ${tag}`)).toBeVisible();

    // §39 "evidence assembled" — a source FIRST.
    //
    // ⚠️ THE ORDER IS THE POINT, NOT CONVENIENCE. The evidence form disables
    // its own submit and says *"Record a source first — an evidence card must
    // cite one."* A walk that tried evidence first would be exercising that
    // refusal rather than the thread.
    //
    // The default Kind is "Published literature", which needs no Knowledge
    // Library document. "A document on file" would make this walk depend on
    // the seed having documents, and the form disables submit when there are
    // none — a dependency worth not taking.
    const sourceTitle = `Adhesion study ${tag}`;
    const sources = panelTitled(page, "Sources");
    await sources.getByLabel("Source title").fill(sourceTitle);
    await sources.getByRole("button", { name: "Record source" }).click();
    await expect(sources.getByText(sourceTitle)).toBeVisible();

    // … then the card that cites it.
    const evidence = panelTitled(page, "Evidence cards");
    await evidence
      .getByLabel("What the evidence says")
      .fill(`Adhesion falls sharply above 22% talc ${tag}`);
    // ⚠️ NOT `selectOption({ label: sourceTitle })`. The option renders as
    // `{evidence_grade} — {title}`, and Playwright matches a label EXACTLY, so
    // that would have failed on a source that exists — a red test blaming the
    // wrong thing. The value is the id; find it by the title it contains.
    const sourceSelect = evidence.getByLabel("Source it rests on");
    const sourceValue = await sourceSelect
      .locator("option")
      .evaluateAll(
        (options, title) =>
          (options as HTMLOptionElement[]).find((option) =>
            option.textContent?.includes(title),
          )?.value ?? "",
        sourceTitle,
      );
    expect(
      sourceValue,
      "the source just recorded is not offered by the evidence form",
    ).not.toBe("");
    await sourceSelect.selectOption(sourceValue);
    await evidence.getByRole("button", { name: "Record evidence" }).click();
    await expect(
      evidence.getByText(`Adhesion falls sharply above 22% talc ${tag}`),
    ).toBeVisible();

    // ── §39 "Research Finding generated" ─────────────────────────────────
    const findingSubject = `Talc knee at 22% ${tag}`;
    const finding = formTitled(page, "Draft a finding");
    await finding.getByLabel("Subject").fill(findingSubject);
    await finding
      .getByLabel("The finding")
      .fill("Adhesion falls below requirement once talc exceeds 22% by mass.");
    await finding
      .getByLabel("Applicability")
      .fill("Polyester body filler, ambient cure, steel substrate.");
    await finding.getByRole("button", { name: "Draft finding" }).click();

    // ⚠️ WAIT FOR THE WRITE TO LAND BEFORE DOING ANYTHING ELSE. The form
    // clears itself from the SUCCESS callback, so an empty Subject means the
    // API answered. Without this the reload below can tear the document down
    // mid-`fetch` and abort a request the server would have honoured — a red
    // run blaming the API for the test's own impatience, and `retries: 0`
    // means there is no second attempt to reveal it as noise.
    await expect(finding.getByLabel("Subject")).toHaveValue("", {
      timeout: 30_000,
    });

    // ── §39 "Experiment Proposal generated" ──────────────────────────────
    //
    // The screen states the boundary this walk must not cross: *"A proposal
    // changes nothing on its own. A chemist decides whether it becomes an
    // actual experiment, and accepting it creates a formula revision."* The
    // proposal is raised here; acceptance is the hop where the FORMULATIONS
    // module — never the Research Center — creates the formula version, and
    // the database half asserts that as an absence.
    const objective = `Reformulate at 18% talc ${tag}`;
    const proposal = formTitled(page, "Propose an experiment");
    await proposal.getByLabel("Objective").fill(objective);
    // ⚠️ THE BASIS MUST NOT REPEAT THE FINDING'S SUBJECT VERBATIM. It did,
    // and the final `getByText(findingSubject)` would then have matched BOTH
    // registers and failed on strict mode — a test that goes red for a reason
    // that says nothing about the application.
    await proposal
      .getByLabel("Basis")
      .fill("The adhesion finding recorded in this workspace.");
    await proposal.getByLabel("Variables").fill("Talc loading 14 / 18 / 22 % by mass.");
    await proposal.getByLabel("Expected direction").fill("Adhesion recovers below 22%.");
    await proposal
      .getByLabel("Required tests")
      .fill("Cross-hatch adhesion, ISO 2409; three replicates per level.");
    await proposal.getByRole("button", { name: "Propose experiment" }).click();
    await expect(proposal.getByLabel("Objective")).toHaveValue("", {
      timeout: 30_000,
    });

    // ── 🔴 THE READ-BACK ─────────────────────────────────────────────────
    //
    // Everything above ran against one loaded page. Reload, and let the SERVER
    // say what it stored. The workspace row carries counts it computed, so a
    // write the API silently refused cannot survive this.
    // 🔴 A NEW PAGE, A NEW SESSION, AND THE SERVER'S OWN COUNTS.
    //
    // Everything above ran against one loaded page, so none of it yet proves a
    // row exists anywhere but in a cache. The reload discards the document AND
    // — per ADR-025 — the session with it, which is why the walk signs in
    // again rather than simply carrying on.
    //
    // ⚠️ THAT MAKES THIS STRONGER THAN A PLAIN RELOAD, NOT A WORKAROUND: what
    // comes back is a fresh document, a fresh token and a fresh query for every
    // panel. The counts are computed by the SERVER from stored rows, so a write
    // it silently refused cannot survive the trip — and neither can one that
    // lived only in the client's cache.
    await page.reload();
    await signIn(page);
    await openResearchCenter(page);

    const row = workspaceRow(page);
    // ⚠️ ANCHORED ON THE SEPARATOR, NOT A BARE SUBSTRING. `toContainText("1
    // question(s)")` is also satisfied by `11 question(s)` and `21
    // question(s)`. The run-unique title means that cannot misfire today, but
    // this is the assertion the whole file rests on — it should not depend on
    // a workspace never reaching eleven of anything.
    await expect(row).toContainText(/·\s*1 question\(s\)/, { timeout: 30_000 });
    await expect(row).toContainText(/·\s*1 card\(s\)/);
    await expect(row).toContainText(/·\s*1 finding\(s\)/);
    await expect(row).toContainText(/·\s*1 proposal\(s\)/);

    // And the two registers — the screens a person other than the author
    // reads — must show the finding and the proposal by name.
    await expect(page.getByText(findingSubject)).toBeVisible();
    await expect(page.getByText(objective)).toBeVisible();
  });
});

/**
 * Sign in the way a person does — press the button, type into the REALM's own
 * form, come back.
 *
 * Not a fabricated session and not the development seam: that seam is compiled
 * OUT of production builds, so a walk using it would prove the screens work
 * for a session the real application can never issue. Every write below then
 * carries a token the API verified against a real Keycloak.
 */
async function signIn(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Sign in" }).click();

  // ⚠️ THE SECOND SIGN-IN USUALLY SEES NO FORM AT ALL, AND THAT IS CORRECT.
  //
  // `auth-provider.tsx`: *"the redirect usually returns without a password
  // prompt, because Keycloak's own SSO cookie is still valid — so it costs a
  // round trip, not a login."* So wait for EITHER the realm's form or the
  // application's signed-in furniture, and type only when asked. Demanding the
  // form would fail the read-back for behaving exactly as designed.
  const username = page.locator(USERNAME_FIELD);
  const switcher = page.getByLabel("Active organization");
  await expect(
    username.or(switcher).first(),
    "neither the realm's login form nor a signed-in application — if the form " +
      "is missing, the realm most likely rejected redirect_uri, and the web " +
      "origin must be http://localhost:3000, which is what evercoat-web " +
      "registers",
  ).toBeVisible({ timeout: 60_000 });

  if (await username.isVisible().catch(() => false)) {
    await username.fill(USERNAME);
    await page.locator(PASSWORD_FIELD).fill(PASSWORD);
    await page.locator(PASSWORD_FIELD).press("Enter");
  }

  // 🔴 LEAVE THE REALM FIRST, AND ASSERT NOTHING UNTIL WE HAVE.
  //
  // This used to assert that the application's "Sign in" button had gone
  // hidden. **Measured 2026-09-01, that assertion matched KEYCLOAK'S OWN
  // BUTTON** — `<button id="kc-login" name="login">Sign In</button>` — because
  // an accessible-name match is case-insensitive, so "Sign in" finds "Sign In".
  // The walk sat on the realm's page for the full 60s watching the realm's own
  // control and reported that the application had failed its token exchange.
  //
  // Two different pages, one accessible name, and the failure message named
  // the wrong one of them. So: get off the realm's origin FIRST — the same
  // order `sign-in.spec.ts` uses, for the same reason.
  await page.waitForURL(
    (url) => !/\/realms\/|\/protocol\/openid-connect\//.test(url.pathname),
    { timeout: 60_000 },
  );

  // ⚠️ AND ASSERT ON A CONTROL THE REALM HAS NO EQUIVALENT OF. The
  // organization switcher renders only once a session exists, and Keycloak
  // has nothing named like it — so unlike "Sign in", it cannot be satisfied
  // by the wrong page.
  await expect(
    page.getByLabel("Active organization"),
    "no organization switcher — back in the application but no session, so " +
      "the token exchange did not complete",
  ).toBeVisible({ timeout: 60_000 });
}

/**
 * Reach the Research Center the way a person does — through the sidebar, with
 * the session intact. See the ADR-025 note in the test for why this is never
 * `page.goto`.
 */
async function openResearchCenter(page: Page): Promise<void> {
  const link = page.getByRole("link", { name: "Research Center", exact: true });

  // The domain section may need opening first. Both are real user paths, and
  // this hides nothing: the assertion below still has to hold either way.
  if (!(await link.isVisible().catch(() => false))) {
    await page
      .getByRole("link", { name: /Material Safety Data/i })
      .first()
      .click();
  }

  await link.click();
  await expect(
    page.getByRole("heading", { name: "Research Center" }),
  ).toBeVisible({ timeout: 30_000 });
}

/** The `<li>` for this walk's workspace, found by its unique title. */
function workspaceRow(page: Page): Locator {
  return page.locator("li").filter({ hasText: TITLE }).first();
}

/**
 * Expand the workspace.
 *
 * ⚠️ THE PANELS ARE NOT ADDRESSABLE. `openId` is React state, not a URL, so
 * the workspace exists only while this page instance is open — which is why
 * every write below happens in ONE session and the read-back is a single
 * reload at the end rather than one after each step. A reload mid-walk would
 * collapse the panels and the next step would fail on a control that is
 * genuinely absent, for a reason that says nothing about the thread.
 */
async function openWorkspace(page: Page): Promise<void> {
  await workspaceRow(page).getByRole("button", { name: "Open", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Questions" })).toBeVisible();
}

/**
 * Scope to one panel by its heading.
 *
 * ⚠️ SCOPING IS NOT TIDINESS. The workspace stacks seven panels of near
 * identical shape, and several labels repeat across them — "Subject" is on the
 * finding form, "Confidence" on two forms. An unscoped `getByLabel` would fill
 * whichever rendered first and the walk would pass while writing the value
 * against the wrong record.
 */
function panelTitled(page: Page, heading: string): Locator {
  return page
    .locator("section")
    .filter({ has: page.getByRole("heading", { name: heading, exact: true }) })
    // \U0001f534 `.last()`, NOT `.first()` — AND THE DIFFERENCE WAS A BLOCKER.
    //
    // The panels are nested INSIDE the `<section>` that holds
    // `<h2>Research workspaces</h2>`, so that outer section also `has:` the
    // panel's heading and, being an ancestor, comes FIRST in document order.
    // `.first()` therefore returned the whole page region rather than one
    // panel: `getByRole("button", { name: "Add" })` then resolved to three
    // buttons — Questions, Hypotheses and Gaps — and died on strict mode at
    // the very first interaction. The innermost match is the last one.
    .last();
}

function formTitled(page: Page, heading: string): Locator {
  return page
    .locator("form")
    .filter({ has: page.getByRole("heading", { name: heading, exact: true }) })
    .first();
}
