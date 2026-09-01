import type { MouseEventHandler, ReactNode } from "react";
import type { ProfileLink } from "@/lib/types";

/** School-page / rankings Hudl team chip. Only render when a verified URL exists. */
export function HudlTeamLink({
  href,
  children = "Hudl",
  className = "",
  onClick,
}: {
  href: string;
  children?: ReactNode;
  className?: string;
  onClick?: MouseEventHandler<HTMLAnchorElement>;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className={`text-amber-300/90 hover:underline ${className}`.trim()}
      onClick={onClick}
    >
      {children}
    </a>
  );
}

/** Texan Live / NFHS chips. Only render when a verified URL exists. */
export function WatchLinks({
  texanLiveUrl,
  nfhsUrl,
  className = "",
}: {
  texanLiveUrl?: string | null;
  nfhsUrl?: string | null;
  className?: string;
}) {
  const links: { label: string; href: string }[] = [];
  if (texanLiveUrl) links.push({ label: "Texan Live", href: texanLiveUrl });
  if (nfhsUrl) links.push({ label: "NFHS", href: nfhsUrl });
  if (!links.length) return null;
  return (
    <span className={`inline-flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs ${className}`.trim()}>
      {links.map((link, i) => (
        <span key={link.label} className="inline-flex items-center gap-x-2">
          {i > 0 ? (
            <span className="select-none text-zinc-500" aria-hidden="true">
              ·
            </span>
          ) : null}
          <HudlTeamLink href={link.href} className="text-xs">
            {link.label}
          </HudlTeamLink>
        </span>
      ))}
    </span>
  );
}

export function ProfileLinks({
  links,
  className = "",
}: {
  links: ProfileLink[];
  className?: string;
}) {
  if (!links.length) return null;
  return (
    <p
      className={`flex flex-wrap items-center gap-x-2 gap-y-1 text-sm ${className}`.trim()}
    >
      {links.map((link, i) => (
        <span key={link.label} className="inline-flex items-center gap-x-2">
          {i > 0 ? (
            <span className="select-none text-zinc-500" aria-hidden="true">
              ·
            </span>
          ) : null}
          <a
            href={link.href}
            target="_blank"
            rel="noreferrer"
            className="text-amber-300/90 hover:underline"
          >
            {link.label}
          </a>
        </span>
      ))}
    </p>
  );
}
