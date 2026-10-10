"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useReducer,
  type ReactNode,
} from "react";

import { type Toast, type ToastTone, toastReducer } from "@/lib/toast-store";

/**
 * P1 overlay surfaces (#172): Modal, Drawer, and a Toast provider/hook. All
 * inherit the global focus-visible ring and reduced-motion guard from #177;
 * Modal/Drawer close on Escape and backdrop click and expose dialog semantics.
 */

function useEscape(active: boolean, onClose: () => void) {
  useEffect(() => {
    if (!active) {
      return;
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, onClose]);
}

export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  useEscape(open, onClose);
  if (!open) {
    return null;
  }
  return (
    <div className="overlay-backdrop" onClick={onClose} role="presentation">
      <div aria-label={title} aria-modal="true" className="modal" onClick={(e) => e.stopPropagation()} role="dialog">
        <header className="modal-head">
          <h2 className="modal-title">{title}</h2>
          <button aria-label="Close dialog" className="overlay-close" onClick={onClose} type="button">
            ✕
          </button>
        </header>
        <div className="modal-body">{children}</div>
        {footer ? <footer className="modal-foot">{footer}</footer> : null}
      </div>
    </div>
  );
}

export function Drawer({
  open,
  onClose,
  title,
  side = "right",
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  side?: "left" | "right";
  children: ReactNode;
  footer?: ReactNode;
}) {
  useEscape(open, onClose);
  if (!open) {
    return null;
  }
  return (
    <div className="overlay-backdrop overlay-backdrop-drawer" onClick={onClose} role="presentation">
      <aside
        aria-label={title}
        aria-modal="true"
        className={`drawer drawer-${side}`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
      >
        <header className="modal-head">
          <h2 className="modal-title">{title}</h2>
          <button aria-label="Close drawer" className="overlay-close" onClick={onClose} type="button">
            ✕
          </button>
        </header>
        <div className="drawer-body">{children}</div>
        {footer ? <footer className="modal-foot">{footer}</footer> : null}
      </aside>
    </div>
  );
}

interface ToastContextValue {
  notify: (toast: { title: string; detail?: string; tone?: ToastTone }) => void;
  dismiss: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const TOAST_DURATION_MS = 5000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, dispatch] = useReducer(toastReducer, [] as Toast[]);

  const dismiss = useCallback((id: string) => dispatch({ type: "dismiss", id }), []);

  const notify = useCallback(
    ({ title, detail, tone = "info" }: { title: string; detail?: string; tone?: ToastTone }) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      dispatch({ type: "push", toast: { id, title, detail, tone } });
      window.setTimeout(() => dispatch({ type: "dismiss", id }), TOAST_DURATION_MS);
    },
    [],
  );

  return (
    <ToastContext.Provider value={{ notify, dismiss }}>
      {children}
      <div aria-live="polite" className="toast-stack">
        {toasts.map((toast) => (
          <div className={`toast toast-${toast.tone}`} key={toast.id} role="status">
            <div className="toast-copy">
              <strong>{toast.title}</strong>
              {toast.detail ? <span>{toast.detail}</span> : null}
            </div>
            <button aria-label="Dismiss notification" className="overlay-close" onClick={() => dismiss(toast.id)} type="button">
              ✕
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}
