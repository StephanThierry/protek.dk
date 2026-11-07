import './style.css';
import { createFluid, absorbance } from './fluid.js';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const coarse = matchMedia('(pointer: coarse)').matches;
const rand = (a, b) => a + Math.random() * (b - a);
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

// --------------------------------------------------------- text and numbers
$$('[data-years-since]').forEach((el) => {
  const n = new Date().getFullYear() - parseInt(el.dataset.yearsSince, 10);
  if (n > 0) el.textContent = n;
});
if (coarse) $('[data-hint-text]').textContent = 'Stryg over skærmen for at røre i vandet. Tryk for at dryppe blæk.';

// --------------------------------------------------------- ink
const HEX = { indigo: 0x2b3a8c, vermilion: 0xd2462a, ochre: 0xd9a21b, teal: 0x1e7f78, rose: 0xb8325e, sumi: 0x1a1a22 };
const INK = Object.fromEntries(Object.entries(HEX).map(([k, v]) => [k, absorbance(v)]));
const inkOf = (name, s = 1) => INK[name || 'indigo'].clone().multiplyScalar(s);
let current = 'indigo';

// --------------------------------------------------------- water
const canvas = $('#tray');
let fluid = null;

async function boot(retry = false) {
  if (!('WebGPU' in window) && !document.createElement('canvas').getContext('webgl2')) return;
  try {
    fluid = await createFluid(canvas, { forceWebGL: new URLSearchParams(location.search).has('webgl') });
  } catch (e) {
    console.warn('Ebru: no GPU simulation', e);
    fluid = null;
    return;
  }
  document.body.classList.add('has-gpu');
  fluid.onLost(async () => {
    fluid.dispose(); fluid = null;
    document.body.classList.remove('has-gpu');
    if (!retry) { await wait(300); boot(true); }
  });
  await document.fonts.load('600 100px "Fraunces"').catch(() => {});
  writeName();
  if (!reduced) welcome();
  tickMeta();
}

function writeName() {
  if (!fluid) return;
  const portrait = innerHeight > innerWidth;
  fluid.writeText(
    [{ text: 'Stephan', channel: 'r' }, { text: 'Thierry', channel: 'g' }],
    inkOf('indigo', 1.35), inkOf('vermilion', 1.25),
    { y: portrait ? 0.44 : 0.47, size: portrait ? 0.11 : 0.19 },
  );
}

// a few drops around the name so the water is alive from the start; the name stays until someone stirs it
async function welcome() {
  await wait(700);
  const spots = [[0.12, 0.2, 'ochre'], [0.88, 0.24, 'teal'], [0.16, 0.78, 'rose'], [0.92, 0.56, 'ochre'], [0.5, 0.86, 'teal']];
  for (const [x, y, c] of spots) {
    fluid?.drop(x, y, inkOf(c, 1.1), 0.05);
    fluid?.ring(x, y, inkOf('indigo', 0.5), 0.06, 0.008);
    await wait(140);
  }
}

// --------------------------------------------------------- stirring the water
const toUV = (x, y) => [x / canvas.clientWidth, y / canvas.clientHeight];
const interactive = (t) => t.closest && t.closest('a, button, .tools, .bar, input, label');
let last = null, down = false, moved = 0, hinted = false;
const FORCE = 5200;

function hintDone() {
  if (hinted) return;
  hinted = true;
  setTimeout(() => $('[data-hint]')?.classList.add('is-done'), 2500);
}

addEventListener('pointermove', (e) => {
  if (!fluid || e.pointerType === 'touch') return;
  const [x, y] = toUV(e.clientX, e.clientY);
  if (last) {
    const dx = x - last[0], dy = y - last[1];
    moved += Math.abs(dx) + Math.abs(dy);
    if (Math.abs(dx) + Math.abs(dy) > 0.0005) {
      fluid.force(x, y, dx * FORCE, dy * FORCE, down ? 0.03 : 0.024, down ? inkOf(current, 0.22) : null);
      hintDone();
    }
  }
  last = [x, y];
}, { passive: true });
addEventListener('pointerdown', (e) => { if (!interactive(e.target)) { down = true; moved = 0; } }, { passive: true });
addEventListener('pointerup', (e) => {
  const wasDown = down; down = false;
  if (!fluid || !wasDown || interactive(e.target) || moved > 0.02) return;
  const [x, y] = toUV(e.clientX, e.clientY);
  dropAt(x, y, current);
  hintDone();
});
addEventListener('pointerleave', () => { last = null; down = false; });

