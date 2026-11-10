"use client";

import { useEffect, useMemo, useState } from "react";
import { MapPin } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  conflictNotes,
  feeTotal,
  formatScheduleRange,
  parseScheduleFee,
  schedulePlainText,
  writeHashScheduleIds,
  type ScheduleNote,
} from "@/lib/tournament-schedule";
import { mapsQuery, mapsSearchUrl, type Tournament } from "@/lib/tournaments";
import type { Weekend } from "@/lib/tournament-weekends";

function categoryLabel(cat: string): string {
  if (cat === "both") return "7v7 + Flag";
  if (cat === "7v7") return "7v7";
  if (cat === "flag") return "Flag";
  return cat || "—";
}

function categoryClass(cat: string): string {
  if (cat === "7v7") return "border-amber-400/40 bg-amber-400/10 text-amber-200";
  if (cat === "flag") return "border-sky-400/40 bg-sky-400/10 text-sky-200";
  if (cat === "both") return "border-emerald-400/40 bg-emerald-400/10 text-emerald-200";
  return "border-white/15 bg-white/5 text-zinc-300";
}

function copyText(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text);
  return new Promise((resolve, reject) => {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
      resolve();
    } catch (e) {
      reject(e);
    } finally {
      ta.remove();
    }
  });
}

export function TournamentSchedulePanel({
  tournaments,
  scheduleIds,
  onScheduleIds,
  excludedWeekendIds,
  weekends,
  generated,
  open,
  onOpenChange,
}: {
  tournaments: Tournament[];
  scheduleIds: string[];
  onScheduleIds: (ids: string[]) => void;
  excludedWeekendIds: string[];
  weekends: Weekend[];
  generated: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [toast, setToast] = useState<string | null>(null);
  const byId = useMemo(() => {
    const m = new Map<string, Tournament>();
    for (const t of tournaments) m.set(t.id, t);
    return m;
  }, [tournaments]);

  const items = useMemo(() => {
    return scheduleIds
      .map((id) => byId.get(id))
      .filter((t): t is Tournament => Boolean(t))
      .sort(
        (a, b) =>
          a.start_date.localeCompare(b.start_date) || a.name.localeCompare(b.name),
      );
  }, [scheduleIds, byId]);

  const tot = useMemo(() => feeTotal(items), [items]);
  const notes = useMemo(
    () => conflictNotes(items, weekends, excludedWeekendIds),
    [items, weekends, excludedWeekendIds],
  );
  const conflictIds = useMemo(() => {
    const s = new Set<string>();
    for (const n of notes) if (n.type !== "excluded") for (const id of n.ids) s.add(id);
    return s;
  }, [notes]);
  const exclIds = useMemo(() => {
    const s = new Set<string>();
    for (const n of notes) if (n.type === "excluded") for (const id of n.ids) s.add(id);
    return s;
  }, [notes]);

  const plain = useMemo(
    () => schedulePlainText(items, generated, tot.label, notes, categoryLabel),
    [items, generated, tot.label, notes],
  );

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 1800);
    return () => window.clearTimeout(t);
  }, [toast]);

  function remove(id: string) {
    onScheduleIds(scheduleIds.filter((x) => x !== id));
  }

  function clearAll() {
    if (!scheduleIds.length) return;
    if (window.confirm("Clear all tournaments from your schedule?")) onScheduleIds([]);
  }

  async function copySchedule() {
    try {
      await copyText(plain || "My Tournament Schedule\n\n(empty)");
      setToast("Schedule copied");
    } catch {
      setToast("Copy failed");
    }
  }

  async function copyLink() {
    writeHashScheduleIds(scheduleIds);
    try {
      await copyText(window.location.href);
      setToast("Link copied");
    } catch {
      setToast("Copy failed");
    }
  }

  return (
    <>
      <div
        id="schedbar"
        className="fixed inset-x-0 bottom-0 z-40 border-t border-amber-400/35 bg-[#12203a]/95 shadow-[0_-4px_16px_rgba(0,0,0,0.35)] backdrop-blur"
      >
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-2.5 sm:px-6">
          <p className="sum text-sm font-semibold text-zinc-50" id="schedsum">
            {items.length ? (
              <>
                My schedule ({items.length}) – {tot.label}
              </>
            ) : (
              "My schedule (0)"
            )}
          </p>
          <Button type="button" id="opensched" onClick={() => onOpenChange(true)}>
            {items.length ? "View schedule" : "Open schedule"}
          </Button>
        </div>
      </div>

      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent
          id="sched-modal"
          role="dialog"
          tabIndex={-1}
          showCloseButton
          className="max-h-[90vh] w-full overflow-y-auto sm:max-w-4xl"
          initialFocus={() => document.getElementById("sched-modal")}
        >
          <DialogHeader>
            <DialogTitle id="schedtitle">My tournament schedule</DialogTitle>
            <DialogDescription id="schedlead">
              {items.length
                ? `${items.length} tournament${items.length === 1 ? "" : "s"} selected`
                : "No tournaments on your schedule yet. Use “+ Add” on a tournament to add it."}
            </DialogDescription>
          </DialogHeader>
          {notes.length ? (
            <div id="schedwarns" className="space-y-1.5">
              {notes.map((n) => (
                <p
                  key={n.text}
                  className={
                    n.type === "excluded"
                      ? "rounded-md border border-red-400/40 bg-red-400/10 px-2 py-1.5 text-sm text-red-100"
                      : "rounded-md border border-amber-400/40 bg-amber-400/10 px-2 py-1.5 text-sm text-amber-100"
                  }
                >
                  {n.text}
                </p>
              ))}
            </div>
          ) : null}
          <div id="schedbody">
            {items.length === 0 ? (
              <p className="empty py-8 text-center text-sm text-zinc-400">Your schedule is empty.</p>
            ) : (
              <ScheduleTable
                items={items}
                tot={tot.label}
                conflictIds={conflictIds}
                exclIds={exclIds}
                onRemove={remove}
              />
            )}
          </div>
          <DialogFooter className="flex-wrap gap-2 sm:justify-between">
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" id="copysched" onClick={() => void copySchedule()}>
                Copy schedule
              </Button>
              <Button type="button" variant="outline" id="copylink" onClick={() => void copyLink()}>
                Copy link
              </Button>
              <Button
                type="button"
                variant="outline"
                id="printsched"
                onClick={() => {
                  window.print();
                }}
              >
                Print / Save as PDF
              </Button>
              <Button type="button" variant="outline" id="clearsched" onClick={clearAll}>
                Clear schedule
              </Button>
            </div>
            <Button type="button" id="closesched" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <PrintSchedule items={items} tot={tot.label} notes={notes} generated={generated} />

      {toast ? (
        <p
          role="status"
          className="fixed bottom-20 left-1/2 z-50 -translate-x-1/2 rounded-md bg-zinc-50 px-3 py-1.5 text-sm font-medium text-zinc-950 shadow-lg"
        >
          {toast}
        </p>
      ) : null}
    </>
  );
}

