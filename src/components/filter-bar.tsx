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
}: {
  action: string;
  state?: string;
  zip?: string;
  sort?: string;
  showSort?: boolean;
}) {
  return (
    <form action={action} method="get" className="flex flex-col gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-3 sm:flex-row sm:flex-wrap sm:items-end">
      <div className="min-w-40 flex-1">
        <Label htmlFor="state" className="text-xs uppercase tracking-wide text-zinc-500">
          State
        </Label>
        <select
          id="state"
          name="state"
          defaultValue={state ?? ""}
          className="mt-1 h-8 w-full rounded-lg border border-input bg-input/30 px-2.5 text-sm text-foreground"
        >
          <option value="">All states</option>
          {US_STATES.map((s) => (
            <option key={s.code} value={s.code}>
              {s.name}
            </option>
          ))}
        </select>
      </div>
      <div className="min-w-36 flex-1">
        <Label htmlFor="zip" className="text-xs uppercase tracking-wide text-zinc-500">
          Zip (≈25 miles)
        </Label>
        <Input
          id="zip"
          name="zip"
          inputMode="numeric"
          pattern="[0-9]{5}"
          maxLength={5}
          placeholder="30518"
          defaultValue={zip ?? ""}
          className="mt-1"
        />
      </div>
      {showSort ? (
        <div className="min-w-40 flex-1">
          <Label htmlFor="sort" className="text-xs uppercase tracking-wide text-zinc-500">
            Sort
          </Label>
          <select
            id="sort"
            name="sort"
            defaultValue={sort === "count" ? "count" : "talent"}
            className="mt-1 h-8 w-full rounded-lg border border-input bg-input/30 px-2.5 text-sm text-foreground"
          >
            <option value="talent">Talent score</option>
            <option value="count">Recruit count</option>
          </select>
        </div>
      ) : null}
      <Button type="submit" className="bg-amber-400 text-zinc-950 hover:bg-amber-300">
        Apply filters
      </Button>
    </form>
  );
}
