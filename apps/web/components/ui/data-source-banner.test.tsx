/**
 * @vitest-environment jsdom
 *
 * I98 — the shared read-path error component threw the server's sentence away.
 *
 * `apiRequest` throws `ApiError` whose `.message` is deliberately generic —
 * "the API refused this request (403)" — and puts the server's own
 * explanation in `.detail`. `serverMessage()` exists to read it. Four WRITE
 * screens were converted on 2026-08-24 (I91); `DataSourceError` was not, and
 * it is called from FIFTEEN sites across eleven screens, so every failed
 * READ in the product showed a status code instead of the reason.
 * (I first said nineteen. Codex counted it and I had included the import
 * lines -- the same "check the claim, do not believe it" that found I90.)
 *
 * Neither reviewer found the defect itself: Codex was asked directly and
 * answered NONE, because it matched the literal `.error.message` and the
 * component reads `{error.message}`.
 *
 * These tests are written to FAIL against the unfixed code, and each was
 * watched failing before the fix went in:
 *
 *   `{error.message}` in the component        -> 2 failed, 1 passed
 *   `detail instanceof Error` guard removed   -> 1 failed, 3 passed
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  ApiError,
  ApiShapeError,
  ApiUnreachableError,
} from "@/lib/api/client";

import { DataSourceError } from "./data-source-banner";

// `globals` is false in vitest.config.ts, so @testing-library/react never
// registers its automatic afterEach cleanup and every render accumulates in
// the same document. Left out, a later assertion matches an EARLIER test's
// output -- which is how a test can pass while proving nothing.
afterEach(cleanup);

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

describe("DataSourceError — errors whose detail is not a response body", () => {
  it("keeps the deliberate sentence when the API is unreachable", () => {
    // 🔴 `ApiUnreachableError` stores the CAUGHT EXCEPTION as `detail`, not a
    // FastAPI body. A TypeError is an object with a `.message`, so a naive
    // `serverMessage` mines it and renders the browser's raw "Failed to
    // fetch" -- discarding the one sentence the class exists to produce.
    //
    // client.ts says it plainly: a CORS refusal and an offline network "mean
    // the same thing to the reader ... reported as one state rather than
    // guessed between". "Failed to fetch" is the guess.
    //
    // This is the most common error on a tunnelled demo, so it is the one a
    // reader is most likely to meet.
    const error = new ApiUnreachableError(new TypeError("Failed to fetch"));

    render(<DataSourceError error={error} />);

    expect(screen.getByText(/the API could not be reached/)).toBeDefined();
    expect(screen.queryByText(/Failed to fetch/)).toBeNull();
  });

  it("keeps the contract-mismatch sentence when the response is the wrong shape", () => {
    // Same trap, second class -- raised by Codex against the first fix.
    // `ApiShapeError`'s detail is whatever `response.json()` or the parser
    // threw: a SyntaxError, or a ZodError. Both are `Error`s, so both would
    // have had their raw internal text mined and shown to a chemist in place
    // of the sentence explaining that the client and server disagree.
    const error = new ApiShapeError(
      "/api/formulations",
      new SyntaxError("Unexpected token < in JSON at position 0"),
    );

    render(<DataSourceError error={error} />);

    expect(
      screen.getByText(/the client and the server disagree about this endpoint/),
    ).toBeDefined();
    expect(screen.queryByText(/Unexpected token/)).toBeNull();
  });
});
