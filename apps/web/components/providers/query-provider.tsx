"use client";

/**
 * TanStack Query, for the whole application.
 *
 * `@tanstack/react-query` has been a dependency since Slice 1 and nothing
 * imported it, because nothing fetched anything. This is where that stops.
 *
 * The defaults below are chosen for a product whose records are controlled
 * technical facts, and each one is a decision rather than a copied recipe.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { ApiAuthError, ApiNotConfiguredError, ApiNoSessionError } from "@/lib/api/client";

export function QueryProvider({ children }: { children: ReactNode }): ReactNode {
  // Created in state, not at module scope. A module-level client is shared
  // across every request in a server render, which on a multi-tenant
  // product means one organization's cached rows served to another.
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // A formulation is a controlled record, not a feed. Refetching
            // it because a window regained focus invites the reader to
            // watch a figure change while they are reading it.
            refetchOnWindowFocus: false,

            // Nothing is fresh by default. `staleTime: 0` means a screen
            // re-opened after an approval shows the approval -- the
            // alternative is a chemist looking at a version that says
            // `submitted` after somebody else approved it.
            staleTime: 0,

            // NEVER retry a refusal. 401, 403 and "no API configured" are
            // ANSWERS. Retrying them turns one refusal into four, delays
            // the honest message by several seconds, and -- for a 401 --
            // hammers the identity provider with a token it has already
            // rejected.
            retry: (failureCount, error) => {
              if (
                error instanceof ApiAuthError ||
                error instanceof ApiNotConfiguredError ||
                error instanceof ApiNoSessionError
              ) {
                return false;
              }
              return failureCount < 2;
            },
          },
        },
      }),
  );

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
