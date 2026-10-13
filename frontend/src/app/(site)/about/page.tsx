import type { Metadata } from "next";

import { CtaBand } from "@/components/site/Sections";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "About",
  description:
    "Forge is the solo, remote web engineer behind AdyraForge, a freelance brand under Adyra Group.",
  alternates: { canonical: "/about" },
};

// The operational stack as listed on the v1 site.
const STACK = [
  "HTML5",
  "CSS3",
  "JavaScript",
  "React",
  "Tailwind",
  "Node.js",
  "Python",
  "Django / Flask",
  "Java",
];

export default function AboutPage() {
  return (
    <>
      <article className="mx-auto max-w-3xl px-5 pt-16">
        <p className="text-xs uppercase tracking-[0.2em] text-gold">About</p>
        <h1 className="mt-3 font-display text-4xl font-bold sm:text-5xl">Behind the forge</h1>
        <div className="mt-8 space-y-5 text-lg text-ink/85">
          <p>
            I&apos;m {site.founder}, a solo, remote web engineer and the developer behind{" "}
            {site.name}, a freelance brand operating under the {site.parent} umbrella.
          </p>
          <p>
            My commitment is to deliver high-quality, high-performance web products. I combine
            architectural logic with creative design, and every line of code is written with
            functional stability, layout accuracy and fast loading in mind.
          </p>
          <p>
            Working with me means working directly with the person who builds your site, with a
            private client portal for progress, files and invoices.
          </p>
          <p>
            {site.name} serves clients as an agile freelance operation today; the long-term
            blueprint is to grow it into an independent technology firm.
          </p>
        </div>
        <h2 className="mt-12 font-display text-2xl font-bold">Stack</h2>
        <ul className="mt-4 flex flex-wrap gap-2">
          {STACK.map((s) => (
            <li key={s} className="rounded border border-ink/15 px-3 py-1 text-sm">
              {s}
            </li>
          ))}
        </ul>
      </article>
      <CtaBand />
    </>
  );
}
