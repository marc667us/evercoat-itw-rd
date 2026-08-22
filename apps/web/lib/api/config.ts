/**
 * Where the API is, and whether there is one.
 *
 * 🔴 `NEXT_PUBLIC_*` IS READ AT BUILD TIME, NOT AT RUNTIME.
 *
 * Next.js inlines these into the bundle when it compiles. Setting
 * `NEXT_PUBLIC_API_BASE_URL` on a running container changes nothing; the
 * value baked in at `next build` is the value the browser uses forever.
 * This platform has already been bitten by exactly that
 * (`feedback: NEXT_PUBLIC_ is BUILD-time, not runtime`), so it is stated
 * here rather than assumed known — pointing the deployed site at a
 * different API means REBUILDING it.
 *
 * WHY AN EMPTY VALUE IS A FIRST-CLASS STATE, NOT AN ERROR
 * -------------------------------------------------------
 * The deployed site is a Render STATIC SITE with no API beside it, and no
 * identity provider anywhere. So "no API configured" is the normal
 * condition of the live deployment today, not a misconfiguration.
 *
 * That makes it dangerous. A page that silently rendered demonstration
 * figures whenever the API was unreachable would look identical to a
 * working product — and this project has already shipped one defect of
 * exactly that shape, where an empty requirement set rendered "ALL
 * REQUIREMENTS PASSED". Absence must never present as success.
 *
 * So the state is NAMED and carried through the whole stack: every hook
 * returns which source its data came from, and every page renders a
 * banner saying so. There is no code path in which live and demonstration
 * data look the same to a reader.
 */

/**
 * The API's origin, without a trailing slash, or `null` when this build
 * was compiled without one.
 */
export const API_BASE_URL: string | null =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") || null;

/** True when this build knows where the API is. */
export const isApiConfigured: boolean = API_BASE_URL !== null;

/**
 * Why the API is not configured, in words a reader can act on.
 *
 * Rendered to the user, so it says what is true of the deployment rather
 * than naming an environment variable they cannot set.
 */
// 🔴 THE CAUSE ONLY. THE CONSEQUENCE BELONGS TO THE FRAME THAT RENDERS IT.
//
// This used to end "...so the figures below come from the demonstration
// dataset rather than from a database", which is true on a `DataPage` and
// FALSE on a `LiveOnlyPage` -- Knowledge, Laboratory and Testing show NOTHING
// rather than a fixture. On those three the deployed page read:
//
//     ...so the figures below come from the demonstration dataset rather than
//     from a database. This screen has no demonstration equivalent: ...
//     nothing is shown rather than something synthetic.
//
// Two sentences contradicting each other, in the one banner whose entire job
// is to tell the reader what they are looking at. Found by loading the
// DEPLOYED page and reading it -- no test noticed, because every test asserts
// the notice is PRESENT and none asserts it is COHERENT.
//
// `DataSourceBanner` already prints the heading "Demonstration data" above
// this, and `LiveOnlyPage` already adds its own "no demonstration equivalent"
// clause, so each frame states its own consequence and neither needs this
// string to guess which one is rendering it.
export const API_UNCONFIGURED_REASON =
  "this build was compiled without an API address";

/**
 * The two things a screen can be showing. Every hook returns one of them
 * and every page frame renders it.
 *
 * A third state is deliberately absent: there is no "unknown". A screen
 * that cannot say where its numbers came from must not display numbers.
 */
export type DataSource = "live" | "demonstration";
