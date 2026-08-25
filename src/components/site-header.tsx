"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Radar } from "lucide-react";

export function SiteHeader() {
  const pathname = usePathname();
  const links = [
    { href: "/", label: "Rankings" },
    { href: "/games", label: "Games of the week" },
  ];
  return (
    <header className="border-b border-white/10 bg-[#07090c]/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2 text-amber-300">
          <Radar className="size-5" aria-hidden />
          <span className="font-heading text-lg font-semibold tracking-tight text-zinc-50">
            FridayRadar
          </span>
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          {links.map((l) => {
            const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={
                  active
                    ? "rounded-md bg-amber-400/15 px-3 py-1.5 font-medium text-amber-200"
                    : "rounded-md px-3 py-1.5 text-zinc-400 hover:bg-white/5 hover:text-zinc-100"
                }
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
