import type { Metadata } from "next";
import { TournamentsBoard } from "@/components/tournaments-board";
import { loadUpcomingTournaments } from "@/lib/load-tournaments";

export const metadata: Metadata = {
  title: "Texas 7v7 / flag tournaments",
  description:
    "Upcoming Texas 7v7 and flag football tournaments from public Zorts and Flag50 listings. Girls-only events are omitted.",
};

export const dynamic = "force-dynamic";

export default function TournamentsPage() {
  const { board, upcoming } = loadUpcomingTournaments();

  return (
    <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">
      <TournamentsBoard
        tournaments={upcoming}
        generated={board.generated}
        fileCount={board.count}
      />
    </main>
  );
}
