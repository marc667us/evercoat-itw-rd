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
export const API_UNCONFIGURED_REASON =
  "this build was compiled without an API address, so the figures below come " +
  "from the demonstration dataset rather than from a database";

/**
 * The two things a screen can be showing. Every hook returns one of them
 * and every page frame renders it.
 *
 * A third state is deliberately absent: there is no "unknown". A screen
 * that cannot say where its numbers came from must not display numbers.
 */
export type DataSource = "live" | "demonstration";
