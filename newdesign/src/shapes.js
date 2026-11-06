// Formerne, partiklerne samler sig i. Hver form er N punkter (xyz) + N farver (rgb).
// Alle punkter er i verdenskoordinater omkring (0,0,0); layout-forskydning lægges på i main.js.

const TAU = Math.PI * 2;

function hex(c) {
  const n = parseInt(c.slice(1), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}
export const PAL = {
  mint: hex('#7CF0C2'),
  ice: hex('#E9F0EE'),
  teal: hex('#2BB3A6'),
  deep: hex('#1C5E6B'),
  coral: hex('#FF8A5B'),
  gold: hex('#FFD27A'),
  violet: hex('#9B8CFF'),
  blueD: hex('#1E6F9F'),
  blueM: hex('#3BA3D9'),
  blueL: hex('#9FDDF7'),
};

function mixc(a, b, t) {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

// Lille deterministisk PRNG, så formerne er ens ved hver genopbygning (resize).
function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function gauss(r) {
  return Math.sqrt(-2 * Math.log(r() + 1e-9)) * Math.cos(TAU * r());
}

function inPoly(x, y, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function samplePoly(r, poly) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const [x, y] of poly) { minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y); }
  for (let k = 0; k < 200; k++) {
    const x = minX + r() * (maxX - minX), y = minY + r() * (maxY - minY);
    if (inPoly(x, y, poly)) return [x, y];
  }
  return poly[0];
}

function polyArea(p) {
  let a = 0;
  for (let i = 0, j = p.length - 1; i < p.length; j = i++) a += (p[j][0] + p[i][0]) * (p[j][1] - p[i][1]);
  return Math.abs(a / 2);
}

// ---------------------------------------------------------------- formerne

// 0 · Tåge: en levende kugleskal med en svag galaksearm. Hero.
function nebula(i, r, out, col) {
  const u = r();
  if (u < 0.72) {
    const th = TAU * r(), ph = Math.acos(2 * r() - 1);
    const rad = 2.6 + gauss(r) * 0.12;
    out[0] = rad * Math.sin(ph) * Math.cos(th);
    out[1] = rad * Math.cos(ph);
    out[2] = rad * Math.sin(ph) * Math.sin(th);
    const t = (out[1] / rad) * 0.5 + 0.5;
    col.push(...mixc(PAL.teal, PAL.mint, t * r()));
  } else {
    // ring/skive rundt om kuglen
    const a = TAU * r(), rad = 3.4 + r() * 2.2;
    out[0] = Math.cos(a) * rad;
    out[1] = gauss(r) * 0.06 + Math.sin(a) * rad * 0.18;
    out[2] = Math.sin(a) * rad;
    col.push(...mixc(PAL.coral, PAL.gold, r()));
  }
}

// 1 · Protek-stjernen, punkterne taget direkte fra SVG-logoet (viewBox 1000, centrum 520,490).
const STAR = [
  ['d', [[257, 197], [468, 378], [520, 490], [420, 412]]],
  ['d', [[177, 684], [450, 490], [520, 490], [420, 585]]],
  ['d', [[717, 694], [610, 537], [520, 490], [580, 582]]],
  ['m', [[424, 45], [540, 430], [505, 500], [462, 400]]],
  ['m', [[283, 880], [465, 520], [520, 490], [500, 575]]],
  ['m', [[925, 538], [585, 458], [520, 490], [612, 538]]],
  ['l', [[117, 352], [512, 430], [520, 490], [485, 528]]],
  ['l', [[640, 980], [572, 488], [520, 470], [485, 528]]],
  ['l', [[731, 242], [572, 488], [520, 490], [512, 430]]],
].map(([k, p]) => [k, p.map(([x, y]) => [(x - 520) / 1000 * 6.4, -(y - 490) / 1000 * 6.4])]);
const STAR_AREA = STAR.map(([, p]) => polyArea(p));
const STAR_TOTAL = STAR_AREA.reduce((a, b) => a + b, 0);

