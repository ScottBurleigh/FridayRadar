"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

type Item = { value: string; label: string; count?: number };

export function MultiSelect({
  id,
  label,
  items,
  selected,
  onChange,
  searchable = false,
  open,
  onOpenChange,
}: {
  id: string;
  label: string;
  items: Item[];
  selected: string[];
  onChange: (next: string[]) => void;
  searchable?: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [q, setQ] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);
  const searchId = useId();
  const sel = useMemo(() => new Set(selected), [selected]);
  const needle = q.trim().toLowerCase();
  const visible = needle
    ? items.filter((it) => it.label.toLowerCase().includes(needle) || it.value.toLowerCase().includes(needle))
    : items;

  const summary =
    selected.length === 0
      ? `All ${label.toLowerCase()}`
      : selected.length === 1
        ? (items.find((it) => it.value === selected[0])?.label ?? selected[0])
        : `${selected.length} ${label.toLowerCase()} selected`;

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) onOpenChange(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onOpenChange(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, onOpenChange]);

  function toggle(value: string) {
    if (sel.has(value)) onChange(selected.filter((v) => v !== value));
    else onChange([...selected, value]);
  }

  function selectVisible() {
    const next = new Set(selected);
    for (const it of visible) next.add(it.value);
    onChange([...next]);
  }

  function clear() {
    setQ("");
    onChange([]);
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        id={id}
        type="button"
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => onOpenChange(!open)}
        className={`relative mt-1 flex h-8 w-full items-center justify-between gap-2 rounded-lg border border-amber-200/45 bg-[#0f1a2e] px-2.5 text-left text-sm text-zinc-50 ${
          selected.length ? "border-amber-300/70 font-medium text-amber-100" : ""
        }`}
      >
        <span className="truncate">{summary}</span>
        <ChevronDown className="size-3.5 shrink-0 text-zinc-400" aria-hidden />
      </button>
      {open ? (
        <div
          role="listbox"
          aria-multiselectable="true"
          aria-labelledby={id}
          className="absolute z-30 mt-1 min-w-full w-max max-w-[min(20rem,92vw)] rounded-lg border border-amber-200/45 bg-[#0f1a2e] p-2 shadow-xl"
        >
          {searchable ? (
            <input
              id={searchId}
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={`Search ${label.toLowerCase()}…`}
              className="mb-2 h-8 w-full rounded-md border border-amber-200/35 bg-[#17233d] px-2 text-sm text-zinc-100 placeholder:text-zinc-500"
            />
          ) : null}
          <div className="mb-2 flex gap-2">
            <button
              type="button"
              className="rounded-md border border-amber-200/35 px-2 py-1 text-xs text-zinc-200 hover:bg-amber-400/10"
              onClick={selectVisible}
            >
              Select all
            </button>
            <button
              type="button"
              className="rounded-md border border-amber-200/35 px-2 py-1 text-xs text-zinc-200 hover:bg-amber-400/10"
              onClick={clear}
            >
              Clear
            </button>
          </div>
          <ul className="max-h-64 overflow-auto">
            {visible.length === 0 ? (
              <li className="px-1 py-2 text-xs text-zinc-500">No matches</li>
            ) : (
              visible.map((it) => {
                const checked = sel.has(it.value);
                return (
                  <li key={it.value}>
                    <label className="flex cursor-pointer items-center gap-2 rounded-md px-1 py-1 text-sm text-zinc-100 hover:bg-amber-400/10">
                      <input
                        type="checkbox"
                        className="size-3.5 accent-amber-400"
                        checked={checked}
                        onChange={() => toggle(it.value)}
                      />
                      <span className="min-w-0 flex-1 truncate">{it.label}</span>
                      {it.count != null ? (
                        <span className="font-mono text-[11px] text-zinc-500">({it.count})</span>
                      ) : null}
                    </label>
                  </li>
                );
              })
            )}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
