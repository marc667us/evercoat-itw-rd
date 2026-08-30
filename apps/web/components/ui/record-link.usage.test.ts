import { readFileSync } from "node:fs";
import { join } from "node:path";
import { readdirSync, statSync } from "node:fs";

import { describe, expect, it } from "vitest";

/**
 * No screen may hand-roll a link into a detail route that only knows the
 * demonstration dataset.
 *
 * 🔴 THE ANALYTICS TABLE 404'd, AND IT LOOKED LIKE THE MOST CORRECT LINE ON
 * THE PAGE.
 *
 * `CLAUDE.md` §2 asks that every figure drill down to a real source record, and
 * the portfolio table obliged: `<Link href={`/projects/${p.project_code}`}>`,
 * over rows fetched live from the API. But `/projects/[code]` renders from
 * `lib/demo/dataset` and calls `notFound()` for any code that is not one of
 * the THREE bundled projects — so every live project in that table led to a
 * 404. Reported by the operator, not by any test.
 *
 * `RecordLink` already existed for exactly this: it asks whether THIS BUILD has
 * a detail page for the code and renders plain text with a reason when it does
 * not. The defect was not a missing component, it was a screen not using the
 * one that was there — which no type and no lint rule can see.
 *
 * So this asserts the rule structurally: inside `app/`, a template link into
 * `/projects/` or `/formulations/` must go through `RecordLink`.
 *
 * ⚠️ SCOPED TO SCREENS THAT READ LIVE DATA, AND THAT IS THE WHOLE RULE.
 *
 * A screen rendering `lib/demo/dataset` is safe by construction: its codes ARE
 * the exported pages, so the link always resolves. Measured across `app/`,
 * every other interpolated record link is on such a screen -- the dashboard,
 * the pipeline, and same-record `#anchor` links inside a detail page. Analytics
 * was the one screen reading the API and hand-rolling the link, and it was the
 * one that 404'd.
 *
 * So the predicate is "does this file import from `@/lib/api/`". A screen whose
 * codes come from the server cannot know they have a page; one whose codes come
 * from the bundle already does.
 *
 * It also ignores static hrefs (`/projects/workspace` is a real page) and
 * `#fragment` links, which point within the record already on screen.
 */

const APP = join(__dirname, "..", "..", "app");

function tsxFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...tsxFiles(full));
    else if (entry.endsWith(".tsx") && !entry.includes(".test.")) out.push(full);
  }
  return out;
}

/** `href={`/projects/${something}`}` — an interpolated record code. */
const INTERPOLATED = /href=\{`\/(projects|formulations)\/\$\{[^`]*`\}/g;

/** A screen whose records come from the server rather than from the bundle. */
function readsLiveData(source: string): boolean {
  return source.includes("@/lib/api/");
}

describe("links into a record detail page", () => {
  it("finds the screens it is meant to be checking", () => {
    // The guard on the guard: an empty file list would make the assertion
    // below pass without reading anything.
    const files = tsxFiles(APP);
    expect(files.length).toBeGreaterThan(20);
    // Analytics is the screen this rule was written from, and it must be in
    // scope -- a predicate that excluded it would check nothing that matters.
    const analytics = files.find((f) => f.includes("analytics"));
    expect(analytics).toBeDefined();
    expect(readsLiveData(readFileSync(analytics as string, "utf8"))).toBe(true);
  });

  it("never hand-rolls one, because only RecordLink knows if it exists", () => {
    const offenders: string[] = [];
    for (const file of tsxFiles(APP)) {
      const source = readFileSync(file, "utf8");
      if (!readsLiveData(source)) continue;
      for (const match of source.matchAll(INTERPOLATED)) {
        // A fragment points within the record already rendered, which exists
        // by definition. Only a link to ANOTHER record can 404.
        if (match[0].includes("#")) continue;
        offenders.push(`${file.slice(file.indexOf("app"))}  ${match[0]}`);
      }
    }
    expect(
      offenders,
      "these build a detail-page URL from a code without asking whether the " +
        "page exists — `/projects/[code]` renders from the demonstration " +
        "dataset and 404s for every live record. Use `RecordLink`.",
    ).toEqual([]);
  });
});
