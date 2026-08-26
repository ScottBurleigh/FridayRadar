"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function SiteHeader() {
  const pathname = usePathname();
  const links = [
    { href: "/", label: "Rankings" },
    { href: "/games", label: "Games of the week" },
  ];
  return (
    <header className="border-b border-amber-400/25 bg-[#0a1220]/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5">
          <Image
            src="/fridayradar-logo.png"
            alt="FridayRadar"
            width={36}
            height={36}
            className="size-9 rounded-md ring-1 ring-amber-400/40"
            priority
          />
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
                    ? "rounded-md bg-amber-400/20 px-3 py-1.5 font-medium text-amber-200"
                    : "rounded-md px-3 py-1.5 text-zinc-300 hover:bg-white/10 hover:text-zinc-50"
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
