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
