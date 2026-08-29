"use client";

/**
 * Opportunities — the front of the digital thread.
 *
 * `CLAUDE.md` §2 begins the thread at Opportunity → Project and requires that
 * no record becomes an isolated island. So a converted opportunity links
 * FORWARD to the project it produced; without that link this screen would be a
 * list of ideas with no way to see what became of them.
 *
 * 🔴 THIS PAGE READ A STATIC ARRAY UNTIL TODAY.
 *
 * It rendered `OPPORTUNITIES` from `lib/demo/dataset` and called no API. There
 * was no opportunities client in the whole application — so `opportunity.create`
 * (the lead) and `opportunity.decide` (the director) were permissions two roles
 * HELD with nothing in the product to press, and the screen showed ideas that
 * no amount of using the application could change.
 *
 * It is now live-only: it shows what the API returns, or says it cannot.
 * Substituting the synthetic ideas when a request fails would make an outage
 * look like a working product, which is the one thing `LiveOnlyPage` exists to
 * prevent.
 *
 * 🔴 THREE ACTS, THREE PERMISSIONS, AND CONVERSION IS THE ODD ONE.
 *
 * Raising and submitting need `opportunity.create`; deciding needs
 * `opportunity.decide`; CONVERTING needs `project.create`, because creating the
 * project is the act being authorized. A director who may decide but may not
 * create projects hands over at that point — the API's own comment calls that
 * the correct separation, and this screen shows it rather than hiding it.
 *
 * ⚠️ NO STATUS IS EVER CHOSEN HERE. `draft → awaiting_decision → approved` is
 * moved by the SERVER in response to an act. A dropdown of the seven states
 * would let somebody mark an idea approved without anybody deciding anything.
 */

import { useState } from "react";

import {
  CreateForm,
  CREATE_INPUT,
  CREATE_LABEL,
} from "@/components/ui/create-form";
import { DataSourceError, LiveOnlyPage } from "@/components/ui/data-source-banner";
import { StatusBadge, type StatusBadgeInput } from "@/components/ui/status-badge";
import { serverMessage } from "@/lib/api/client";
import { useOpportunities, useOpportunityWrites } from "@/lib/api/hooks";
import {
  OPPORTUNITY_DECISIONS,
  OPPORTUNITY_PRIORITIES,
  type Opportunity,
} from "@/lib/api/opportunities";
import { permits, usePermissions } from "@/lib/permissions";

const BUTTON =
  "rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 " +
  "disabled:cursor-not-allowed disabled:bg-slate-300";
const SECONDARY =
  "rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-800 " +
  "hover:bg-slate-100 disabled:cursor-not-allowed disabled:text-slate-400";

/**
 * An opportunity's state, as a badge.
 *
 * 🔴 EVERY YELLOW CARRIES ITS REASON, AND TYPESCRIPT ENFORCES IT.
 *
 * `StatusBadgeInput` makes `reason` REQUIRED on yellow — rule 3 as a compile
 * error rather than a review comment. Each of the three yellows below therefore
 * has to say what is outstanding and who has it, which is exactly what §11 asks
 * of every yellow in the product.
 *
 * ⚠️ `more_information` IS NOT A REJECTION, and neither is `on_hold`. Both send
 * the idea back rather than killing it, so both are yellow. Colouring them with
 * the rejections would teach a lead that asking a question ends a proposal.
 */
function opportunityStatus(row: Opportunity): StatusBadgeInput {
  if (row.status === "converted") {
    return { status: "green", label: "CONVERTED TO A PROJECT" };
  }
  if (row.status === "approved") return { status: "green", label: "APPROVED" };
  if (row.status === "rejected") return { status: "red", label: "REJECTED" };
  if (row.status === "awaiting_decision") {
    return {
      status: "yellow",
      label: "AWAITING A DECISION",
      reason: "submitted and waiting for somebody holding opportunity.decide",
    };
  }
  if (row.status === "on_hold") {
    return {
      status: "yellow",
      label: "ON HOLD",
      reason: "decided as hold — it needs revisiting rather than a fresh idea",
    };
  }
  if (row.status === "feasibility") {
    return {
      status: "yellow",
      label: "FEASIBILITY",
      reason: "being worked up before it goes for a decision",
    };
  }
  return { status: "neutral", label: "DRAFT" };
}

