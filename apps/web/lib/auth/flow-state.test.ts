/**
 * The flow store, attacked rather than exercised.
 *
 * Every assertion here corresponds to a defect Codex found in review of
 * the first implementation. None of them would have failed loudly in
 * production; each would have presented as "sign-in is broken" with
 * nothing to go on.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { saveFlow, takeFlow } from "./flow-state";
import type { PkceChallenge } from "./pkce";

const CHALLENGE: PkceChallenge = {
  verifier: "the-verifier-that-must-survive-one-redirect",
  challenge: "the-hash",
  state: "the-state",
};

/** A sessionStorage stand-in whose methods can be made to misbehave. */
function installStorage(overrides: Partial<Storage> = {}): Map<string, string> {
  const data = new Map<string, string>();
  const store = {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
    clear: () => data.clear(),
    key: () => null,
    get length() {
      return data.size;
    },
    ...overrides,
  } as Storage;
  vi.stubGlobal("window", { sessionStorage: store });
  return data;
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("saveFlow", () => {
  it("stores the flow and reports success", () => {
    const data = installStorage();
    expect(saveFlow(CHALLENGE, "/materials")).toBe(true);
    expect(data.size).toBe(1);
  });

  it("🔴 REPORTS FAILURE when storage is unavailable", () => {
    // It used to return void and give up silently. signIn() then
    // redirected anyway, the user authenticated for real, and the
    // callback failed with "no sign-in was in progress" -- forever, with
    // no way forward. Safari private mode and locked-down enterprise
    // profiles both produce this.
    vi.stubGlobal("window", {
      get sessionStorage(): Storage {
        throw new Error("SecurityError: storage is disabled");
      },
    });
    expect(saveFlow(CHALLENGE, "/materials")).toBe(false);
  });

  it("🔴 REPORTS FAILURE when the write itself throws", () => {
    // Storage can be present at the probe and refuse the write -- quota,
    // or access revoked in between.
    installStorage({
      setItem: () => {
        throw new Error("QuotaExceededError");
      },
    });
    expect(saveFlow(CHALLENGE, "/materials")).toBe(false);
  });
});

describe("takeFlow", () => {
  it("returns the flow and clears it in the same breath", () => {
    const data = installStorage();
    saveFlow(CHALLENGE, "/materials");

    const first = takeFlow();
    expect(first?.verifier).toBe(CHALLENGE.verifier);
    expect(first?.returnTo).toBe("/materials");
    expect(data.size).toBe(0);

    // Take-ONCE. A verifier that survives its exchange can be replayed
    // against a second intercepted code.
    expect(takeFlow()).toBeNull();
  });

  it("🔴 STILL CLEARS when removeItem throws", () => {
    // getItem and removeItem used to sit outside the try. A SecurityError
    // from removeItem left the verifier stored AND threw out of the
    // callback as an unhandled rejection, so the page never reached the
    // state check or its failure message.
    let removeCalled = false;
    installStorage({
      removeItem: () => {
        removeCalled = true;
        throw new Error("SecurityError");
      },
    });
    saveFlow(CHALLENGE, "/materials");

    expect(() => takeFlow()).not.toThrow();
    expect(removeCalled).toBe(true);
  });

  it("returns null rather than throwing when the read throws", () => {
    installStorage({
      getItem: () => {
        throw new Error("SecurityError");
      },
    });
    expect(takeFlow()).toBeNull();
  });

  it("refuses a stored value missing either secret", () => {
    const data = installStorage();
    // A half-written or tampered entry must not produce a flow whose
    // state check then compares undefined to undefined and passes.
    data.set("evercoat.auth.flow", JSON.stringify({ verifier: "v" }));
    expect(takeFlow()).toBeNull();
  });

  it("returns null on unparseable JSON", () => {
    const data = installStorage();
    data.set("evercoat.auth.flow", "{not json");
    expect(takeFlow()).toBeNull();
  });

  it("is a no-op with no DOM at all", () => {
    // The static export is prerendered in Node, where window is absent.
    vi.stubGlobal("window", undefined);
    expect(takeFlow()).toBeNull();
    expect(saveFlow(CHALLENGE, "/x")).toBe(false);
  });
});
