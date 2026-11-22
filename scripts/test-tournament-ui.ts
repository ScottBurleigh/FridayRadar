/**
 * Client-side weekend + schedule helpers (no data files).
 * Run: npx tsx scripts/test-tournament-ui.ts
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  ageLine,
  ageTokens,
  collectAges,
  conflictNotes,
  feeTotal,
  formatAgeRange,
  hiddenByPast,
  isPast,
  localTodayYmd,
  parseScheduleFee,
  readHashScheduleIds,
  schedulePlainText,
  writeHashScheduleIds,
} from "../src/lib/tournament-schedule";
import {
  hiddenByWeekends,
  overlapsWeekend,
  weekendList,
} from "../src/lib/tournament-weekends";
import type { Tournament } from "../src/lib/tournaments";

function t(partial: Partial<Tournament> & Pick<Tournament, "id" | "name" | "start_date">): Tournament {
  return {
    category: "7v7",
    end_date: partial.end_date ?? partial.start_date,
    city: "Austin",
    venue: "",
    sport: "7v7",
    age_groups: "",
    divisions: "",
    entry_fee: "",
    registration_ends: "",
    organizer: "",
    contact_email: "",
    contact_phone: "",
    event_url: "https://example.com",
    clubhouse_url: "",
    source: "zorts",
    ...partial,
  };
}

function checkFees() {
  assert.deepEqual(parseScheduleFee("$100-$250"), { value: 100, label: "$100" });
  assert.deepEqual(parseScheduleFee("$400 per team"), { value: 400, label: "$400" });
  assert.deepEqual(parseScheduleFee("$1,239"), { value: 1239, label: "$1,239" });
  assert.deepEqual(parseScheduleFee(""), { value: null, label: "TBD" });
  assert.deepEqual(parseScheduleFee(null), { value: null, label: "TBD" });
  assert.deepEqual(parseScheduleFee("$0"), { value: 0, label: "free" });
  assert.deepEqual(parseScheduleFee("0"), { value: 0, label: "free" });
  const tot = feeTotal([
    { entry_fee: "$100-$250" },
    { entry_fee: "$1,139" },
    { entry_fee: "" },
    { entry_fee: "ask" },
  ]);
  assert.equal(tot.sum, 1239);
  assert.equal(tot.tbd, 2);
  assert.equal(tot.label, "$1,239 (+2 TBD)");
}

function checkWeekends() {
  const tue = weekendList(new Date(2026, 10, 10)); // Tue Nov 10
  assert.equal(tue[0]?.id, "2026-11-13");
  assert.equal(tue[0]?.label, "Sat Nov 14 – Sun Nov 15");
  assert.equal(tue[0]?.month, "Nov 2026");
  assert.equal(tue[tue.length - 1]?.id, "2027-07-30");

  const fri = weekendList(new Date(2026, 10, 13));
  assert.equal(fri[0]?.id, "2026-11-13");

  const sun = weekendList(new Date(2026, 10, 15));
  assert.equal(sun[0]?.id, "2026-11-13");

  const jun = weekendList(new Date(2026, 5, 15)); // Jun — still this year's July 31
  assert.equal(jun[jun.length - 1]?.id, "2026-07-31");

  const aug = weekendList(new Date(2026, 7, 1)); // past July → next year's July 31
  assert.equal(aug[aug.length - 1]?.id, "2027-07-30");

  const w = tue[0]!;
  assert.equal(overlapsWeekend("2026-11-13", "2026-11-15", w), true);
  assert.equal(overlapsWeekend("2026-11-15", "2026-11-15", w), true);
  assert.equal(overlapsWeekend("2026-11-12", "2026-11-12", w), false);
  assert.equal(overlapsWeekend("2026-11-16", "2026-11-16", w), false);
  assert.equal(overlapsWeekend("2026-11-12", "2026-11-13", w), true);

  assert.equal(hiddenByWeekends("2026-11-15", "2026-11-15", ["2026-11-13"], tue), true);
  assert.equal(hiddenByWeekends("2026-11-20", "2026-11-22", ["2026-11-13"], tue), false);
  assert.equal(hiddenByWeekends("2026-11-15", "2026-11-15", [], tue), false);
}

function checkConflicts() {
  const weekends = weekendList(new Date(2026, 10, 10));
  const a = t({ id: "a", name: "Austin Open", start_date: "2026-11-14", end_date: "2026-11-15" });
  const b = t({ id: "b", name: "Dallas Classic", start_date: "2026-11-15", end_date: "2026-11-15" });
  const c = t({ id: "c", name: "Houston Cup", start_date: "2026-12-05", end_date: "2026-12-06" });
  const notes = conflictNotes([a, b, c], weekends, ["2026-11-13"]);
  assert.ok(notes.some((n) => n.type === "overlap" && n.text.includes("Austin Open")));
  assert.ok(notes.some((n) => n.type === "excluded" && n.text.includes("Austin Open")));
  assert.ok(notes.some((n) => n.type === "excluded" && n.text.includes("Dallas Classic")));
  assert.ok(!notes.some((n) => n.text.includes("Houston Cup")));

  const d = t({ id: "d", name: "Friday only", start_date: "2026-11-13", end_date: "2026-11-13" });
  const e = t({ id: "e", name: "Sunday only", start_date: "2026-11-15", end_date: "2026-11-15" });
  const sameWk = conflictNotes([d, e], weekends, []);
  assert.ok(sameWk.some((n) => n.type === "weekend" && n.text.includes("Same weekend")));
}

function checkHash() {
  const loc = { hash: "", pathname: "/tournaments", search: "" };
  (globalThis as unknown as { window: unknown }).window = {
    location: loc,
    history: {
      replaceState(_a: unknown, _b: string, url: string) {
        if (url.startsWith("#")) loc.hash = url;
        else loc.hash = "";
      },
    },
  };
  loc.hash = "#sched=zorts-1,flag50-2,nope";
  const known = new Set(["zorts-1", "flag50-2"]);
  assert.deepEqual(readHashScheduleIds(known), ["zorts-1", "flag50-2"]);
  writeHashScheduleIds(["zorts-1", "flag50-2"]);
  assert.equal(loc.hash, "#sched=zorts-1,flag50-2");
  writeHashScheduleIds([]);
  assert.equal(loc.hash, "");
}

function checkAges() {
  assert.deepEqual(ageTokens("Coed 13/14U"), ["13/14U"]);
  assert.deepEqual(ageTokens("13-14u"), ["13/14U"]);
  assert.deepEqual(ageTokens("Boy's 18U"), ["18U"]);
  assert.deepEqual(ageTokens("Girl's High School"), ["HS"]);
  assert.equal(formatAgeRange("4u to 17u"), "4U–17U");
  assert.equal(formatAgeRange("6u to adult"), "6U–Adult");
  assert.equal(formatAgeRange("8U, 10U"), "");
  assert.deepEqual(collectAges(["8U", "10U", "8U", "MS"]), ["8U", "10U", "MS"]);

  assert.equal(ageLine(t({ id: "x", name: "Empty", start_date: "2026-11-14" })), "Ages TBD");
  assert.equal(
    ageLine(t({ id: "x", name: "List AG", start_date: "2026-11-14", age_groups: "8U; 10U; HS" })),
    "8U, 10U, HS",
  );
  assert.equal(
    ageLine(
      t({
        id: "x",
        name: "Div girls",
        start_date: "2026-11-14",
        divisions: "Boy's 10U; Girl's 12U; Girl's HS",
      }),
    ),
    "10U (girls: 12U, HS)",
  );

  const board = JSON.parse(readFileSync("data/tournaments.json", "utf8")) as {
    tournaments: Tournament[];
  };
  const byName = (name: string) => {
    const row = board.tournaments.find((r) => r.name === name);
    assert.ok(row, `missing ${name}`);
    return row!;
  };
  assert.equal(
    ageLine(byName("Black Friday Blitz 2026 Flag Football Tournament")),
    "8U, 10U, 12U, 14U (girls: 8U, 10U, 12U, 14U, HS)",
  );
  assert.equal(
    ageLine(byName("Santa Bowl 2026")),
    "8U, 10U, 11U, 12U, 13U, 14U, HS (girls: 10U, 12U, 14U, HS)",
  );
  assert.equal(
    ageLine(byName("2027 Kickoff Classic Tournament")),
    "8U, 9U, 10U, 11U, 12U, 13U, 14U, 15U, 18U",
  );
  assert.equal(ageLine(byName("Toys for tots flag football tournament")), "4U–17U");

  const plain = schedulePlainText(
    [byName("Toys for tots flag football tournament"), t({ id: "empty", name: "No ages", start_date: "2027-02-01" })],
    "test",
    "$0",
    [],
    () => "Flag",
  );
  assert.ok(plain.includes("  Ages: 4U–17U"));
  assert.ok(plain.includes("  Ages: TBD"));
}

function checkPast() {
  const today = "2026-11-22";
  const ended = t({ id: "p1", name: "Ended", start_date: "2026-11-21", end_date: "2026-11-21" });
  const endsToday = t({ id: "p2", name: "Today", start_date: "2026-11-22", end_date: "2026-11-22" });
  const future = t({ id: "p3", name: "Future", start_date: "2026-11-27", end_date: "2026-11-29" });
  const startOnlyPast = t({ id: "p4", name: "Start only", start_date: "2026-11-21", end_date: "" });
  const startOnlyToday = t({ id: "p5", name: "Start today", start_date: "2026-11-22", end_date: "" });
  const spanning = t({
    id: "p6",
    name: "Span",
    start_date: "2026-11-21",
    end_date: "2026-11-22",
  });

  assert.equal(isPast(ended, today), true);
  assert.equal(isPast(endsToday, today), false);
  assert.equal(isPast(future, today), false);
  assert.equal(isPast(startOnlyPast, today), true);
  assert.equal(isPast(startOnlyToday, today), false);
  assert.equal(isPast(spanning, today), false);
  assert.equal(isPast(ended, ""), false);

  assert.equal(hiddenByPast(ended, false, today), false);
  assert.equal(hiddenByPast(ended, true, today), true);
  assert.equal(hiddenByPast(future, true, today), false);
  assert.equal(hiddenByPast(ended, true, ""), false);

  const rows = [ended, endsToday, future, startOnlyPast, spanning];
  const shown = rows.filter((r) => !hiddenByPast(r, true, today));
  assert.deepEqual(
    shown.map((r) => r.id),
    ["p2", "p3", "p6"],
  );

  assert.equal(localTodayYmd(new Date(2026, 10, 22, 0, 5, 0)), "2026-11-22");
  assert.equal(localTodayYmd(new Date(2026, 10, 22, 23, 59, 0)), "2026-11-22");

  const copy = schedulePlainText([ended, future], "test", "$0", [], () => "7v7", today);
  assert.ok(copy.includes("Nov 21, 2026  (Past)"));
  assert.ok(copy.includes("Nov 27–29, 2026\n"));
  assert.ok(!copy.includes("Nov 27–29, 2026  (Past)"));
}

checkFees();
checkWeekends();
checkConflicts();
checkHash();
checkAges();
checkPast();
console.log("test-tournament-ui: ok");
