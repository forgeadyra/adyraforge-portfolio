import { site } from "@/lib/site";

/**
 * Structured data. "<" is escaped so CMS/API text can never close the script
 * element and inject markup (the payload includes admin-entered content).
 */
export function JsonLd({ data }: { data: Record<string, unknown> }) {
  const json = JSON.stringify(data).replace(/</g, "\\u003c");
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: json }} />;
}

export const organizationLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  "@id": `${site.url}/#organization`,
  name: site.name,
  url: site.url,
  email: site.email,
  description: site.description,
  founder: { "@id": `${site.url}/#founder` },
  parentOrganization: { "@type": "Organization", name: site.parent },
  sameAs: [site.links.fiverr, site.links.github],
};

export const personLd = {
  "@context": "https://schema.org",
  "@type": "Person",
  "@id": `${site.url}/#founder`,
  name: site.founder,
  jobTitle: "Web engineer",
  worksFor: { "@id": `${site.url}/#organization` },
  url: `${site.url}/about`,
  sameAs: [site.links.github],
};
