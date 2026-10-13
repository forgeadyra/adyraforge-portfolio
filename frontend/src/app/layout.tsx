import type { Metadata } from "next";
import { Inter, Syne } from "next/font/google";
import "./globals.css";

// next/font self-hosts these at build time: no runtime requests to Google.
const syne = Syne({ variable: "--font-syne", subsets: ["latin"], display: "swap" });
const inter = Inter({ variable: "--font-inter", subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: "AdyraForge — websites that work as hard as you do",
  description:
    "AdyraForge builds high-performance business websites, landing pages and web applications. Founded by Forge under Adyra Group.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${syne.variable} ${inter.variable}`}>
      <body className="bg-base text-ink antialiased">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-surface focus:px-4 focus:py-2"
        >
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
