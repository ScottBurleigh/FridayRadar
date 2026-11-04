"use client";

import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, ExternalLink, MapPin, Navigation } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MultiSelect } from "@/components/multi-select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  compareDivisionBuckets,
  divisionBuckets,
  mapsDirectionsUrl,
  mapsQuery,
  mapsSearchUrl,
  parseEntryFeeUsd,
  type Tournament,
} from "@/lib/tournaments";

type FormatFilter = "all" | "7v7" | "flag";
type SortKey =
  | "start_date"
  | "name"
  | "city"
  | "category"
  | "entry_fee"
  | "registration_ends"
  | "organizer";
type OpenFilter = "div" | "city" | "month" | null;

const MONTH_LABEL = new Intl.DateTimeFormat("en-US", {
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

function formatIsoDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso || "—";
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

function formatRange(start: string, end: string): string {
  if (!start) return "—";
  if (!end || end === start) return formatIsoDate(start);
  return `${formatIsoDate(start)} – ${formatIsoDate(end)}`;
}

function monthKey(iso: string): string {
  return iso.slice(0, 7);
}

function monthLabel(ym: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(ym);
  if (!m) return ym;
  return MONTH_LABEL.format(new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, 1)));
}

function matchesFormat(t: Tournament, format: FormatFilter, excludeBoth: boolean): boolean {
  if (format === "all") return true;
  if (t.category === "both") return !excludeBoth;
  return t.category === format;
}

function isClone(t: Tournament): boolean {
  return (t.name || "").toLowerCase().includes("(clone)");
}

function categoryLabel(cat: string): string {
  if (cat === "both") return "7v7 + Flag";
  if (cat === "7v7") return "7v7";
  if (cat === "flag") return "Flag";
  return cat || "—";
}

function openDivisionText(t: Tournament): string {
  if (t.open_divisions && t.open_divisions.length) return t.open_divisions.join("; ");
  return t.divisions || t.age_groups || "—";
}

function EventMeta({ t }: { t: Tournament }) {
  const flag50 = (t.flag50_url || "").trim();
  const girls = (t.girls_divisions || []).join("; ");
  return (
    <div className="mt-1 flex flex-wrap items-center gap-1.5">
      {t.verified ? (
        <Badge
          variant="outline"
          className="border-emerald-400/50 bg-emerald-400/10 text-[10px] font-medium uppercase tracking-wide text-emerald-200"
        >
          Verified on Zorts + Flag50
        </Badge>
      ) : null}
      {t.has_girls_divisions ? (
        <Badge
          variant="outline"
          title={girls || undefined}
          className="border-pink-400/50 bg-pink-400/10 text-[10px] font-medium uppercase tracking-wide text-pink-200"
        >
          + girls divisions
        </Badge>
      ) : null}
      {flag50 ? (
        <a
          href={flag50}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-[11px] text-sky-300 hover:text-amber-300"
        >
          Flag50
          <ExternalLink className="size-3" aria-hidden />
        </a>
      ) : null}
    </div>
  );
}

function CityLinks({ t }: { t: Tournament }) {
  const query = mapsQuery(t);
  const label = t.city || (query ? "Map" : "—");
  if (!query) return <span className="font-sans text-zinc-200">{label}</span>;
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-0.5">
      <a
        href={mapsSearchUrl(query)}
        target="_blank"
        rel="noreferrer"
        title="Open in Google Maps"
        className="inline-flex items-center gap-1 text-zinc-100 hover:text-amber-300"
      >
        <MapPin className="size-3 shrink-0 text-amber-300" aria-hidden />
        {label}
      </a>
      <a
        href={mapsDirectionsUrl(query)}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1 text-[11px] text-sky-300 hover:text-amber-300"
      >
        <Navigation className="size-3" aria-hidden />
        Directions
      </a>
    </span>
  );
}

function categoryClass(cat: string): string {
  if (cat === "7v7") return "border-amber-400/40 bg-amber-400/10 text-amber-200";
  if (cat === "flag") return "border-sky-400/40 bg-sky-400/10 text-sky-200";
  if (cat === "both") return "border-emerald-400/40 bg-emerald-400/10 text-emerald-200";
  return "border-white/15 bg-white/5 text-zinc-300";
}

