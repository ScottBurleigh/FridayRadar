import { useId, type ReactNode } from "react";
import { Info, XIcon } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ToughnessIcon } from "@/lib/types";
import { TOUGHNESS_LABEL } from "@/lib/toughness";

function n(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toLocaleString("en-US", {
    maximumFractionDigits: 3,
    minimumFractionDigits: 0,
  });
}

function Formula({ children }: { children: string }) {
  return <p className="font-mono text-[13px] leading-relaxed text-amber-100/90">{children}</p>;
}

const PANEL =
  "relative w-[min(32rem,calc(100%-2rem))] max-h-[min(36rem,85vh)] overflow-y-auto rounded-xl bg-[#17233d] p-4 text-zinc-100 shadow-xl ring-1 ring-amber-400/25 [&::backdrop]:bg-[#0a1220]/75";

const PANEL_POS = {
  position: "fixed",
  inset: "unset",
  top: "50%",
  left: "50%",
  margin: 0,
  transform: "translate(-50%, -50%)",
} as const;

const LABEL: Record<ToughnessIcon, string> = {
  ...TOUGHNESS_LABEL,
  unknown: "unknown",
};

function CloseButton({ panelId }: { panelId: string }) {
  return (
    <button
      type="button"
      className={cn(
        buttonVariants({ variant: "ghost", size: "icon-sm" }),
        "absolute top-2 right-2 text-zinc-400 hover:text-zinc-50",
      )}
      aria-label="Close"
      popoverTarget={panelId}
      popoverTargetAction="hide"
    >
      <XIcon className="size-4" />
    </button>
  );
}

/** Live ingest cutoffs from `toughness_icon()` — UI does not recompute. */
function Scale() {
  return (
    <section>
      <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-300">Cutoffs</h3>
      <p className="mt-1 text-zinc-300">
        Opponent strength minus this school. Missing opponent strength is unknown, never 0.
      </p>
      <Formula>{"unknown  opponent has no team_strength"}</Formula>
      <Formula>{"≥ 20     heavy underdog"}</Formula>
      <Formula>{"≥ 8      underdog"}</Formula>
      <Formula>{"> −8     toss-up"}</Formula>
      <Formula>{"> −20    favored"}</Formula>
      <Formula>{"else     heavy favorite"}</Formula>
    </section>
  );
}

export function ToughnessExplainButton({
  schoolName,
  teamStrength,
}: {
  schoolName: string;
  teamStrength: number | null | undefined;
}) {
  const reactId = useId();
  const panelId = `toughness-formula-${reactId.replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const label = `How ${schoolName} game toughness is decided`;

  return (
    <>
      <button
        type="button"
        className={cn(
          buttonVariants({ variant: "ghost", size: "icon-xs" }),
          "-mr-1 text-zinc-400 hover:bg-white/10 hover:text-amber-300",
        )}
        aria-label={label}
        popoverTarget={panelId}
        popoverTargetAction="toggle"
      >
        <Info className="size-3.5" aria-hidden />
      </button>
      <div
        id={panelId}
        popover="auto"
        role="dialog"
        aria-label={`${schoolName} game toughness`}
        className={PANEL}
        style={PANEL_POS}
      >
        <CloseButton panelId={panelId} />
        <h2 className="pr-8 text-base font-medium text-zinc-50">{schoolName} game toughness</h2>
        <p className="mt-2 text-sm text-zinc-400">
          From this team’s view: subtract this school’s team strength from the opponent’s. Same
          team_strength number as the header (talent mixed with On3/MaxPreps, plus Texas DCTF
          bonus when it applies). Icons are stamped at ingest — this page does not recompute them.
        </p>
        <div className="mt-4 space-y-4 text-sm">
          <section>
            <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-300">This school</h3>
            <Formula>{`team_strength = ${n(teamStrength)}`}</Formula>
            <Formula>{"delta = opponent_strength − team_strength"}</Formula>
          </section>
          <Scale />
        </div>
      </div>
    </>
  );
}

export function GameToughnessButton({
  schoolName,
  teamStrength,
  opponentName,
  opponentStrength,
  icon,
  children,
}: {
  schoolName: string;
  teamStrength: number | null | undefined;
  opponentName: string;
  opponentStrength: number | null | undefined;
  icon: ToughnessIcon;
  children: ReactNode;
}) {
  const reactId = useId();
  const panelId = `toughness-game-${reactId.replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const missing = opponentStrength == null;
  const delta =
    teamStrength != null && opponentStrength != null ? opponentStrength - teamStrength : null;
  const title = `${opponentName} toughness`;

  return (
    <>
      <button
        type="button"
        className="inline-flex items-center justify-center rounded-md px-1 py-0.5 hover:bg-white/10"
        aria-label={`Why ${opponentName} is ${LABEL[icon]}`}
        popoverTarget={panelId}
        popoverTargetAction="toggle"
      >
        {children}
      </button>
      <div
        id={panelId}
        popover="auto"
        role="dialog"
        aria-label={title}
        className={PANEL}
        style={PANEL_POS}
      >
        <CloseButton panelId={panelId} />
        <h2 className="pr-8 text-base font-medium text-zinc-50">{title}</h2>
        <p className="mt-2 text-sm text-zinc-400">
          {schoolName} vs {opponentName}. Delta is opponent team strength minus {schoolName}’s.
        </p>
        <div className="mt-4 space-y-4 text-sm">
          <section>
            <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-300">Inputs</h3>
            <Formula>{`${schoolName} team_strength = ${n(teamStrength)}`}</Formula>
            {missing ? (
              <Formula>{`${opponentName} opponent_strength missing`}</Formula>
            ) : (
              <Formula>{`${opponentName} opponent_strength = ${n(opponentStrength)}`}</Formula>
            )}
            {missing ? (
              <p className="mt-2 text-zinc-300">
                Unknown — no icon. Missing opponent strength is not treated as 0.
              </p>
            ) : (
              <>
                <Formula>{`delta = ${n(opponentStrength)} − ${n(teamStrength)} = ${n(delta)}`}</Formula>
                <p className="mt-2 text-zinc-300">
        {LABEL[icon]} ({icon.replace(/_/g, " ")}).
                </p>
              </>
            )}
          </section>
          <Scale />
        </div>
      </div>
    </>
  );
}
