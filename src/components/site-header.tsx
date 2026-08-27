"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ListOrdered, CalendarDays } from "lucide-react";

export function SiteHeader() {
  const pathname = usePathname();
  const links = [
    { href: "/", label: "Rankings", Icon: ListOrdered },
    { href: "/games", label: "Games of the week", Icon: CalendarDays },
  ];
  return (
    <header className="border-b border-amber-400/35 bg-[#0a1220]/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/fridayradar-mark.svg" alt="FridayRadar" width={36} height={36} className="size-9" />
          <span className="font-heading text-lg font-semibold tracking-tight text-zinc-50">
            FridayRadar
          </span>
        </Link>
        <nav
          aria-label="View"
          className="flex items-center gap-1 self-stretch rounded-lg border border-white/10 bg-white/5 p-1 text-sm sm:self-auto"
        >
          {links.map((l) => {
            const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
            const Icon = l.Icon;
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={
                  active
                    ? "inline-flex flex-1 items-center justify-center gap-1.5 rounded-md bg-amber-400 px-3 py-1.5 font-medium text-zinc-950 sm:flex-none"
                    : "inline-flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-zinc-300 hover:bg-white/10 hover:text-zinc-50 sm:flex-none"
                }
              >
                <Icon className="size-4 shrink-0" strokeWidth={2} aria-hidden />
                {l.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
