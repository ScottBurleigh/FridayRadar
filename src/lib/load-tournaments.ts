import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { cache } from "react";
import {
  upcomingTournaments,
  type TournamentBoard,
} from "./tournaments";

const EMPTY_BOARD: TournamentBoard = {
  generated: "",
  window: [],
  count: 0,
  tournaments: [],
};

export function loadTournamentBoard(): TournamentBoard {
  const path = join(process.cwd(), "data", "tournaments.json");
  if (!existsSync(path)) return EMPTY_BOARD;
  try {
    const raw = JSON.parse(readFileSync(path, "utf8")) as TournamentBoard;
    const tournaments = Array.isArray(raw.tournaments) ? raw.tournaments : [];
    return {
      generated: typeof raw.generated === "string" ? raw.generated : "",
      window: Array.isArray(raw.window) ? raw.window : [],
      count: Number.isFinite(raw.count) ? raw.count : tournaments.length,
      tournaments,
    };
  } catch {
    return EMPTY_BOARD;
  }
}

export const loadUpcomingTournaments = cache(() => {
  const board = loadTournamentBoard();
  return { board, upcoming: upcomingTournaments(board.tournaments) };
});
