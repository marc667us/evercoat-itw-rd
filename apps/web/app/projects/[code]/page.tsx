import type { Metadata } from "next";

import { notFound } from "next/navigation";

import { PROJECTS, projectByCode } from "@/lib/demo/dataset";

import { ProjectDetail } from "./project-detail";

/**
 * A server component whose only jobs are the route's static params and its
 * metadata. The workspace itself is a client component, because the data
 * grid it uses is one.
 *
 * `generateStaticParams` is REQUIRED here, not an optimisation. Under
 * `output: "export"` there is no server to resolve a dynamic segment at
 * request time, so a `[code]` route with no static params is a build
 * error. Every project in the dataset therefore gets its own pre-rendered
 * page — which is also why deep links into a project work on a static host
 * with no rewrite rules.
 */
export function generateStaticParams(): { code: string }[] {
  return PROJECTS.map((p) => ({ code: p.project_code }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}): Promise<Metadata> {
  const { code } = await params;
  const project = projectByCode(code);
  return {
    // The code, not just the name: a tab showing "Premium Lightweight
    // Automotive Putty" is indistinguishable from any other tab of the
    // same product once truncated.
    title: project ? `${project.project_code} · ${project.name}` : "Project",
  };
}

export default async function ProjectPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  // `params` is a Promise in Next 15 — awaiting it is required, not
  // stylistic. Reading it synchronously is a build-time error.
  const { code } = await params;
  // A real 404, not a 200 carrying a "not found" body.
  //
  // `dynamicParams` defaults to true, so under `next start` — which is the
  // mode the E2E suite runs — /projects/NOPE server-rendered the fallback
  // with HTTP 200, contradicting this suite's own rule that an unbuilt
  // route is never silently served. Raised by the Supervisor.
  if (!projectByCode(code)) notFound();
  return <ProjectDetail code={code} />;
}
