"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ListOrdered, CalendarDays, LogOut } from "lucide-react";
import { signOut } from "@/lib/auth-actions";

export function SiteHeader() {
  const pathname = usePathname();
  // The login page carries its own branding and has no signed-in nav to show.
  if (pathname === "/login") return null;
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
        <div className="flex items-center gap-2 self-stretch sm:self-auto">
        <nav
          aria-label="View"
          className="flex flex-1 items-center gap-1 rounded-lg border border-white/10 bg-white/5 p-1 text-sm sm:flex-none"
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
        <form action={signOut}>
          <button
            type="submit"
            title="Sign out"
            className="inline-flex size-9 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-zinc-400 hover:bg-white/10 hover:text-zinc-100"
          >
            <LogOut className="size-4" strokeWidth={2} aria-hidden />
            <span className="sr-only">Sign out</span>
          </button>
        </form>
        </div>
      </div>
    </header>
  );
}
