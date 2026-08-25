/**
 * @vitest-environment jsdom
 *
 * I98 — the shared read-path error component threw the server's sentence away.
 *
 * `apiRequest` throws `ApiError` whose `.message` is deliberately generic —
 * "the API refused this request (403)" — and puts the server's own
 * explanation in `.detail`. `serverMessage()` exists to read it. Four WRITE
 * screens were converted on 2026-08-24 (I91); `DataSourceError` was not, and
 * it is called from nineteen sites across eleven screens, so every failed
 * READ in the product showed a status code instead of the reason.
 *
 * Neither reviewer found it: Codex was asked directly and answered NONE,
 * because it matched the literal `.error.message` and the component reads
 * `{error.message}`.
 *
 * These tests are written to FAIL against the unfixed component. Verified:
 * with `{error.message}` in place, the first two fail and the third passes.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api/client";

import { DataSourceError } from "./data-source-banner";

describe("DataSourceError", () => {
  it("shows the server's own explanation, not the generic status message", () => {
    // Exactly what `apiRequest` builds for a 403: a generic message, and the
    // sentence that matters wrapped in FastAPI's `{"detail": ...}` envelope.
    const error = new ApiError("the API refused this request (403)", 403, {
      detail: "You are not a member of this project.",
    });

    render(<DataSourceError error={error} />);

    expect(
      screen.getByText(/You are not a member of this project\./),
    ).toBeDefined();
    expect(screen.queryByText(/the API refused this request/)).toBeNull();
  });

  it("lists EVERY block of a refusal, not just the first", () => {
    // A blocked submission answers with a message plus a block list. Rendering
    // `.message` discarded the blocks wholesale -- the defect I91 recorded.
    const error = new ApiError("the API refused this request (422)", 422, {
      detail: {
        message: "This formula cannot be submitted",
        blocks: [
          { code: "SDS_MISSING", message: "RM-107 has no usable SDS" },
          { code: "SUM_NOT_100", message: "components total 98.4%" },
        ],
      },
    });

    render(<DataSourceError error={error} />);

    expect(screen.getByText(/RM-107 has no usable SDS/)).toBeDefined();
    expect(screen.getByText(/components total 98\.4%/)).toBeDefined();
  });

  it("still renders a plain Error's message, so nothing regresses", () => {
    // `serverMessage` falls back rather than inventing one. A network failure
    // is not an ApiError and must keep reading exactly as it did.
    render(<DataSourceError error={new Error("the API could not be reached")} />);

    expect(screen.getByText(/the API could not be reached/)).toBeDefined();
  });
});
