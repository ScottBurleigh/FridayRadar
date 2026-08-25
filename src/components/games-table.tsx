import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { RankedGame } from "@/lib/data";
import { formatKickoff, formatTalent } from "@/lib/format";
import type { Game, School } from "@/lib/types";

function SchoolName({ school, mapped }: { school: School; mapped: boolean }) {
  if (!mapped) {
    return <span className="text-zinc-300">{school.name}</span>;
  }
  return (
    <Link href={`/schools/${school.id}`} className="text-zinc-100 hover:text-amber-300">
      {school.name}
    </Link>
  );
}

function venueLabel(game: Game): string {
  const city = (game.venue?.city || game.city)?.trim();
  const state = (game.venue?.state || game.state)?.trim();
  if (city && state) return `${city}, ${state}`;
  if (state) return state;
  if (city) return city;
  return "—";
}

export function GamesTable({ rows }: { rows: RankedGame[] }) {
  if (!rows.length) {
    return null;
  }
  return (
    <>
      <div className="hidden lg:block">
        <Table className="font-mono text-[13px]">
          <TableHeader>
            <TableRow className="border-white/10 hover:bg-transparent">
              <TableHead className="w-14 text-zinc-500">Rk</TableHead>
              <TableHead className="text-zinc-500">Kickoff</TableHead>
              <TableHead className="text-zinc-500">Matchup</TableHead>
              <TableHead className="text-right text-zinc-500">Away rec / talent</TableHead>
              <TableHead className="text-right text-zinc-500">Home rec / talent</TableHead>
              <TableHead className="text-right text-zinc-500">Combined</TableHead>
              <TableHead className="text-zinc-500">Site</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.game.id} className="border-white/8 hover:bg-amber-400/5">
                <TableCell className="text-zinc-400">{row.rank}</TableCell>
                <TableCell className="whitespace-nowrap font-sans text-zinc-300">
                  {formatKickoff(row.game.kickoff, row.game.is_time_tba)}
                </TableCell>
                <TableCell className="font-sans">
                  <SchoolName school={row.away} mapped={row.awayMapped} />
                  <span className="px-2 text-zinc-600">@</span>
                  <SchoolName school={row.home} mapped={row.homeMapped} />
                </TableCell>
                <TableCell className="text-right text-zinc-300">
                  {row.awayRecruits} / {formatTalent(row.awayTalent)}
                </TableCell>
                <TableCell className="text-right text-zinc-300">
                  {row.homeRecruits} / {formatTalent(row.homeTalent)}
                </TableCell>
                <TableCell className="text-right font-semibold text-amber-200">
                  {formatTalent(row.combined)}
                </TableCell>
                <TableCell className="font-sans text-zinc-400">
                  {venueLabel(row.game)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <ul className="space-y-2 lg:hidden">
        {rows.map((row) => (
          <li
            key={row.game.id}
            className="rounded-xl border border-white/10 bg-white/[0.03] p-3"
          >
            <div className="flex items-baseline justify-between gap-3 text-xs">
              <span className="font-mono text-zinc-500">#{row.rank}</span>
              <span className="text-zinc-400">
                {formatKickoff(row.game.kickoff, row.game.is_time_tba)}
              </span>
            </div>
            <p className="mt-2 text-zinc-100">
              <SchoolName school={row.away} mapped={row.awayMapped} />
              <span className="px-2 text-zinc-600">@</span>
              <SchoolName school={row.home} mapped={row.homeMapped} />
            </p>
            <p className="mt-1 text-sm text-zinc-500">
              {venueLabel(row.game)}
            </p>
            <p className="mt-2 font-mono text-xs text-zinc-400">
              Away {row.awayRecruits}/{formatTalent(row.awayTalent)} · Home {row.homeRecruits}/
              {formatTalent(row.homeTalent)} · Combined{" "}
              <span className="text-amber-200">{formatTalent(row.combined)}</span>
            </p>
          </li>
        ))}
      </ul>
    </>
  );
}
