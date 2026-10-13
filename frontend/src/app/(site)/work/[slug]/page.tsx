import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";

import { JsonLd } from "@/components/site/JsonLd";
import { ProjectCard } from "@/components/site/ProjectCard";
import { Reveal } from "@/components/site/Reveal";
import { CtaBand } from "@/components/site/Sections";
import { content } from "@/lib/content";
import { site } from "@/lib/site";

export const revalidate = 3600;
export const dynamicParams = true; // projects published later render on first request

type Props = { params: Promise<{ slug: string }> };

export async function generateStaticParams() {
  const projects = await content.projects();
  return projects.map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const project = await content.project((await params).slug);
  if (!project) return { title: "Project not found" };
  const description =
    project.summary ||
    `${project.title}: a ${project.status === "live" ? "live" : "concept"} project by AdyraForge.`;
  return {
    title: project.title,
    description,
    alternates: { canonical: `/work/${project.slug}` },
    openGraph: { title: project.title, description, type: "article" },
  };
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="border-t border-ink/10 py-10">
      <h2 className="font-display text-2xl font-bold">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export default async function CaseStudyPage({ params }: Props) {
  const project = await content.project((await params).slug);
  if (!project) notFound();

  const creativeWork = {
    "@context": "https://schema.org",
    "@type": "CreativeWork",
    name: project.title,
    description: project.summary || project.solution,
    url: `${site.url}/work/${project.slug}`,
    creator: { "@id": `${site.url}/#organization` },
    keywords: project.technologies.map((t) => t.name).join(", "),
    ...(project.industry ? { about: project.industry } : {}),
    ...(project.live_url ? { sameAs: project.live_url } : {}),
    ...(project.cover_image ? { image: project.cover_image } : {}),
    dateModified: project.updated_at,
  };

  return (
    <>
      <JsonLd data={creativeWork} />
      <article className="mx-auto max-w-4xl px-5 pt-14">
        <p className="text-sm">
          <Link href="/work">← All work</Link>
        </p>
        <p className="mt-6 text-xs uppercase tracking-[0.2em] text-gold">
          {[project.industry, project.status === "live" ? "Live" : "Concept build"]
            .filter(Boolean)
            .join(" · ")}
        </p>
        <h1 className="mt-3 font-display text-4xl font-bold sm:text-5xl">{project.title}</h1>
        {project.summary && <p className="mt-4 text-lg text-ink/80">{project.summary}</p>}
        {project.client_name && (
          <p className="mt-2 text-sm text-muted">Client: {project.client_name}</p>
        )}
        {project.live_url && (
          <p className="mt-6">
            <a
              href={project.live_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-gold"
            >
              Visit the live site<span className="sr-only"> (opens in a new tab)</span> ↗
            </a>
          </p>
        )}

        {project.cover_image && (
          <div className="relative mt-10 aspect-[16/9] overflow-hidden rounded-xl border border-ink/10">
            <Image
              src={project.cover_image}
              alt={project.cover_alt}
              fill
              priority
              sizes="(min-width: 896px) 896px, 100vw"
              className="object-cover"
            />
          </div>
        )}

        <div className="mt-6">
          {project.problem && (
            <Block title="The problem">
              <p className="whitespace-pre-line text-ink/85">{project.problem}</p>
            </Block>
          )}
          {project.solution && (
            <Block title="What I built">
              <p className="whitespace-pre-line text-ink/85">{project.solution}</p>
            </Block>
          )}
          {project.result_metrics.length > 0 && (
            <Block title="The result">
              <dl className="grid gap-4 sm:grid-cols-3">
                {project.result_metrics.map((m) => (
                  <div key={m.label} className="rounded-lg border border-ink/10 bg-surface p-4">
                    <dt className="text-sm text-muted">{m.label}</dt>
                    <dd className="mt-1 font-display text-2xl font-bold text-gold">{m.value}</dd>
                  </div>
                ))}
              </dl>
            </Block>
          )}
          {project.technologies.length > 0 && (
            <Block title="Stack">
              <ul className="flex flex-wrap gap-2">
                {project.technologies.map((t) => (
                  <li key={t.slug}>
                    <Link
                      href={`/work?tech=${t.slug}`}
                      className="rounded border border-ink/15 px-3 py-1 text-sm text-ink no-underline hover:border-gold/50"
                    >
                      {t.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </Block>
          )}
          {project.gallery.length > 0 && (
            <Block title="Screenshots">
              <Reveal as="ul" className="grid gap-4 sm:grid-cols-2">
                {project.gallery
                  .filter((g) => g.image)
                  .map((g) => (
                    <li key={g.image}>
                      <figure>
                        <div className="relative aspect-[16/10] overflow-hidden rounded-lg border border-ink/10">
                          <Image
                            src={g.image as string}
                            alt={g.alt_text}
                            fill
                            sizes="(min-width: 640px) 50vw, 100vw"
                            className="object-cover"
                          />
                        </div>
                        {g.caption && (
                          <figcaption className="mt-2 text-sm text-muted">{g.caption}</figcaption>
                        )}
                      </figure>
                    </li>
                  ))}
              </Reveal>
            </Block>
          )}
          {project.live_url && (
            <Block title="See it live">
              <a href={project.live_url} target="_blank" rel="noopener noreferrer">
                {project.live_url.replace(/^https:\/\//, "").replace(/\/$/, "")}
                <span className="sr-only"> (opens in a new tab)</span> ↗
              </a>
            </Block>
          )}
        </div>
      </article>

      {project.similar.length > 0 && (
        <section aria-labelledby="similar" className="mx-auto max-w-6xl px-5 py-16">
          <h2 id="similar" className="font-display text-2xl font-bold">
            Similar projects
          </h2>
          <Reveal as="ul" className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {project.similar.map((p) => (
              <li key={p.slug}>
                <ProjectCard project={p} />
              </li>
            ))}
          </Reveal>
        </section>
      )}

      <CtaBand title="Want something like this?" />
    </>
  );
}
