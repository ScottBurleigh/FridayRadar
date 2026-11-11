import type { Viewport } from "next";
import type { ReactNode } from "react";

/** Phone schedule modal uses env(safe-area-inset-*). Other routes keep the root viewport. */
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#0a1220",
  colorScheme: "dark",
};

export default function TournamentsLayout({ children }: { children: ReactNode }) {
  return children;
}