// touch: a swipe stirs, even while the page scrolls; a tap drips
let touchLast = null;
addEventListener('touchstart', (e) => { const t = e.touches[0]; touchLast = toUV(t.clientX, t.clientY); }, { passive: true });
addEventListener('touchmove', (e) => {
  if (!fluid || !touchLast) return;
  const t = e.touches[0];
  const [x, y] = toUV(t.clientX, t.clientY);
  fluid.force(x, y, (x - touchLast[0]) * FORCE * 0.8, (y - touchLast[1]) * FORCE * 0.8, 0.04);
  touchLast = [x, y];
  hintDone();
}, { passive: true });

function dropAt(x, y, name, big = 1) {
  if (!fluid) return;
  // an ebru drop: colour in the middle and a thin darker rim, as when the pigment pushes the water away
  const r = rand(0.035, 0.055) * big;
  fluid.drop(x, y, inkOf(name, 1.15), r);
  fluid.ring(x, y, inkOf(name, 0.9), r * 1.15, r * 0.22);
}

// --------------------------------------------------------- scroll drags the water along
let lastY = scrollY;
addEventListener('scroll', () => {
  const d = scrollY - lastY; lastY = scrollY;
  if (fluid && !reduced) fluid.drift(0, -Math.max(-60, Math.min(60, d)) * 7);
}, { passive: true });

// --------------------------------------------------------- scenes per section
const scenes = {
  // battal: the water is sprinkled with colours and a comb is dragged back and forth (gel-git)
  async origin() {
    for (let i = 0; i < 16; i++) {
      dropAt(rand(0.05, 0.95), rand(0.12, 0.92), ['ochre', 'vermilion', 'indigo', 'teal'][i % 4], 0.85);
      await wait(70);
    }
    await wait(600);
    fluid?.comb({ freq: 7, axis: 0, alt: true, amp: 1.6, ms: 1500 });
  },
  // taraklı: four colours side by side and a vertical comb through them
  async github() {
    const inks = ['indigo', 'teal', 'vermilion', 'ochre'];
    for (let i = 0; i < 8; i++) { dropAt(0.1 + (i % 4) * 0.27, i < 4 ? 0.3 : 0.7, inks[i % 4], 1.4); await wait(90); }
    await wait(500);
    fluid?.comb({ freq: 11, axis: 1, alt: false, amp: 1.5, ms: 1600 });
  },
  // bülbül yuvası (nightingale's nest): small swirls spin the colours into spirals
  async poi() {
    const pts = [[0.2, 0.35], [0.5, 0.65], [0.8, 0.38]];
    pts.forEach(([x, y], i) => { dropAt(x, y, ['vermilion', 'sumi', 'rose'][i], 1.3); fluid?.ring(x, y, inkOf('ochre', 0.9), 0.085, 0.01); });
    await wait(300);
    for (let k = 0; k < 24; k++) {
      pts.forEach(([x, y], i) => fluid?.swirl(x, y, (i % 2 ? -1 : 1) * 5, 0.1));
      await wait(30);
    }
  },
  // tulip: rings within rings, then a needle is drawn up through the middle
  async contact() {
    const wide = innerWidth > 860;
    // on mobile the tulip sits above the text; y distances are scaled so the shape is not stretched in portrait
    const x = wide ? 0.74 : 0.5, y = wide ? 0.62 : 0.3, s = Math.min(1, innerWidth / innerHeight);
    const layers = [['rose', 0.11], ['ochre', 0.075], ['vermilion', 0.05], ['sumi', 0.022]];
    for (const [c, r] of layers) { fluid?.drop(x, y, inkOf(c, 1.2), r); await wait(160); }
    await wait(400);
    for (let k = 0; k < 18; k++) { fluid?.force(x, y + (0.04 - k * 0.012) * s, 0, -120, 0.018); await wait(24); }
    await wait(250);
    // two leaves
    const lx = wide ? 0.08 : 0.13, ly = 0.16 * s;
    fluid?.drop(x - lx, y + ly, inkOf('teal', 1.2), 0.03);
    fluid?.drop(x + lx, y + ly, inkOf('teal', 1.2), 0.03);
    for (let k = 0; k < 10; k++) {
      fluid?.force(x - lx + k * lx * 0.075, y + ly - k * ly * 0.0375, 70, -70, 0.016);
      fluid?.force(x + lx - k * lx * 0.075, y + ly - k * ly * 0.0375, -70, -70, 0.016);
      await wait(24);
    }
  },
};

