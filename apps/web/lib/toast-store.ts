/**
 * Pure toast-queue reducer (#172). Kept DOM-free so the queueing/dismissal
 * logic is unit-tested in isolation; the React provider is a thin wrapper.
 */

export type ToastTone = "neutral" | "info" | "success" | "warning" | "danger";

export interface Toast {
  id: string;
  title: string;
  detail?: string;
  tone: ToastTone;
}

export type ToastAction =
  | { type: "push"; toast: Toast }
  | { type: "dismiss"; id: string };

/** Cap concurrent toasts so the stack never grows unbounded. */
export const MAX_TOASTS = 4;

export function toastReducer(state: Toast[], action: ToastAction): Toast[] {
  switch (action.type) {
    case "push":
      return [...state, action.toast].slice(-MAX_TOASTS);
    case "dismiss":
      return state.filter((toast) => toast.id !== action.id);
    default:
      return state;
  }
}
