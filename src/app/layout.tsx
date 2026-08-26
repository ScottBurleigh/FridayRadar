import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Geist, Geist_Mono } from "next/font/google";
import { SiteHeader } from "@/components/site-header";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "FridayRadar",
    template: "%s · FridayRadar",
  },
  description:
    "High school football programs ranked by 2027-and-later recruiting talent across 247Sports, On3/Rivals, and ESPN.",
  icons: {
    icon: [{ url: "/fridayradar-logo.png", type: "image/png" }],
    apple: "/fridayradar-logo.png",
    shortcut: "/fridayradar-logo.png",
  },
};

export const viewport = {
  themeColor: "#0a1220",
  colorScheme: "dark" as const,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`dark ${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-[#0a1220] text-zinc-100">
        <SiteHeader />
        <div className="flex flex-1 flex-col">{children}</div>
      </body>
    </html>
  );
}
