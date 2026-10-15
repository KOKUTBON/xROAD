import { describe, expect, it } from "vitest";

import { MAX_TOASTS, type Toast, toastReducer } from "./toast-store";

function toast(id: string): Toast {
  return { id, title: `Toast ${id}`, tone: "info" };
}

describe("toast reducer", () => {
  it("pushes a toast onto the queue", () => {
    expect(toastReducer([], { type: "push", toast: toast("a") })).toEqual([toast("a")]);
  });

  it("dismisses by id", () => {
    const state = [toast("a"), toast("b")];
    expect(toastReducer(state, { type: "dismiss", id: "a" })).toEqual([toast("b")]);
  });

  it("caps the queue at MAX_TOASTS, dropping the oldest", () => {
    let state: Toast[] = [];
    for (let i = 0; i < MAX_TOASTS + 2; i += 1) {
      state = toastReducer(state, { type: "push", toast: toast(String(i)) });
    }
    expect(state).toHaveLength(MAX_TOASTS);
    expect(state[0].id).toBe("2"); // first two dropped
    expect(state[state.length - 1].id).toBe(String(MAX_TOASTS + 1));
  });

  it("ignores dismiss for unknown ids", () => {
    const state = [toast("a")];
    expect(toastReducer(state, { type: "dismiss", id: "zzz" })).toEqual(state);
  });
});
