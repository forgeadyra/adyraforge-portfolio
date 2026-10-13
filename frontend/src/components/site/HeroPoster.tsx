import { A_COUNTER, A_OUTER, F_OUTER, MONOGRAM_SHIFT_X, type Point } from "@/lib/monogram";

const SIZE = 600;
const SCALE = 120;
const CENTER = SIZE / 2;

function pts(points: Point[], dx = 0, dy = 0): string {
  return points
    .map(([x, y]) => `${CENTER + (x + MONOGRAM_SHIFT_X) * SCALE + dx},${CENTER - y * SCALE + dy}`)
    .join(" ");
}

function hexagon(radius: number): string {
  return Array.from({ length: 6 }, (_, i) => {
    const a = (Math.PI / 3) * i + Math.PI / 6;
    return `${CENTER + radius * Math.cos(a)},${CENTER + radius * Math.sin(a)}`;
  }).join(" ");
}

/**
 * Static stand-in for the 3D hero: same monogram and ring, drawn as SVG.
 * Shown first (no layout shift), and permanently on phones, low-end devices,
 * reduced motion and no WebGL.
 */
export function HeroPoster() {
  const depth = 14; // fake extrusion offset in px
  return (
    <svg
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      className="h-full w-full"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <radialGradient id="glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#D4AF37" stopOpacity="0.22" />
          <stop offset="70%" stopColor="#D4AF37" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="face" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#F5C66A" />
          <stop offset="55%" stopColor="#D4AF37" />
          <stop offset="100%" stopColor="#8F7224" />
        </linearGradient>
        <linearGradient id="side" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#7A5F1C" />
          <stop offset="100%" stopColor="#3A2D0D" />
        </linearGradient>
        <mask id="a-mask">
          <polygon points={pts(A_OUTER)} fill="white" />
          <polygon points={pts(A_COUNTER)} fill="black" />
        </mask>
        <mask id="a-mask-back">
          <polygon points={pts(A_OUTER, depth, depth)} fill="white" />
          <polygon points={pts(A_COUNTER, depth, depth)} fill="black" />
        </mask>
      </defs>
      <circle cx={CENTER} cy={CENTER} r={CENTER} fill="url(#glow)" />
      <polygon
        points={hexagon(255)}
        fill="none"
        stroke="#D4AF37"
        strokeOpacity="0.55"
        strokeWidth="6"
      />
      <polygon
        points={hexagon(255)}
        fill="none"
        stroke="#F5C66A"
        strokeOpacity="0.25"
        strokeWidth="1.5"
        transform={`translate(4 4)`}
      />
      {/* extrusion */}
      <rect width={SIZE} height={SIZE} fill="url(#side)" mask="url(#a-mask-back)" />
      <polygon points={pts(F_OUTER, depth, depth)} fill="url(#side)" />
      {/* faces */}
      <rect width={SIZE} height={SIZE} fill="url(#face)" mask="url(#a-mask)" />
      <polygon points={pts(F_OUTER)} fill="url(#face)" />
      <polygon
        points={pts(A_OUTER)}
        fill="none"
        stroke="#FCE7A8"
        strokeOpacity="0.5"
        strokeWidth="1.5"
      />
      <polygon
        points={pts(F_OUTER)}
        fill="none"
        stroke="#FCE7A8"
        strokeOpacity="0.5"
        strokeWidth="1.5"
      />
    </svg>
  );
}