function star(i, r, out, col) {
  const u = r();
  if (u < 0.22) {
    const ring = r() < 0.6 ? 470 : 330;
    const a = TAU * r(), rad = ring / 1000 * 6.4 + gauss(r) * 0.015;
    out[0] = Math.cos(a) * rad; out[1] = Math.sin(a) * rad; out[2] = gauss(r) * 0.04;
    col.push(...mixc(PAL.blueM, PAL.ice, r() * 0.5));
    return;
  }
  let pick = r() * STAR_TOTAL, idx = 0;
  while (pick > STAR_AREA[idx] && idx < STAR.length - 1) pick -= STAR_AREA[idx++];
  const [kind, poly] = STAR[idx];
  const [x, y] = samplePoly(r, poly);
  out[0] = x; out[1] = y;
  // spidserne løfter sig ud mod beskueren, mere jo længere fra centrum
  out[2] = (r() - 0.5) * 0.18 + Math.hypot(x, y) * 0.08 * (kind === 'l' ? 1 : kind === 'm' ? 0 : -1);
  col.push(...(kind === 'd' ? PAL.blueD : kind === 'm' ? PAL.blueM : PAL.blueL));
}

// 2 · Karriere-helix: en dobbeltspiral langs x, med en lysende knude per arbejdsplads.
export const HELIX_LEN = 34;
export const HELIX_NODES = 10;
function helix(i, r, out, col) {
  const u = r();
  const R = 1.25;
  if (u < 0.16) {
    // knuder (arbejdspladser)
    const n = Math.floor(r() * HELIX_NODES);
    const x = -HELIX_LEN / 2 + (n + 0.5) * (HELIX_LEN / HELIX_NODES);
    const th = TAU * r(), ph = Math.acos(2 * r() - 1), rad = 0.55 * Math.cbrt(r());
    out[0] = x + rad * Math.sin(ph) * Math.cos(th);
    out[1] = rad * Math.cos(ph);
    out[2] = rad * Math.sin(ph) * Math.sin(th);
    col.push(...mixc(PAL.gold, PAL.coral, n / (HELIX_NODES - 1)));
    return;
  }
  const t = r();
  const x = -HELIX_LEN / 2 - 2 + t * (HELIX_LEN + 4);
  const a = x * 0.9;
  if (u < 0.3) {
    // tværstænger mellem strengene
    const k = Math.round(a / 0.9) * 0.9, s = r() * 2 - 1;
    const xx = k / 0.9;
    out[0] = xx; out[1] = Math.cos(k) * R * s; out[2] = Math.sin(k) * R * s;
    col.push(...mixc(PAL.deep, PAL.teal, 0.5));
    return;
  }
  const off = r() < 0.5 ? 0 : Math.PI;
  out[0] = x + gauss(r) * 0.04;
  out[1] = Math.cos(a + off) * R + gauss(r) * 0.05;
  out[2] = Math.sin(a + off) * R + gauss(r) * 0.05;
  col.push(...mixc(PAL.teal, PAL.violet, t));
}

// 3 · GitHub-stjerne: femtakket, med volumen.
const GH = (() => {
  const p = [];
  for (let k = 0; k < 10; k++) {
    const a = Math.PI / 2 + (k * TAU) / 10, rad = k % 2 ? 1.25 : 3;
    p.push([Math.cos(a) * rad, Math.sin(a) * rad]);
  }
  return p;
})();
function ghStar(i, r, out, col) {
  const u = r();
  if (u < 0.3) {
    // kanter
    const k = Math.floor(r() * 10), a = GH[k], b = GH[(k + 1) % 10], t = r();
    out[0] = a[0] + (b[0] - a[0]) * t; out[1] = a[1] + (b[1] - a[1]) * t; out[2] = (r() - 0.5) * 0.5;
    col.push(...PAL.ice);
  } else if (u < 0.88) {
    const [x, y] = samplePoly(r, GH);
    out[0] = x; out[1] = y; out[2] = (r() - 0.5) * 0.5 * (1 - Math.hypot(x, y) / 3.2);
    col.push(...mixc(PAL.gold, PAL.coral, Math.hypot(x, y) / 3));
  } else {
    // støv omkring
    const a = TAU * r(), rad = 3.6 + r() * 3;
    out[0] = Math.cos(a) * rad; out[1] = Math.sin(a) * rad; out[2] = gauss(r) * 1.2;
    col.push(...mixc(PAL.deep, PAL.gold, r() * 0.4));
  }
}

