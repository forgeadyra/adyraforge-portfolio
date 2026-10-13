/** Public facts about the business, taken from the v1 site. Edit here. */
export const site = {
  name: "AdyraForge",
  url: (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000").replace(/\/+$/, ""),
  tagline: "We forge websites that work as hard as you do.",
  description:
    "AdyraForge is a freelance web development studio building high-performance business websites, landing pages and web applications. Founded by Forge under Adyra Group.",
  founder: "Forge",
  parent: "Adyra Group",
  email: "forgeadyra@gmail.com",
  links: {
    fiverr: "https://www.fiverr.com/adyraforge",
    github: "https://github.com/forgeadyra",
  },
};

export const nav = [
  { href: "/work", label: "Work" },
  { href: "/services", label: "Services" },
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
];

export function formatPrice(amount: number, currency: "INR" | "USD"): string {
  return new Intl.NumberFormat(currency === "INR" ? "en-IN" : "en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
}