function compare(a: Tournament, b: Tournament, key: SortKey): number {
  if (key === "entry_fee") {
    const fa = parseEntryFeeUsd(a.entry_fee);
    const fb = parseEntryFeeUsd(b.entry_fee);
    if (fa == null && fb == null) return 0;
    if (fa == null) return 1;
    if (fb == null) return -1;
    return fa - fb;
  }
  const av = (a[key] || "").toString();
  const bv = (b[key] || "").toString();
  return av.localeCompare(bv, "en", { sensitivity: "base", numeric: true });
}

function SortButton({
  label,
  active,
  dir,
  onClick,
  align = "left",
}: {
  label: string;
  active: boolean;
  dir: "asc" | "desc";
  onClick: () => void;
  align?: "left" | "right";
}) {
  const Icon = active ? (dir === "asc" ? ArrowUp : ArrowDown) : ArrowUpDown;
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1 font-medium text-zinc-300 hover:text-amber-200 ${
        align === "right" ? "ml-auto" : ""
      }`}
    >
      {label}
      <Icon className="size-3.5" aria-hidden />
    </button>
  );
}

export function TournamentsBoard({
  tournaments,
  generated,
  fileCount,
}: {
  tournaments: Tournament[];
  generated: string;
  fileCount: number;
}) {
  const [q, setQ] = useState("");
  const [format, setFormat] = useState<FormatFilter>("all");
  const [citiesSel, setCitiesSel] = useState<string[]>([]);
  const [state, setState] = useState("");
  const [monthsSel, setMonthsSel] = useState<string[]>([]);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [maxFee, setMaxFee] = useState("");
  const [divsSel, setDivsSel] = useState<string[]>([]);
  const [hideGirls, setHideGirls] = useState(false);
  const [hideClone, setHideClone] = useState(true);
  const [excludeBoth, setExcludeBoth] = useState(false);
  const [openMs, setOpenMs] = useState<OpenFilter>(null);
  const [sortKey, setSortKey] = useState<SortKey>("start_date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const bucketsById = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const t of tournaments) m.set(t.id, divisionBuckets(t));
    return m;
  }, [tournaments]);

  const states = useMemo(() => {
    const s = new Set<string>();
    for (const t of tournaments) if (t.state) s.add(t.state);
    return [...s].sort((a, b) => a.localeCompare(b));
  }, [tournaments]);
  const showStateFilter = states.length > 1;

  const cityItems = useMemo(() => {
    const s = new Set<string>();
    for (const t of tournaments) s.add(t.city || "(unspecified)");
    return [...s].sort((a, b) => a.localeCompare(b)).map((value) => ({ value, label: value }));
  }, [tournaments]);

  const monthItems = useMemo(() => {
    const s = new Set<string>();
    for (const t of tournaments) if (t.start_date) s.add(monthKey(t.start_date));
    return [...s].sort().map((value) => ({ value, label: monthLabel(value) }));
  }, [tournaments]);

  const divItems = useMemo(() => {
    const s = new Set<string>();
    for (const t of tournaments) for (const d of bucketsById.get(t.id) || []) s.add(d);
    return [...s].sort(compareDivisionBuckets).map((value) => ({ value, label: value }));
  }, [tournaments, bucketsById]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const cap = maxFee.trim() === "" ? null : Number(maxFee);
    const feeCap = cap != null && Number.isFinite(cap) ? cap : null;
    const citySet = new Set(citiesSel);
    const monthSet = new Set(monthsSel);
    const divSet = new Set(divsSel);
    const rows = tournaments.filter((t) => {
      if (!matchesFormat(t, format, excludeBoth)) return false;
      if (hideGirls && t.has_girls_divisions) return false;
      if (hideClone && isClone(t)) return false;
      if (state && t.state !== state) return false;
      if (citySet.size && !citySet.has(t.city || "(unspecified)")) return false;
      if (monthSet.size && !monthSet.has(monthKey(t.start_date))) return false;
      if (divSet.size) {
        const buckets = bucketsById.get(t.id) || [];
        if (!buckets.some((d) => divSet.has(d))) return false;
      }
      if (from && (t.end_date || t.start_date || "") < from) return false;
      if (to && (t.start_date || "") > to) return false;
      if (feeCap != null) {
        const fee = parseEntryFeeUsd(t.entry_fee);
        if (fee == null || fee > feeCap) return false;
      }
      if (needle) {
        const blob = [t.name, t.city, t.venue, t.organizer, t.sport, t.divisions, t.age_groups]
          .join(" ")
          .toLowerCase();
        if (!blob.includes(needle)) return false;
      }
      return true;
    });
    rows.sort((a, b) => {
      const c = compare(a, b, sortKey);
      if (c !== 0) return sortDir === "asc" ? c : -c;
      return (a.start_date || "").localeCompare(b.start_date || "") || a.name.localeCompare(b.name);
    });
    return rows;
  }, [
    tournaments,
    q,
    format,
    excludeBoth,
    hideGirls,
    hideClone,
    state,
    citiesSel,
    monthsSel,
    divsSel,
    from,
    to,
    maxFee,
    sortKey,
    sortDir,
    bucketsById,
  ]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  function clearFilters() {
    setQ("");
    setFormat("all");
    setCitiesSel([]);
    setState("");
    setMonthsSel([]);
    setFrom("");
    setTo("");
    setMaxFee("");
    setDivsSel([]);
    setHideGirls(false);
    setHideClone(true);
    setExcludeBoth(false);
    setOpenMs(null);
  }

  const updated = generated ? generated.replace("T", " ").replace(/\.\d+$/, "") : null;
  const filtersOn = Boolean(
    q ||
      citiesSel.length ||
      state ||
      monthsSel.length ||
      from ||
      to ||
      maxFee ||
      divsSel.length ||
      hideGirls ||
      !hideClone ||
      excludeBoth ||
      format !== "all",
  );

  return (
    <>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-amber-400/80">
            Texas 7v7 and flag
          </p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-zinc-50">Tournaments</h1>
          <p className="mt-2 max-w-2xl text-sm text-zinc-300">
            Upcoming Texas 7v7 and flag football tournaments from Zorts and Flag50. Girls-only
            events are omitted; mixed events keep a + girls divisions tag. Each event name opens
            the organizer&apos;s registration page. City opens Google Maps; Directions uses the
            venue. Past events (ended before today, Central Time) are hidden. Fees, divisions, and
            contacts are copied from the public listing — never invented.
          </p>
        </div>
        <p className="font-mono text-sm text-zinc-400">
          {updated ? <>Updated {updated}</> : "Updated —"}
          <span className="ml-2 text-zinc-500">
            · {filtered.length.toLocaleString()}
            {filtersOn ? ` of ${tournaments.length.toLocaleString()}` : ""}{" "}
            {filtered.length === 1 ? "tournament" : "tournaments"}
            {fileCount !== tournaments.length ? (
              <span className="block text-right text-xs text-zinc-500">
                {fileCount.toLocaleString()} on file
              </span>
            ) : null}
          </span>
        </p>
      </div>

      <form
        className="mt-6 flex flex-col gap-3 rounded-xl border border-amber-400/35 bg-[#17233d] p-3"
        onSubmit={(e) => e.preventDefault()}
      >
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-52 flex-[2]">
            <Label htmlFor="tq" className="text-xs font-medium uppercase tracking-wide text-zinc-100">
              Search
            </Label>
            <Input
              id="tq"
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Name, city, organizer, venue"
              className="mt-1"
            />
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-100">Format</p>
            <div
              role="group"
              aria-label="Format"
              className="mt-1 flex rounded-lg border border-amber-200/45 bg-[#0f1a2e] p-0.5"
            >
              {(
                [
                  ["all", "All"],
                  ["7v7", "7v7"],
                  ["flag", "Flag"],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setFormat(value)}
                  className={
                    format === value
                      ? "rounded-md bg-amber-400 px-3 py-1 text-sm font-medium text-zinc-950"
                      : "rounded-md px-3 py-1 text-sm text-zinc-300 hover:text-zinc-50"
                  }
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {showStateFilter ? (
            <div>
              <Label htmlFor="tstate" className="text-xs font-medium uppercase tracking-wide text-zinc-100">
                State
              </Label>
              <select
                id="tstate"
                value={state}
                onChange={(e) => setState(e.target.value)}
                className="night-select mt-1 h-8 w-full rounded-lg px-2.5 text-sm"
              >
                <option value="">All states</option>
                {states.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          <div>
            <Label htmlFor="tdiv" className="text-xs font-medium uppercase tracking-wide text-zinc-100">
              Divisions
            </Label>
            <MultiSelect
              id="tdiv"
              label="Divisions"
              items={divItems}
              selected={divsSel}
              onChange={setDivsSel}
              open={openMs === "div"}
              onOpenChange={(o) => setOpenMs(o ? "div" : null)}
            />
          </div>
          <div>
            <Label htmlFor="tcity" className="text-xs font-medium uppercase tracking-wide text-zinc-100">
              Cities
            </Label>
            <MultiSelect
              id="tcity"
              label="Cities"
              items={cityItems}
              selected={citiesSel}
              onChange={setCitiesSel}
              searchable
              open={openMs === "city"}
              onOpenChange={(o) => setOpenMs(o ? "city" : null)}
            />
          </div>
          <div>
            <Label htmlFor="tmonth" className="text-xs font-medium uppercase tracking-wide text-zinc-100">
              Months
            </Label>
            <MultiSelect
              id="tmonth"
              label="Months"
              items={monthItems}
              selected={monthsSel}
              onChange={setMonthsSel}
              open={openMs === "month"}
              onOpenChange={(o) => setOpenMs(o ? "month" : null)}
            />
          </div>
          <div>
            <Label htmlFor="tfrom" className="text-xs font-medium uppercase tracking-wide text-zinc-100">
              From
            </Label>
            <Input id="tfrom" type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="mt-1" />
          </div>
          <div>
            <Label htmlFor="tto" className="text-xs font-medium uppercase tracking-wide text-zinc-100">
              To
            </Label>
            <Input id="tto" type="date" value={to} onChange={(e) => setTo(e.target.value)} className="mt-1" />
          </div>
          <div>
            <Label htmlFor="tfee" className="text-xs font-medium uppercase tracking-wide text-zinc-100">
              Max entry fee ($)
            </Label>
            <Input
              id="tfee"
              type="number"
              min={0}
              step={25}
              inputMode="numeric"
              placeholder="Any"
              value={maxFee}
              onChange={(e) => setMaxFee(e.target.value)}
              className="mt-1"
            />
          </div>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
          <label className="flex items-center gap-2 text-sm text-zinc-200">
            <input
              type="checkbox"
              className="size-3.5 accent-amber-400"
              checked={hideGirls}
              onChange={(e) => setHideGirls(e.target.checked)}
            />
            Hide tournaments with girls divisions
          </label>
          <label className="flex items-center gap-2 text-sm text-zinc-200">
            <input
              type="checkbox"
              className="size-3.5 accent-amber-400"
              checked={hideClone}
              onChange={(e) => setHideClone(e.target.checked)}
            />
            Hide “(clone)” duplicates
          </label>
          <label className="flex items-center gap-2 text-sm text-zinc-200">
            <input
              type="checkbox"
              className="size-3.5 accent-amber-400"
              checked={excludeBoth}
              onChange={(e) => setExcludeBoth(e.target.checked)}
            />
            Exclude events that have both formats
          </label>
        </div>
        {filtersOn ? (
          <div>
            <Button type="button" variant="outline" size="sm" onClick={clearFilters}>
              Clear filters
            </Button>
          </div>
        ) : null}
      </form>

      {filtered.length === 0 ? (
        <div className="mt-8 rounded-xl border border-dashed border-amber-400/35 bg-[#17233d] px-6 py-16 text-center">
          <p className="text-lg font-medium text-zinc-100">No tournaments match</p>
          <p className="mx-auto mt-2 max-w-lg text-sm text-zinc-400">
            {tournaments.length === 0
              ? "No upcoming 7v7 or flag events are on file. The Monday refresh pulls Zorts and Flag50 public listings when they are reachable."
              : "Try clearing a filter, widening the date range, or switching format back to All."}
          </p>
        </div>
      ) : (
        <>
          <div className="mt-6 hidden lg:block">
            <Table className="text-[13px]">
              <TableHeader>
                <TableRow className="border-white/10 hover:bg-transparent">
                  <TableHead className="text-zinc-300">
                    <SortButton
                      label="Date"
                      active={sortKey === "start_date"}
                      dir={sortDir}
                      onClick={() => toggleSort("start_date")}
                    />
                  </TableHead>
                  <TableHead className="text-zinc-300">
                    <SortButton
                      label="Event"
                      active={sortKey === "name"}
                      dir={sortDir}
                      onClick={() => toggleSort("name")}
                    />
                  </TableHead>
                  <TableHead className="text-zinc-300">
                    <SortButton
                      label="Format"
                      active={sortKey === "category"}
                      dir={sortDir}
                      onClick={() => toggleSort("category")}
                    />
                  </TableHead>
                  <TableHead className="text-zinc-300">
                    <SortButton
                      label="City"
                      active={sortKey === "city"}
                      dir={sortDir}
                      onClick={() => toggleSort("city")}
                    />
                  </TableHead>
                  <TableHead className="text-zinc-300">Divisions</TableHead>
                  <TableHead className="text-right text-zinc-300">
                    <SortButton
                      label="Fee"
                      active={sortKey === "entry_fee"}
                      dir={sortDir}
                      onClick={() => toggleSort("entry_fee")}
                      align="right"
                    />
                  </TableHead>
                  <TableHead className="text-zinc-300">
                    <SortButton
                      label="Register by"
                      active={sortKey === "registration_ends"}
                      dir={sortDir}
                      onClick={() => toggleSort("registration_ends")}
                    />
                  </TableHead>
                  <TableHead className="text-zinc-300">
                    <SortButton
                      label="Organizer"
                      active={sortKey === "organizer"}
                      dir={sortDir}
                      onClick={() => toggleSort("organizer")}
                    />
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((t) => (
                  <TableRow key={t.id} className="border-white/12 hover:bg-amber-400/8">
                    <TableCell className="whitespace-nowrap font-mono text-zinc-300">
                      {formatRange(t.start_date, t.end_date)}
                    </TableCell>
                    <TableCell className="max-w-xs whitespace-normal font-sans">
                      <a
                        href={t.event_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-start gap-1 text-zinc-100 hover:text-amber-300"
                      >
                        <span>{t.name}</span>
                        <ExternalLink className="mt-0.5 size-3 shrink-0 text-zinc-500" aria-hidden />
                      </a>
                      <EventMeta t={t} />
                      {t.venue ? <p className="mt-0.5 text-xs text-zinc-500">{t.venue}</p> : null}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className={categoryClass(t.category)}>
                        {categoryLabel(t.category)}
                      </Badge>
                    </TableCell>
                    <TableCell className="whitespace-normal">
                      <CityLinks t={t} />
                    </TableCell>
                    <TableCell className="max-w-[14rem] whitespace-normal text-xs text-zinc-400">
                      {openDivisionText(t)}
                    </TableCell>
                    <TableCell className="text-right font-mono text-zinc-200">{t.entry_fee || "—"}</TableCell>
                    <TableCell className="whitespace-normal text-xs text-zinc-400">
                      {t.registration_ends || "—"}
                    </TableCell>
                    <TableCell className="whitespace-normal font-sans text-zinc-300">
                      {t.organizer || "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <ul className="mt-6 space-y-2 lg:hidden">
            {filtered.map((t) => (
              <li key={t.id} className="rounded-xl border border-amber-400/30 bg-[#17233d] p-3">
                <div className="flex items-start justify-between gap-3">
                  <p className="font-mono text-xs text-zinc-400">{formatRange(t.start_date, t.end_date)}</p>
                  <Badge variant="outline" className={categoryClass(t.category)}>
                    {categoryLabel(t.category)}
                  </Badge>
                </div>
                <a
                  href={t.event_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 inline-flex items-start gap-1 text-zinc-100 hover:text-amber-300"
                >
                  <span>{t.name}</span>
                  <ExternalLink className="mt-1 size-3 shrink-0 text-zinc-500" aria-hidden />
                </a>
                <EventMeta t={t} />
                <p className="mt-1">
                  <CityLinks t={t} />
                </p>
                {t.organizer ? <p className="mt-1 text-sm text-zinc-400">{t.organizer}</p> : null}
                {t.entry_fee ? (
                  <p className="mt-1 font-mono text-xs text-amber-200">{t.entry_fee}</p>
                ) : null}
                <p className="mt-1 text-xs text-zinc-500">{openDivisionText(t)}</p>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}
