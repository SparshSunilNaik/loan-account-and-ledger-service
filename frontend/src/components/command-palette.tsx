"use client";
import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Command, Search, X } from "lucide-react";
import { session, useStudio } from "@/lib/session";
import { workbenchCommand, type WorkbenchAction } from "@/lib/workbench-state";
export function CommandPalette() {
  const { selectedLoan, actor, recent } = useStudio();
  const router = useRouter();
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [index, setIndex] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  function show(value: boolean) {
    setOpen(value);
    if (value) {
      setSearch("");
      setIndex(0);
    }
  }
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((v) => !v);
        setSearch("");
        setIndex(0);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  function account(action: WorkbenchAction) {
    if (
      path === `/loans/${selectedLoan}` ||
      (path === "/new-loan" &&
        !!document.querySelector(".originated-account .loan-workbench"))
    )
      workbenchCommand(action);
    else
      router.push(
        `/loans/${selectedLoan}?tab=${action === "payment" || action === "refresh" ? "schedule" : action}`,
      );
  }
  const actions = [
    ...(actor !== "demo-auditor"
      ? [
          {
            label: "Create a new loan",
            detail: "Borrower and terms",
            run: () => router.push("/new-loan"),
          },
        ]
      : []),
    ...(
      [
        "schedule",
        "repayments",
        "ledger",
        ...(actor !== "demo-officer" ? ["history"] : []),
      ] as WorkbenchAction[]
    )
      .filter(() => !!selectedLoan)
      .map((action) => ({
        label: `Open ${action === "history" ? "audit history" : action}`,
        detail: "Current loan",
        run: () => account(action),
      })),
    {
      label: "Open testing workspace",
      detail: "Advanced delivery checks and guided demo",
      run: () => router.push("/testing"),
    },
    ...recent.map((r) => ({
      label: `Open ${r.reference}`,
      detail: "Known in this browser session",
      run: () => {
        session.select(r.id);
        router.push(`/loans/${r.id}`);
      },
    })),
  ].filter((a) =>
    `${a.label} ${a.detail}`.toLowerCase().includes(search.toLowerCase()),
  );
  useEffect(() => {
    if (open)
      document
        .getElementById(`command-${index}`)
        ?.scrollIntoView({ block: "nearest" });
  }, [index, search, open]);
  function execute(i: number) {
    const action = actions[i];
    if (!action) return;
    show(false);
    action.run();
  }
  return (
    <>
      <button
        className="command-trigger icon-button"
        aria-label="Open command palette"
        title="Commands (⌘K / Ctrl+K)"
        onClick={() => show(true)}
      >
        <Command size={16} aria-hidden="true" />
        <kbd> K</kbd>
      </button>
      <Dialog.Root open={open} onOpenChange={show}>
        <Dialog.Portal>
          <Dialog.Overlay className="dialog-overlay" />
          <Dialog.Content
            className="command-palette"
            onOpenAutoFocus={(e) => {
              e.preventDefault();
              input.current?.focus();
            }}
          >
            <Dialog.Title className="sr-only">Workbench commands</Dialog.Title>
            <Dialog.Description className="command-hint">
              Actions and locally known loans. This does not search the
              database.
            </Dialog.Description>
            <div className="command-search">
              <Search size={18} aria-hidden="true" />
              <input
                ref={input}
                aria-label="Search commands and known loans"
                role="combobox"
                aria-autocomplete="list"
                aria-expanded="true"
                aria-controls="command-results"
                aria-activedescendant={
                  actions.length
                    ? `command-${Math.min(index, actions.length - 1)}`
                    : undefined
                }
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setIndex(0);
                }}
                onKeyDown={(e) => {
                  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
                    e.preventDefault();
                    setIndex((i) =>
                      actions.length
                        ? (i +
                            (e.key === "ArrowDown" ? 1 : -1) +
                            actions.length) %
                          actions.length
                        : 0,
                    );
                  }
                  if (e.key === "Enter") {
                    e.preventDefault();
                    execute(Math.min(index, actions.length - 1));
                  }
                }}
                placeholder="Find a command or recent reference…"
              />
              <Dialog.Close className="icon-button" aria-label="Close commands">
                <X size={16} />
              </Dialog.Close>
            </div>
            <div
              id="command-results"
              role="listbox"
              aria-label="Matching commands"
              className="command-results"
            >
              {actions.map((action, i) => (
                <button
                  id={`command-${i}`}
                  key={action.label}
                  role="option"
                  aria-selected={i === Math.min(index, actions.length - 1)}
                  tabIndex={-1}
                  onPointerMove={() => setIndex(i)}
                  onClick={() => execute(i)}
                >
                  <span>{action.label}</span>
                  <small>{action.detail}</small>
                </button>
              ))}
              {!actions.length && (
                <p className="page-note">
                  No matching command or session reference.
                </p>
              )}
            </div>
            <p className="command-hint">
              ↑ ↓ Select · Enter Open · Esc Close
              {actor === "demo-officer"
                ? " · Audit history requires manager or auditor."
                : actor === "demo-auditor"
                  ? " · Auditor is read-only."
                  : ""}
            </p>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
