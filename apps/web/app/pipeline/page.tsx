import type { Metadata } from "next";

import Link from "next/link";

import { DemoPage } from "@/components/ui/demo-banner";
import { formatDay } from "@/lib/format/date";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  PROJECTS,
  STAGES,
  requirementSetStatus,
  userName,
} from "@/lib/demo/dataset";

export const metadata: Metadata = { title: "R&D Pipeline" };

/**
 * The R&D pipeline, as the eight configured stage gates.
 *
 * A server component: it renders no interactive grid, so there is nothing
 * to send to the client but markup.
 *
 * The stages come from the configured stage set, NOT from the distinct
 * values present in the project rows. That difference matters — deriving
 * columns from the data makes an empty stage vanish, so nobody can see
 * that Laboratory has no projects in it, which is exactly the kind of
 * question a pipeline view exists to answer.
 */
export default function PipelinePage() {
  return (
    <DemoPage
      title="R&D Pipeline"
      lede="Projects positioned across the eight configured stage gates. Stages with
            nothing in them are shown deliberately — an empty stage is a finding,
            and a board that hides it cannot report one."
    >
      <div className="flex gap-3 overflow-x-auto pb-3">
        {STAGES.map((stage) => {
          const inStage = PROJECTS.filter(
            (p) => p.current_stage === stage.stage_code,
          );
          return (
            <section
              key={stage.stage_code}
              className="w-72 shrink-0 rounded border border-slate-200 bg-slate-50"
              aria-label={`${stage.name} stage`}
            >
              <header className="border-b border-slate-200 px-3 py-2">
                <div className="flex items-baseline justify-between gap-2">
                  <h2 className="text-xs font-semibold text-slate-900">
                    {stage.sequence}. {stage.name}
                  </h2>
                  <span className="text-xs tabular-nums text-slate-500">
                    {inStage.length}
                  </span>
                </div>
                <p className="mt-0.5 text-[11px] text-slate-500">
                  {stage.requires_approval
                    ? `Exit requires ${stage.approval_role?.replace(/_/g, " ")} approval`
                    : "No approval gate"}
                </p>
              </header>

              <ul className="space-y-2 p-2">
                {inStage.length === 0 && (
                  <li className="rounded border border-dashed border-slate-300 bg-white p-3 text-[11px] text-slate-500">
                    No projects at this stage.
                  </li>
                )}
                {inStage.map((p) => {
                  const verdict = requirementSetStatus(p.requirements);
                  return (
                    <li key={p.project_code}>
                      <Link
                        href={`/projects/${p.project_code}`}
                        className="block rounded border border-slate-200 bg-white p-3 transition-colors hover:border-slate-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-900"
                      >
                        <div className="text-[11px] tabular-nums text-slate-500">
                          {p.project_code}
                        </div>
                        <div className="mt-0.5 text-xs font-medium text-slate-900">
                          {p.name}
                        </div>
                        <div className="mt-1 text-[11px] text-slate-600">
                          Lead {userName(p.lead)}
                        </div>
                        {/* ⚠️ TARGET RELEASE, NOT "ADDED", AND THAT IS NOT AN
                            OVERSIGHT.
                            This board is fixture-backed (`DemoPage` over
                            `PROJECTS`) and `DemoProject` carries no creation
                            date. Rendering "Added —" on every card would put an
                            empty date column on a board where nothing could ever
                            fill it. The target release date is the one the
                            fixture genuinely holds, and it is the date a stage
                            board is actually about. The LIVE creation date is on
                            /projects, which reads the API. */}
                        {p.target_release_date !== null && (
                          <div className="mt-0.5 text-[11px] text-slate-600">
                            Target release {formatDay(p.target_release_date)}
                          </div>
                        )}
                        {/* A card with no requirements said "ALL PASSED".
                            Absence of evidence is not success. */}
                        <div className="mt-2">
                          {verdict.status === "yellow" ? (
                            <StatusBadge
                              status="yellow"
                              label={verdict.label}
                              reason={verdict.reason ?? ""}
                              size="sm"
                            />
                          ) : (
                            <StatusBadge
                              status={verdict.status}
                              label={verdict.label}
                              size="sm"
                            />
                          )}
                        </div>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })}
      </div>
    </DemoPage>
  );
}
