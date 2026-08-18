import type { Metadata } from "next";

import { notFound } from "next/navigation";

import { FORMULAS, formulaByCode } from "@/lib/demo/dataset";

import { FormulaDetail } from "./formula-detail";

/**
 * Static params for every formula, for the same reason as the project
 * route: under `output: "export"` there is no server to resolve a dynamic
 * segment, so a `[code]` route with no static params is a build error.
 */
export function generateStaticParams(): { code: string }[] {
  return FORMULAS.map((f) => ({ code: f.formula_code }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}): Promise<Metadata> {
  const { code } = await params;
  const f = formulaByCode(code);
  return { title: f ? `${f.formula_code} · ${f.name}` : "Formula" };
}

export default async function FormulaPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  // A real 404 rather than a 200 carrying a "not found" body.
  if (!formulaByCode(code)) notFound();
  return <FormulaDetail code={code} />;
}
