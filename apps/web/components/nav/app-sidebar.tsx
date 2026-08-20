"use client";

/**
 * The sidebar, with its badge counts computed from the same source as the
 * screen behind them.
 *
 * 🔴 THE BADGE AND THE PAGE MUST NOT DISAGREE.
 *
 * The count was previously computed in `app/layout.tsx` — a SERVER
 * component — from the bundled demonstration fixture. That was correct
 * while My Work was a demonstration screen too. The moment My Work
 * started issuing a real request, the badge became a build-time constant
 * sitting beside a live list: a signed-in chemist with four real tasks
 * would have seen whatever number the fixture happened to contain.
 *
 * A badge that disagrees with the page it points at is worse than no
 * badge, because a reader trusts the smaller number to be a summary of
 * the larger one. This project has already recorded the same shape twice:
 * two literals encoding one rule, and a sidebar count that meant
 * something different from the queue it labelled.
 *
 * So the count comes from `useMyWork` — the same hook, the same query
 * key, the same cache entry the page reads. They cannot drift, because
 * there is only one of them.
 *
 * `CLAUDE.md` §11: a badge counts items needing action BY THE HOLDER,
 * never total rows. `/api/my-work` already filters to actionable statuses,
 * and the demonstration path counts only the viewer's own open tasks.
 */

import { Sidebar } from "@/components/nav/sidebar";
import { useMyWork } from "@/lib/api/hooks";
import { DEMO_VIEWER, tasksAssignedTo } from "@/lib/demo/dataset";

export function AppSidebar({ permissions }: { permissions: ReadonlySet<string> }) {
  // The demonstration fallback is the viewer's OWN open tasks, which is
  // what `tasksAssignedTo` returns — not `TASKS.length`, and not the
  // organisation's open tasks either, which is what a badge beside the
  // words "My Work" would otherwise have been claiming.
  const { data, error } = useMyWork(tasksAssignedTo(DEMO_VIEWER).length, (live) => live.length);

  // `data` is undefined while a live request is in flight or after it
  // failed. No badge is shown then, deliberately: a zero would be a claim
  // that there is nothing to do, and that is the one wrong answer.
  // 🔴 `error` IS CHECKED, NOT JUST `data`.
  //
  // React Query KEEPS the last successful `data` when a background
  // refetch fails. The page prioritises `error` and shows no rows, so
  // without this the sidebar went on advertising a count for a list that
  // was displaying an error — the badge and the page disagreeing, which
  // is the exact defect this component was created to end. Codex found
  // it.
  const usable = error === null && data !== undefined;
  return (
    <Sidebar permissions={permissions} counts={usable ? { "my-work": data } : {}} />
  );
}
