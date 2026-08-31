import { US_STATES } from "@/lib/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function FilterBar({
  action,
  state,
  zip,
  sort,
  q,
  showSort = true,
  showSearch = true,
  stateLabel = "State",
  zipLabel = "Zip (≈25 miles)",
}: {
  action: string;
  state?: string;
  zip?: string;
  sort?: string;
  q?: string;
  showSort?: boolean;
  showSearch?: boolean;
  stateLabel?: string;
  zipLabel?: string;
}) {
  return (
    <form
      action={action}
      method="get"
      className="flex flex-col gap-3 rounded-xl border border-amber-400/35 bg-[#17233d] p-3 sm:flex-row sm:flex-wrap sm:items-end"
    >
      {showSearch ? (
        <div className="min-w-52 flex-[2]">
          <Label
            htmlFor="q"
            className="text-xs font-medium uppercase tracking-wide text-zinc-100"
          >
            School name
          </Label>
          <Input
            id="q"
            name="q"
            type="search"
            placeholder="Search by school name"
            defaultValue={q ?? ""}
            className="mt-1 border-amber-200/45 bg-[#0f1a2e] text-zinc-50 placeholder:text-zinc-400"
          />
        </div>
      ) : null}
      <div className="min-w-40 flex-1">
        <Label htmlFor="state" className="text-xs font-medium uppercase tracking-wide text-zinc-100">
          {stateLabel}
        </Label>
        <select
          id="state"
          name="state"
          defaultValue={state ?? ""}
          className="night-select mt-1 h-8 w-full rounded-lg px-2.5 text-sm"
        >
          <option value="" className="bg-[#0f1a2e] text-zinc-50">
            All states
          </option>
          {US_STATES.map((s) => (
            <option key={s.code} value={s.code} className="bg-[#0f1a2e] text-zinc-50">
              {s.name}
            </option>
          ))}
        </select>
      </div>
      <div className="min-w-36 flex-1">
        <Label htmlFor="zip" className="text-xs font-medium uppercase tracking-wide text-zinc-100">
          {zipLabel}
        </Label>
        <Input
          id="zip"
          name="zip"
          inputMode="numeric"
          pattern="[0-9]{5}"
          maxLength={5}
          placeholder="30518"
          defaultValue={zip ?? ""}
          className="mt-1 border-amber-200/45 bg-[#0f1a2e] text-zinc-50 placeholder:text-zinc-400"
        />
      </div>
      {showSort ? (
        <div className="min-w-40 flex-1">
          <Label htmlFor="sort" className="text-xs font-medium uppercase tracking-wide text-zinc-100">
            Sort
          </Label>
          <select
            id="sort"
            name="sort"
            defaultValue={sort === "count" || sort === "talent" ? sort : "strength"}
            className="night-select mt-1 h-8 w-full rounded-lg px-2.5 text-sm"
          >
            <option value="strength" className="bg-[#0f1a2e] text-zinc-50">
              Team strength
            </option>
            <option value="talent" className="bg-[#0f1a2e] text-zinc-50">
              Talent
            </option>
            <option value="count" className="bg-[#0f1a2e] text-zinc-50">

              Recruit count
            </option>
          </select>
        </div>
      ) : null}
      <Button type="submit" className="bg-amber-400 text-zinc-950 hover:bg-amber-300">
        Apply filters
      </Button>
    </form>
  );
}