const played = new Set();
const sceneIO = new IntersectionObserver((entries) => {
  for (const en of entries) {
    if (!en.isIntersecting) continue;
    const name = en.target.dataset.scene;
    if (!fluid || reduced || played.has(name) || !scenes[name]) continue;
    played.add(name);
    scenes[name]();
  }
}, { threshold: 0.35 });
$$('[data-scene]').forEach((s) => sceneIO.observe(s));

// the menu highlights the section crossing the middle of the screen (the CV is too tall for a threshold)
const navIO = new IntersectionObserver((entries) => {
  for (const en of entries) {
    if (!en.isIntersecting) continue;
    $$('.bar__nav a').forEach((a) => a.setAttribute('aria-current', String(a.getAttribute('href') === `#${en.target.id}`)));
  }
}, { rootMargin: '-50% 0px -50% 0px' });
$$('[data-scene]').forEach((s) => navIO.observe(s));

// CV: each workplace drips its colour when its card reaches the middle of the screen
const yearOut = $('[data-year-out]');
const jobIO = new IntersectionObserver((entries) => {
  for (const en of entries) {
    if (!en.isIntersecting) continue;
    const job = en.target;
    job.classList.add('is-in');
    if (job.dataset.year && yearOut) yearOut.textContent = job.dataset.year;
    if (job.dataset.dropped || !fluid || reduced) continue;
    job.dataset.dropped = '1';
    const wide = innerWidth > 860;
    const x = wide ? rand(0.08, 0.36) : rand(0.15, 0.85);
    const y = rand(0.25, 0.8);
    dropAt(x, y, job.dataset.ink, 1.3);
    setTimeout(() => fluid?.swirl(x, y, rand(-14, 14), 0.08), 300);
  }
}, { rootMargin: '-35% 0px -35% 0px' });
$$('.job').forEach((j) => jobIO.observe(j));
// cards must also become visible without reaching the middle (e.g. the last card on a tall screen)
const showIO = new IntersectionObserver((entries) => entries.forEach((en) => en.isIntersecting && en.target.classList.add('is-in')), { threshold: 0.15 });
$$('.job').forEach((j) => showIO.observe(j));

// --------------------------------------------------------- tool tray
$$('.ink').forEach((b) => b.addEventListener('click', () => {
  current = b.dataset.ink;
  $$('.ink').forEach((o) => o.setAttribute('aria-checked', String(o === b)));
  dropAt(rand(0.3, 0.7), rand(0.3, 0.6), current);
}));
$('[data-act="comb"]').addEventListener('click', () => {
  const kinds = [{ axis: 0, alt: true, freq: 6 }, { axis: 1, alt: false, freq: 10 }, { axis: 1, alt: true, freq: 5 }, { axis: 0, alt: false, freq: 12 }];
  fluid?.comb({ ...kinds[Math.floor(Math.random() * kinds.length)], amp: 1.6, ms: 1500 });
});
$('[data-act="name"]').addEventListener('click', () => { scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' }); writeName(); });
$('[data-act="clear"]').addEventListener('click', () => { fluid?.clear(); played.clear(); });

const meta = $('[data-meta]');
const tech = $('[data-tech]');
function tickMeta() {
  if (!fluid) return;
  meta.textContent = `${fluid.backend} · ${fluid.cells} · ${fluid.fps} fps`;
  tech.textContent = `Vandet er en Navier–Stokes-simulering (${fluid.cells} celler) skrevet i three.js TSL og kørt på din GPU via ${fluid.backend}.`;
  setTimeout(tickMeta, 1000);
}

let rT;
addEventListener('resize', () => {
  clearTimeout(rT);
  rT = setTimeout(() => { if (fluid && fluid.resize()) writeName(); }, 150);
});

// --------------------------------------------------------- GitHub stats (cached for an hour)
(() => {
  const USER = 'StephanThierry', KEY = 'protek-gh';
  const starsEl = $('[data-gh-stars]'), reposEl = $('[data-gh-repos]');
  const set = (s, r) => { starsEl.textContent = s; reposEl.textContent = r; };
  try {
    const c = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (c) { set(c.stars, c.repos); if (Date.now() - c.t < 3600e3) return; }
  } catch (e) { /* ignore */ }
  fetch(`https://api.github.com/users/${USER}/repos?per_page=100&type=owner`)
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then((list) => {
      list = list.filter((r) => !r.fork);
      const sum = list.reduce((a, r) => a + (r.stargazers_count || 0), 0);
      if (!list.length || !sum) return;
      set(sum, list.length);
      try { localStorage.setItem(KEY, JSON.stringify({ t: Date.now(), stars: sum, repos: list.length })); } catch (e) { /* ignore */ }
    })
    .catch(() => {});
})();

document.body.classList.remove('is-loading');
boot();