export default function InnovationPage() {
  const opportunities = useOpportunities();
  const rows = opportunities.data ?? [];

  return (
    <LiveOnlyPage
      title="Innovation"
      lede="Opportunities under evaluation, with the decision taken on each. A
            converted opportunity links forward to the project it produced — the
            first link in the digital thread."
      unavailable={opportunities.unavailable}
      notInvented="opportunities and the decisions taken on them"
    >
      {opportunities.error ? (
        <DataSourceError error={opportunities.error} />
      ) : opportunities.unavailable !== null ? (
        <p className="text-sm text-slate-600">
          No opportunities can be shown until this build is pointed at an API.
        </p>
      ) : (
        <div className="grid gap-6">
          <RaiseOpportunityForm />

          <section>
            <h2 className="text-base font-semibold text-slate-900">Opportunities</h2>
            {rows.length === 0 ? (
              <p className="mt-3 text-sm text-slate-600">
                {opportunities.isLoading
                  ? "Loading opportunities…"
                  : "No opportunities have been raised yet."}
              </p>
            ) : (
              <ul className="mt-3 grid gap-3">
                {rows.map((row) => (
                  <OpportunityCard key={row.id} row={row} />
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </LiveOnlyPage>
  );
}

function RaiseOpportunityForm() {
  const writes = useOpportunityWrites();
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [need, setNeed] = useState("");
  const [family, setFamily] = useState("");
  const [concept, setConcept] = useState("");
  const [priority, setPriority] = useState<string>("medium");

  return (
    <CreateForm
      title="Raise an opportunity"
      permission="opportunity.create"
      submitLabel="Raise opportunity"
      isPending={writes.isPending}
      error={writes.error}
      done={writes.lastAction}
      onSubmit={() =>
        writes.raise(
          {
            opportunity_code: code,
            title,
            market_need: need === "" ? undefined : need,
            product_family: family === "" ? undefined : family,
            technical_concept: concept === "" ? undefined : concept,
            priority,
          },
          () => {
            setCode("");
            setTitle("");
            setNeed("");
            setFamily("");
            setConcept("");
          },
        )
      }
    >
      <label className={CREATE_LABEL}>
        Opportunity code
        <input
          className={CREATE_INPUT}
          required
          minLength={3}
          value={code}
          onChange={(event) => setCode(event.target.value)}
        />
      </label>
      <label className={CREATE_LABEL}>
        Title
        <input
          className={CREATE_INPUT}
          required
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
      </label>
      <label className={CREATE_LABEL}>
        Product family
        <input
          className={CREATE_INPUT}
          value={family}
          onChange={(event) => setFamily(event.target.value)}
        />
      </label>
      <label className={CREATE_LABEL}>
        Priority
        <select
          className={CREATE_INPUT}
          value={priority}
          onChange={(event) => setPriority(event.target.value)}
        >
          {OPPORTUNITY_PRIORITIES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
      <label className={`${CREATE_LABEL} sm:col-span-2`}>
        Market need
        <textarea
          className={CREATE_INPUT}
          rows={2}
          value={need}
          onChange={(event) => setNeed(event.target.value)}
        />
      </label>
      <label className={`${CREATE_LABEL} sm:col-span-2`}>
        Technical concept
        <textarea
          className={CREATE_INPUT}
          rows={2}
          value={concept}
          onChange={(event) => setConcept(event.target.value)}
        />
      </label>
    </CreateForm>
  );
}

function OpportunityCard({ row }: { readonly row: Opportunity }) {
  const permissions = usePermissions();
  const writes = useOpportunityWrites();
  const [open, setOpen] = useState<"decide" | "convert" | null>(null);
  const [decision, setDecision] = useState("approve");
  const [rationale, setRationale] = useState("");
  const [projectCode, setProjectCode] = useState("");
  const [projectName, setProjectName] = useState("");

  const maySubmit = permits(permissions, "opportunity.create");
  const mayDecide = permits(permissions, "opportunity.decide");
  const mayConvert = permits(permissions, "project.create");

  return (
    <li className="rounded border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <h3 className="flex-1 text-sm font-semibold text-slate-900">
          {row.opportunity_code} — {row.title}
        </h3>
        <StatusBadge {...opportunityStatus(row)} />
        <span className="text-xs text-slate-600">{row.priority} priority</span>
      </div>
      <p className="mt-1 text-xs text-slate-600">
        {row.product_family ?? "No product family"}
        {row.target_application ? ` · ${row.target_application}` : ""}
        {row.created_by_name ? ` · raised by ${row.created_by_name}` : ""}
      </p>

      {/* 🔴 THE FORWARD LINK §2 REQUIRES. Without it this is a list of ideas
          with no way to see what became of them. */}
      {row.project_code !== null && (
        <p className="mt-2 text-sm text-slate-800">
          Became project <strong>{row.project_code}</strong>.
        </p>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        {row.status === "draft" && (
          <button
            type="button"
            className={SECONDARY}
            disabled={writes.isPending || !maySubmit}
            onClick={() => writes.submit(row.id)}
          >
            Submit for decision
          </button>
        )}
        {row.status === "awaiting_decision" && (
          <button
            type="button"
            className={SECONDARY}
            disabled={!mayDecide}
            onClick={() => setOpen(open === "decide" ? null : "decide")}
          >
            {open === "decide" ? "Cancel" : "Record a decision"}
          </button>
        )}
        {row.status === "approved" && row.project_id === null && (
          <button
            type="button"
            className={SECONDARY}
            disabled={!mayConvert}
            onClick={() => setOpen(open === "convert" ? null : "convert")}
          >
            {open === "convert" ? "Cancel" : "Convert to a project"}
          </button>
        )}
        {row.status === "awaiting_decision" && !mayDecide && (
          <span className="self-center text-xs text-slate-600">
            Deciding needs the opportunity.decide permission.
          </span>
        )}
        {row.status === "approved" && row.project_id === null && !mayConvert && (
          <span className="self-center text-xs text-slate-600">
            Converting creates a project, so it needs project.create.
          </span>
        )}
      </div>

      {open === "decide" && (
        <form
          className="mt-3 grid gap-3 border-t border-slate-200 pt-3 sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            writes.decide(row.id, { decision, rationale }, () => {
              setOpen(null);
              setRationale("");
            });
          }}
        >
          <label className={CREATE_LABEL}>
            Decision
            <select
              className={CREATE_INPUT}
              value={decision}
              onChange={(event) => setDecision(event.target.value)}
            >
              {OPPORTUNITY_DECISIONS.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className={CREATE_LABEL}>
            Rationale
            <input
              className={CREATE_INPUT}
              required
              minLength={3}
              value={rationale}
              onChange={(event) => setRationale(event.target.value)}
            />
            {/* The server requires this and says why in its own comment. */}
            <span className="mt-1 block text-xs font-normal text-slate-600">
              Required. A rejected opportunity with no stated reason gets
              re-proposed every year by somebody who was not in the room.
            </span>
          </label>
          <div className="sm:col-span-2">
            <button type="submit" className={BUTTON} disabled={writes.isPending}>
              {writes.isPending ? "Recording…" : "Record decision"}
            </button>
          </div>
        </form>
      )}

      {open === "convert" && (
        <form
          className="mt-3 grid gap-3 border-t border-slate-200 pt-3 sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            writes.convert(
              row.id,
              { project_code: projectCode, name: projectName },
              () => {
                setOpen(null);
                setProjectCode("");
                setProjectName("");
              },
            );
          }}
        >
          <label className={CREATE_LABEL}>
            Project code
            <input
              className={CREATE_INPUT}
              required
              minLength={3}
              value={projectCode}
              onChange={(event) => setProjectCode(event.target.value)}
            />
          </label>
          <label className={CREATE_LABEL}>
            Project name
            <input
              className={CREATE_INPUT}
              required
              value={projectName}
              onChange={(event) => setProjectName(event.target.value)}
            />
          </label>
          <div className="sm:col-span-2">
            <button type="submit" className={BUTTON} disabled={writes.isPending}>
              {writes.isPending ? "Converting…" : "Create the project"}
            </button>
          </div>
        </form>
      )}

      {writes.error !== null && (
        <p role="alert" className="mt-2 text-sm text-rose-700">
          {serverMessage(writes.error)}
        </p>
      )}
      {writes.error === null && writes.lastAction && (
        <p role="status" className="mt-2 text-sm text-slate-700">
          {writes.lastAction}
        </p>
      )}
    </li>
  );
}
