import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { SchoolRankingRow } from "@/lib/types";
import { formatTalent } from "@/lib/format";

export function RankingsTable({ rows }: { rows: SchoolRankingRow[] }) {
  if (!rows.length) {
    return (
      <div className="rounded-xl border border-dashed border-white/15 px-6 py-16 text-center">
        <p className="text-lg font-medium text-zinc-200">No programs match these filters</p>
        <p className="mt-2 text-sm text-zinc-500">
          Clear the state or zip filter to return to the nationwide 2027+ talent board.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="hidden md:block">
        <Table className="font-mono text-[13px]">
          <TableHeader>
            <TableRow className="border-white/10 hover:bg-transparent">
              <TableHead className="w-14 text-zinc-500">Rk</TableHead>
              <TableHead className="text-zinc-500">School</TableHead>
              <TableHead className="text-zinc-500">City</TableHead>
              <TableHead className="w-12 text-zinc-500">St</TableHead>
              <TableHead className="w-16 text-zinc-500">Zip</TableHead>
              <TableHead className="w-16 text-right text-zinc-500">Rec</TableHead>
              <TableHead className="w-12 text-right text-zinc-500">5★</TableHead>
              <TableHead className="w-12 text-right text-zinc-500">4★</TableHead>
              <TableHead className="w-12 text-right text-zinc-500">3★</TableHead>
              <TableHead className="w-24 text-right text-zinc-500">Talent</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.school.id} className="border-white/8 hover:bg-amber-400/5">
                <TableCell className="text-zinc-400">{row.rank}</TableCell>
                <TableCell>
                  <Link
                    href={`/schools/${row.school.id}`}
                    className="font-sans font-medium text-zinc-100 hover:text-amber-300"
                  >
                    {row.school.name}
                    {row.school.mascot ? (
                      <span className="ml-2 font-normal text-zinc-500">{row.school.mascot}</span>
                    ) : null}
                  </Link>
                </TableCell>
                <TableCell className="font-sans text-zinc-400">{row.school.city}</TableCell>
                <TableCell className="text-zinc-300">{row.school.state}</TableCell>
                <TableCell className="text-zinc-400">{row.school.zip ?? "—"}</TableCell>
                <TableCell className="text-right text-zinc-200">{row.recruitCount}</TableCell>
                <TableCell className="text-right text-amber-300">{row.stars5 || "—"}</TableCell>
                <TableCell className="text-right text-zinc-300">{row.stars4 || "—"}</TableCell>
                <TableCell className="text-right text-zinc-400">{row.stars3 || "—"}</TableCell>
                <TableCell className="text-right font-semibold text-amber-200">
                  {formatTalent(row.talentScore)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <ul className="space-y-2 md:hidden">
        {rows.map((row) => (
          <li key={row.school.id}>
            <Link
              href={`/schools/${row.school.id}`}
              className="block rounded-xl border border-white/10 bg-white/[0.03] p-3"
            >
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-mono text-xs text-zinc-500">#{row.rank}</span>
                <span className="font-mono text-sm font-semibold text-amber-200">
                  {formatTalent(row.talentScore)}
                </span>
              </div>
              <p className="mt-1 font-medium text-zinc-50">{row.school.name}</p>
              <p className="text-sm text-zinc-500">
                {row.school.city}, {row.school.state} {row.school.zip ?? ""}
              </p>
              <p className="mt-2 font-mono text-xs text-zinc-400">
                {row.recruitCount} recruits · {row.stars5} 5★ · {row.stars4} 4★ · {row.stars3} 3★
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
