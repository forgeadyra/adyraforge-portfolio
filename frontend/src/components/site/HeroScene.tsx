"use client";

/**
 * The 3D "forge": a faceted, extruded AF monogram inside a low-poly hexagonal
 * ring, slowly rotating and leaning toward the cursor, with a gold rim light
 * and bloom. Loaded only on capable desktop devices, after first paint.
 */

import { Canvas, useFrame } from "@react-three/fiber";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import { useEffect, useMemo, useRef } from "react";
import { ExtrudeGeometry, Path, Shape, type Group, type Mesh } from "three";

import { A_COUNTER, A_OUTER, F_OUTER, MONOGRAM_SHIFT_X, type Point } from "@/lib/monogram";

function toShape(points: Point[]): Shape {
  const shape = new Shape();
  points.forEach(([x, y], i) =>
    i === 0 ? shape.moveTo(x + MONOGRAM_SHIFT_X, y) : shape.lineTo(x + MONOGRAM_SHIFT_X, y),
  );
  shape.closePath();
  return shape;
}

function useMonogramGeometry() {
  return useMemo(() => {
    const a = toShape(A_OUTER);
    const counter = new Path();
    A_COUNTER.forEach(([x, y], i) =>
      i === 0 ? counter.moveTo(x + MONOGRAM_SHIFT_X, y) : counter.lineTo(x + MONOGRAM_SHIFT_X, y),
    );
    a.holes.push(counter);
    const geometry = new ExtrudeGeometry([a, toShape(F_OUTER)], {
      depth: 0.42,
      bevelEnabled: true,
      bevelThickness: 0.09,
      bevelSize: 0.07,
      bevelSegments: 1, // single-step bevel = crisp facets
      curveSegments: 1,
    });
    geometry.center();
    return geometry;
  }, []);
}

function Forge({ pointer }: { pointer: React.RefObject<{ x: number; y: number }> }) {
  const group = useRef<Group>(null);
  const ring = useRef<Mesh>(null);
  const geometry = useMonogramGeometry();

  useFrame((_, delta) => {
    const g = group.current;
    if (!g) return;
    const p = pointer.current ?? { x: 0, y: 0 };
    g.rotation.y += delta * 0.18; // slow idle spin
    // Subtle lean toward the cursor, eased.
    g.rotation.x += (p.y * 0.25 - g.rotation.x) * Math.min(1, delta * 2);
    g.position.x += (p.x * 0.15 - g.position.x) * Math.min(1, delta * 2);
    if (ring.current) ring.current.rotation.z -= delta * 0.08;
  });

  return (
    <group ref={group}>
      <mesh geometry={geometry} castShadow>
        <meshStandardMaterial color="#D4AF37" metalness={0.55} roughness={0.32} flatShading />
      </mesh>
      <mesh ref={ring} rotation={[0, 0, Math.PI / 6]}>
        <torusGeometry args={[2.25, 0.06, 4, 6]} />
        <meshStandardMaterial color="#D4AF37" metalness={0.55} roughness={0.4} flatShading />
      </mesh>
    </group>
  );
}

export default function HeroScene({ active, onReady }: { active: boolean; onReady: () => void }) {
  const pointer = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const move = (e: PointerEvent) => {
      pointer.current = {
        x: (e.clientX / window.innerWidth) * 2 - 1,
        y: (e.clientY / window.innerHeight) * 2 - 1,
      };
    };
    window.addEventListener("pointermove", move, { passive: true });
    return () => window.removeEventListener("pointermove", move);
  }, []);

  return (
    <Canvas
      // Render nothing while hidden or off-screen.
      frameloop={active ? "always" : "never"}
      dpr={[1, 1.5]}
      camera={{ position: [0, 0, 7], fov: 35 }}
      gl={{ antialias: false, alpha: true, powerPreference: "high-performance" }}
      onCreated={() => onReady()}
      aria-hidden="true"
    >
      <ambientLight intensity={0.12} />
      <directionalLight position={[3, 4, 5]} intensity={1.4} color="#F5C66A" />
      {/* Soft gold rim light from behind. */}
      <pointLight position={[-3.5, 1.5, -3]} intensity={40} color="#D4AF37" />
      <pointLight position={[3.5, -1.5, -2.5]} intensity={18} color="#F5C66A" />
      {/* Direct lights only: an environment map's startup cost (PMREM) isn't worth it here. */}
      <directionalLight position={[0, 0, 6]} intensity={0.9} color="#F5C66A" />
      <directionalLight position={[-4, 3, 2]} intensity={0.6} color="#D4AF37" />
      <Forge pointer={pointer} />
      <EffectComposer multisampling={0}>
        <Bloom intensity={0.45} luminanceThreshold={0.75} luminanceSmoothing={0.15} mipmapBlur />
      </EffectComposer>
    </Canvas>
  );
}
