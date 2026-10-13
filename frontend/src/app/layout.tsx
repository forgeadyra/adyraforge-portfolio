import type { Metadata, Viewport } from "next";
import { Inter, Syne } from "next/font/google";

import { site } from "@/lib/site";

import "./globals.css";

// next/font self-hosts these at build time: no runtime requests to Google.
// Syne (display face) ships only its bold cut (~14 KB). With the motion libraries
// deferred, "swap" measured the same LCP as "optional" (2.3 s mobile, CLS 0.024),
// so the brand font is always shown.
const syne = Syne({
  variable: "--font-syne",
  subsets: ["latin"],
  weight: ["700"],
  display: "swap",
});
const inter = Inter({ variable: "--font-inter", subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  metadataBase: new URL(site.url),
  title: {
    default: `${site.name}: websites that work as hard as you do`,
    template: `%s · ${site.name}`,
  },
  description: site.description,
  applicationName: site.name,
  authors: [{ name: site.founder }],
  openGraph: { type: "website", siteName: site.name, locale: "en_US", url: "/" },
  twitter: { card: "summary_large_image" },
  alternates: { canonical: "/" },
};

export const viewport: Viewport = { themeColor: "#0A0A0B", colorScheme: "dark" };

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
