import { ImageResponse } from "next/og";

export const OG_SIZE = { width: 1200, height: 630 };

/** Branded Open Graph card: black, gold accent, big title. No external fonts. */
export function ogCard({
  eyebrow,
  title,
  footer,
}: {
  eyebrow: string;
  title: string;
  footer: string;
}) {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: "72px",
        background: "radial-gradient(circle at 85% 15%, rgba(212,175,55,0.28), #0A0A0B 55%)",
        color: "#F4F1EA",
      }}
    >
      <div
        style={{
          display: "flex",
          fontSize: 30,
          letterSpacing: 6,
          color: "#D4AF37",
          textTransform: "uppercase",
        }}
      >
        {eyebrow}
      </div>
      <div
        style={{
          display: "flex",
          fontSize: title.length > 40 ? 64 : 80,
          fontWeight: 700,
          lineHeight: 1.05,
          maxWidth: 1000,
        }}
      >
        {title}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 30 }}>
        <span style={{ fontWeight: 700 }}>Adyra</span>
        <span style={{ fontWeight: 700, color: "#D4AF37", marginLeft: -16 }}>Forge</span>
        <span style={{ color: "#8A8578", marginLeft: 12 }}>{footer}</span>
      </div>
    </div>,
    OG_SIZE,
  );
}