function ScheduleTable({
  items,
  tot,
  conflictIds,
  exclIds,
  onRemove,
}: {
  items: Tournament[];
  tot: string;
  conflictIds: Set<string>;
  exclIds: Set<string>;
  onRemove: (id: string) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-white/10">
      <table className="sched-table w-full text-left text-[13px]">
        <thead>
          <tr className="border-b border-white/10 text-[11px] uppercase tracking-wide text-zinc-400">
            <th className="px-3 py-2 font-medium">Date</th>
            <th className="px-3 py-2 font-medium">Tournament</th>
            <th className="px-3 py-2 font-medium">City</th>
            <th className="px-3 py-2 font-medium">Format</th>
            <th className="px-3 py-2 font-medium">Fee</th>
            <th className="px-3 py-2 font-medium" />
          </tr>
        </thead>
        <tbody>
          {items.map((r) => {
            const f = parseScheduleFee(r.entry_fee);
            const q = mapsQuery(r);
            const rowClass = exclIds.has(r.id)
              ? "excluded bg-red-400/10"
              : conflictIds.has(r.id)
                ? "conflict bg-amber-400/10"
                : "";
            return (
              <tr key={r.id} className={`border-b border-white/8 ${rowClass}`}>
                <td className="whitespace-nowrap px-3 py-2 font-mono text-zinc-300">
                  {formatScheduleRange(r.start_date, r.end_date)}
                </td>
                <td className="px-3 py-2">
                  <span className="mr-1.5 inline-flex align-middle">
                    <Badge variant="outline" className={categoryClass(r.category)}>
                      {r.category === "flag" ? "FLAG" : categoryLabel(r.category)}
                    </Badge>
                  </span>
                  <a
                    href={r.event_url}
                    target="_blank"
                    rel="noreferrer"
                    className="font-medium text-sky-300 hover:text-amber-300"
                  >
                    {r.name}
                  </a>
                </td>
                <td className="px-3 py-2">
                  {q ? (
                    <a
                      href={mapsSearchUrl(q)}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-sky-300 hover:text-amber-300"
                    >
                      <MapPin className="size-3 text-amber-300" aria-hidden />
                      {r.city || "Map"}
                    </a>
                  ) : (
                    <span>{r.city || "—"}</span>
                  )}
                </td>
                <td className="px-3 py-2 text-zinc-300">{categoryLabel(r.category)}</td>
                <td className="whitespace-nowrap px-3 py-2 font-mono text-zinc-200">{f.label}</td>
                <td className="px-3 py-2">
                  <Button type="button" variant="outline" size="xs" data-rm={r.id} onClick={() => onRemove(r.id)}>
                    Remove
                  </Button>
                </td>
              </tr>
            );
          })}
          <tr className="total-row bg-[#0f1a2e] text-sm font-semibold">
            <td className="px-3 py-3" colSpan={4}>
              Total
            </td>
            <td className="whitespace-nowrap px-3 py-3 font-mono">{tot}</td>
            <td />
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function PrintSchedule({
  items,
  tot,
  notes,
  generated,
}: {
  items: Tournament[];
  tot: string;
  notes: ScheduleNote[];
  generated: string;
}) {
  return (
    <section id="print-sched" aria-hidden="true">
      <h1>My Tournament Schedule</h1>
      <p className="meta">FridayRadar tournaments · {generated || ""}</p>
      {items.length ? (
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Tournament</th>
              <th>City</th>
              <th>Format</th>
              <th>Fee</th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.id}>
                <td>{formatScheduleRange(r.start_date, r.end_date)}</td>
                <td>
                  {r.name}
                  {r.event_url ? <div className="meta">{r.event_url}</div> : null}
                </td>
                <td>{r.city || "—"}</td>
                <td>{categoryLabel(r.category)}</td>
                <td>{parseScheduleFee(r.entry_fee).label}</td>
              </tr>
            ))}
            <tr className="total">
              <td colSpan={4}>Total</td>
              <td>{tot}</td>
            </tr>
          </tbody>
        </table>
      ) : (
        <p>Your schedule is empty.</p>
      )}
      {notes.map((n) => (
        <p key={n.text} className="w">
          {n.text}
        </p>
      ))}
    </section>
  );
}