// 4 · Knude: torus-knude (2,3). Points of interest, alt hænger sammen.
function knot(i, r, out, col) {
  const t = r() * TAU, p = 2, q = 3;
  const cx = (2 + Math.cos(q * t)) * Math.cos(p * t);
  const cy = (2 + Math.cos(q * t)) * Math.sin(p * t);
  const cz = -Math.sin(q * t);
  // tangent og normaler via differens
  const e = 0.001, t2 = t + e;
  const nx = (2 + Math.cos(q * t2)) * Math.cos(p * t2) - cx;
  const ny = (2 + Math.cos(q * t2)) * Math.sin(p * t2) - cy;
  const nz = -Math.sin(q * t2) - cz;
  const tl = Math.hypot(nx, ny, nz);
  const T = [nx / tl, ny / tl, nz / tl];
  let B = [T[1], -T[0], 0]; // T x (0,0,1)
  const bl = Math.hypot(...B) || 1; B = B.map((v) => v / bl);
  const N = [B[1] * T[2] - B[2] * T[1], B[2] * T[0] - B[0] * T[2], B[0] * T[1] - B[1] * T[0]];
  const a = TAU * r(), rad = 0.42 * Math.sqrt(r() * 0.25 + 0.75);
  const s = 1.05;
  out[0] = (cx + (Math.cos(a) * N[0] + Math.sin(a) * B[0]) * rad) * s;
  out[1] = (cy + (Math.cos(a) * N[1] + Math.sin(a) * B[1]) * rad) * s;
  out[2] = (cz + (Math.cos(a) * N[2] + Math.sin(a) * B[2]) * rad) * s;
  col.push(...mixc(PAL.violet, PAL.mint, (Math.sin(t * 3) + 1) / 2));
}

// 5 · @: samples fra et canvas med tegnet. Kontakt.
let atPts = null;
function atSamples() {
  if (atPts) return atPts;
  const S = 256, c = document.createElement('canvas');
  c.width = c.height = S;
  const g = c.getContext('2d');
  g.fillStyle = '#fff';
  g.textAlign = 'center'; g.textBaseline = 'middle';
  g.font = `700 ${S * 0.95}px Archivo, Arial, sans-serif`;
  g.fillText('@', S / 2, S / 2 + S * 0.03);
  const d = g.getImageData(0, 0, S, S).data, pts = [];
  for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) if (d[(y * S + x) * 4 + 3] > 128) pts.push([(x / S - 0.5) * 6, -(y / S - 0.5) * 6]);
  atPts = pts.length ? pts : [[0, 0]];
  return atPts;
}
function at(i, r, out, col) {
  const pts = atSamples();
  const p = pts[Math.floor(r() * pts.length)];
  const j = 6 / 256;
  out[0] = p[0] + (r() - 0.5) * j; out[1] = p[1] + (r() - 0.5) * j; out[2] = (r() - 0.5) * 0.35;
  col.push(...mixc(PAL.mint, PAL.ice, r() * 0.6));
}

export const SHAPES = [nebula, star, helix, ghStar, knot, at];
export const CV_INDEX = 2;

// Bygger positions- og farvedata for alle former.
// layout[i] = { x, y, s } (forskydning og skala per form), rnd = delt tilfældighed per partikel.
export function buildShapes(count, layout, rnd) {
  return SHAPES.map((fn, si) => {
    const r = rng(1000 + si * 7919);
    const pos = new Float32Array(count * 4);
    const colors = new Float32Array(count * 4);
    const L = layout[si];
    const out = [0, 0, 0], col = [];
    for (let i = 0; i < count; i++) {
      col.length = 0;
      fn(i, r, out, col);
      pos[i * 4] = out[0] * L.s + L.x;
      pos[i * 4 + 1] = out[1] * L.s + L.y;
      pos[i * 4 + 2] = out[2] * L.s;
      pos[i * 4 + 3] = rnd[i];
      colors[i * 4] = col[0]; colors[i * 4 + 1] = col[1]; colors[i * 4 + 2] = col[2]; colors[i * 4 + 3] = 1;
    }
    return { pos, colors };
  });
}
