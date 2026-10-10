"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { useInstitution } from "@/components/institution-provider";
import { WorkspaceIcon } from "@/components/icons";
import { usePlatformSession } from "@/components/session-provider";
import {
  buildNavigation,
  sessionMunicipalities,
  type NavItem,
} from "@/lib/platform-shell";

type Command =
  | { kind: "route"; id: string; label: string; detail: string; href: string }
  | { kind: "city"; id: string; label: string; detail: string; municipalityId: string };

function matches(command: Command, query: string): boolean {
  if (!query) {
    return true;
  }
  const haystack = `${command.label} ${command.detail}`.toLowerCase();
  return query
    .toLowerCase()
    .split(/\s+/)
    .every((term) => haystack.includes(term));
}

/**
 * ⌘K / Ctrl-K command palette (#173): jump to any role-visible route or switch
 * the active municipality. Opens on the keyboard shortcut or the utility-bar
 * trigger, traps focus, and closes on Escape. Rendered once by the workspace
 * shell.
 */
export function CommandPalette() {
  const router = useRouter();
  const { config } = useInstitution();
  const { selectContext, session } = usePlatformSession();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands = useMemo<Command[]>(() => {
    const routes: Command[] = buildNavigation(session, config).map((item: NavItem) => ({
      kind: "route",
      id: `route:${item.href}`,
      label: item.label,
      detail: item.detail,
      href: item.href,
    }));
    const cities: Command[] = sessionMunicipalities(session).map((municipality) => ({
      kind: "city",
      id: `city:${municipality.id}`,
      label: `Switch to ${municipality.name}`,
      detail: `${municipality.regionLabel} · ${municipality.coverageLabel}`,
      municipalityId: municipality.id,
    }));
    return [...routes, ...cities];
  }, [session, config]);

  const filtered = useMemo(
    () => commands.filter((command) => matches(command, query)),
    [commands, query],
  );

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => !value);
      } else if (event.key === "Escape") {
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActiveIndex(0);
      const id = window.setTimeout(() => inputRef.current?.focus(), 0);
      return () => window.clearTimeout(id);
    }
    return undefined;
  }, [open]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  // Expose an opener for the utility-bar trigger via a custom event.
  useEffect(() => {
    function onOpen() {
      setOpen(true);
    }
    window.addEventListener("command-palette:open", onOpen);
    return () => window.removeEventListener("command-palette:open", onOpen);
  }, []);

  if (!open) {
    return null;
  }

  function runCommand(command: Command) {
    setOpen(false);
    if (command.kind === "route") {
      router.push(command.href);
    } else {
      selectContext(session.selectedOrganizationId, command.municipalityId);
    }
  }

  function onListKeyDown(event: React.KeyboardEvent) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => Math.min(index + 1, filtered.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const command = filtered[activeIndex];
      if (command) {
        runCommand(command);
      }
    }
  }

  return (
    <div
      className="command-palette-overlay"
      onClick={() => setOpen(false)}
      role="presentation"
    >
      <div
        aria-label="Command palette"
        aria-modal="true"
        className="command-palette"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <input
          aria-label="Search routes and cities"
          className="command-palette-input"
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={onListKeyDown}
          placeholder="Jump to a workspace or switch city…"
          ref={inputRef}
          type="text"
          value={query}
        />
        <ul className="command-palette-list" role="listbox">
          {filtered.length === 0 ? (
            <li className="command-palette-empty">No matches.</li>
          ) : (
            filtered.map((command, index) => (
              <li key={command.id} role="presentation">
                <button
                  aria-selected={index === activeIndex}
                  className={`command-palette-item${index === activeIndex ? " is-active" : ""}`}
                  onClick={() => runCommand(command)}
                  onMouseEnter={() => setActiveIndex(index)}
                  role="option"
                  type="button"
                >
                  <span className="command-palette-item-icon" aria-hidden="true">
                    {command.kind === "route" ? (
                      <WorkspaceIcon name={command.href.split("/").pop() || "map"} size={18} />
                    ) : (
                      <WorkspaceIcon name="siting-advisor" size={18} />
                    )}
                  </span>
                  <span className="command-palette-item-label">{command.label}</span>
                  <span className="command-palette-item-detail">{command.detail}</span>
                </button>
              </li>
            ))
          )}
        </ul>
        <div className="command-palette-footer">
          <span><kbd>↑</kbd><kbd>↓</kbd> navigate</span>
          <span><kbd>↵</kbd> open</span>
          <span><kbd>esc</kbd> close</span>
        </div>
      </div>
    </div>
  );
}
