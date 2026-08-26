import { US_STATES } from "@/lib/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function FilterBar({
  action,
  state,
  zip,
  sort,
  showSort = true,
  stateLabel = "State",
  zipLabel = "Zip (≈25 miles)",
}: {
  action: string;
  state?: string;
  zip?: string;
  sort?: string;
  showSort?: boolean;
  stateLabel?: string;
  zipLabel?: string;
}) {
  return (
    <form
      action={action}
      method="get"
      className="flex flex-col gap-3 rounded-xl border border-amber-400/25 bg-[#121c2e] p-3 sm:flex-row sm:flex-wrap sm:items-end"
    >
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
          <option value="" className="bg-[#0d1628] text-zinc-50">
            All states
          </option>
          {US_STATES.map((s) => (
            <option key={s.code} value={s.code} className="bg-[#0d1628] text-zinc-50">
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
          className="mt-1 border-amber-200/45 bg-[#0d1628] text-zinc-50 placeholder:text-zinc-400"
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
            defaultValue={sort === "count" || sort === "strength" ? sort : "talent"}
            className="night-select mt-1 h-8 w-full rounded-lg px-2.5 text-sm"
          >
            <option value="talent" className="bg-[#0d1628] text-zinc-50">
              Talent score
            </option>
            <option value="strength" className="bg-[#0d1628] text-zinc-50">
              Team strength
            </option>
            <option value="count" className="bg-[#0d1628] text-zinc-50">
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
