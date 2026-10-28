// XENO ECOSYSTEM — surface history for the metal of the experimental bodies.
//
// A new CG surface is uniformly clean. These materials are patched (onBeforeCompile) so that roughness and colour vary in world space with a deliberate pattern, not as noise
// laid evenly everywhere:
//   brushing      fine anisotropic streaks along one world axis (where the metal was finished), strongest on the chrome parts
//   scratches     thin bright lines at a few preferred angles, sparse and clustered
//   edge wear     paint and polish are rubbed off at creases: found from the screen-space change of the normal (``fwidth``), so it follows the real geometry
//   joint grime   darkening towards joints, bolts and cable fixings, from a per-vertex ``aWear`` weight baked at build time (0 where the attribute is absent)
//   downward grime darkening on faces that look down, where dirt and condensation collect
//   water streaks vertical glossy and darkened runs on vertical faces, strongest below joints
//   staining      glossy dark patches on upward faces (oil-like residue), thresholded from a low-frequency field so that they are patches and not a tint
//   smudges       low-frequency roughness variation (localised polishing and handling)
// The pattern is evaluated only within ``range`` world units of the camera and fades out before it ends, so distant surfaces cost nothing.
import * as THREE from 'three';

export interface Weathering {
  /** 0..1 each */
  brushing: number; scratches: number; edgeWear: number; grime: number; streaks: number; stains: number; smudge: number;
  /** world distance at which the effect has faded out */
  range: number;
}
export const WEATHER_DEFAULT: Weathering = { brushing: 0.5, scratches: 0.5, edgeWear: 0.5, grime: 0.5, streaks: 0.5, stains: 0.5, smudge: 0.5, range: 70 };

const NOISE = /* glsl */ `
float wh(vec3 p){ p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float wn(vec3 x){ vec3 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(wh(i), wh(i + vec3(1,0,0)), f.x), mix(wh(i + vec3(0,1,0)), wh(i + vec3(1,1,0)), f.x), f.y),
             mix(mix(wh(i + vec3(0,0,1)), wh(i + vec3(1,0,1)), f.x), mix(wh(i + vec3(0,1,1)), wh(i + vec3(1,1,1)), f.x), f.y), f.z); }
float wf(vec3 p){ return 0.55 * wn(p) + 0.3 * wn(p * 2.1 + 3.7) + 0.15 * wn(p * 4.3 + 8.1); }
`;

/** Patch a standard material with the weathering pattern. The material is modified in place and returned. */
export function weather<T extends THREE.MeshStandardMaterial>(mat: T, w: Weathering = WEATHER_DEFAULT): T {
  const key = `weather:${w.brushing}:${w.scratches}:${w.edgeWear}:${w.grime}:${w.streaks}:${w.stains}:${w.smudge}:${w.range}`;
  mat.onBeforeCompile = (shader) => {
    shader.uniforms.wBrush = { value: w.brushing }; shader.uniforms.wScr = { value: w.scratches }; shader.uniforms.wEdge = { value: w.edgeWear };
    shader.uniforms.wGrime = { value: w.grime }; shader.uniforms.wStreak = { value: w.streaks }; shader.uniforms.wStain = { value: w.stains };
    shader.uniforms.wSmudge = { value: w.smudge }; shader.uniforms.wRange = { value: w.range };
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nattribute float aWear;\nvarying vec3 vWPos;\nvarying vec3 vWN;\nvarying float vWear;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvWPos = (modelMatrix * vec4(transformed, 1.0)).xyz;\nvWN = normalize(mat3(modelMatrix) * objectNormal);\nvWear = aWear;');
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', `#include <common>\nuniform float wBrush, wScr, wEdge, wGrime, wStreak, wStain, wSmudge, wRange;\nvarying vec3 vWPos;\nvarying vec3 vWN;\nvarying float vWear;\n${NOISE}`)
      .replace('#include <roughnessmap_fragment>', `#include <roughnessmap_fragment>
        {
          float wd = distance(vWPos, cameraPosition), fade = 1.0 - smoothstep(wRange * 0.55, wRange, wd);
          if (fade > 0.001) {
            vec3 p = vWPos, n = normalize(vWN);
            float up = clamp(n.y, 0.0, 1.0), down = clamp(-n.y, 0.0, 1.0), vert = 1.0 - abs(n.y);
            // brushing: a stretched field along world x, and a second one along z on the faces that look along x
            float brush = wn(vec3(p.x * 2.0, p.y * 38.0, p.z * 38.0)) * (1.0 - abs(n.x)) + wn(vec3(p.x * 38.0, p.y * 38.0, p.z * 2.0)) * abs(n.x);
            // scratches: sparse thin lines at three angles, clustered by a low-frequency mask
            float cl = smoothstep(0.55, 0.8, wf(p * 0.35 + 11.0));
            float s1 = 1.0 - smoothstep(0.0, 0.045, abs(wn(vec3(dot(p.xz, vec2(0.8, 0.6)) * 22.0, p.y * 3.0, 1.0)) - 0.5));
            float s2 = 1.0 - smoothstep(0.0, 0.04, abs(wn(vec3(dot(p.xz, vec2(-0.5, 0.86)) * 26.0, p.y * 2.0, 5.0)) - 0.5));
            float scr = (s1 + s2) * cl;
            // edge wear from the change of the normal across the pixel, and joint grime from the baked weight
            float crease = clamp(length(fwidth(n)) * 9.0, 0.0, 1.0);
            float edgeMask = smoothstep(0.15, 0.7, crease) * wEdge;
            float jointMask = clamp(vWear, 0.0, 1.0) * wGrime;
            float low = wf(p * 0.9 + 2.0);
            float grime = clamp(jointMask * (0.55 + 0.6 * low) + down * 0.35 * wGrime * (0.4 + low) + low * 0.12 * wGrime, 0.0, 1.0);
            // water streaks: vertical runs, longer and more frequent below the joints
            float st = pow(wn(vec3(p.x * 14.0 + p.z * 11.0, p.y * 0.7, 3.0)), 2.2) * vert * wStreak * (0.35 + 0.9 * clamp(vWear, 0.0, 1.0) + 0.3 * low);
            // oil-like patches on upward faces
            float stain = smoothstep(0.64, 0.72, wf(p * 0.7 + 9.0)) * up * wStain;
            float smudge = (wf(p * 1.6 + 4.0) - 0.5) * wSmudge;
            float r = roughnessFactor;
            r += (brush - 0.5) * 0.3 * wBrush * fade;
            r -= scr * 0.22 * wScr * fade;
            r -= edgeMask * 0.16 * fade;
            r += grime * 0.3 * fade + smudge * 0.35 * fade;
            r -= st * 0.3 * fade;
            r -= stain * 0.28 * fade;
            roughnessFactor = clamp(r, 0.05, 1.0);
            diffuseColor.rgb *= 1.0 - fade * (grime * 0.32 + st * 0.25 + stain * 0.3);
            diffuseColor.rgb += fade * (edgeMask * 0.16 + scr * 0.1 * wScr);
          }
        }`);
  };
  mat.customProgramCacheKey = () => key;
  return mat;
}

/** Set the per-vertex wear weight of a geometry to a constant (hubs and clamps carry more than long tubes). */
export function setWear(g: THREE.BufferGeometry, value: number): THREE.BufferGeometry {
  const n = g.getAttribute('position').count, a = new Float32Array(n).fill(value);
  g.setAttribute('aWear', new THREE.BufferAttribute(a, 1));
  return g;
}
