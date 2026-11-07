import './style.css';
import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { SplitText } from 'gsap/SplitText';
import Lenis from 'lenis';
import { Particles } from './particles.js';
import { buildShapes, CV_INDEX, HELIX_LEN } from './shapes.js';

gsap.registerPlugin(ScrollTrigger, SplitText);

const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const finePointer = matchMedia('(hover: hover) and (pointer: fine)').matches;
const isMobile = matchMedia('(max-width: 860px)').matches || /Android|iPhone|iPad/i.test(navigator.userAgent);
const sections = [...document.querySelectorAll('main > .sec')];

// Years of experience follow the calendar.
document.querySelectorAll('[data-years-since]').forEach((el) => {
  const n = new Date().getFullYear() - parseInt(el.dataset.yearsSince, 10);
  if (n > 0) el.textContent = n;
});

// ------------------------------------------------------------ smooth scroll
const lenis = reduced ? null : new Lenis({ lerp: 0.09, wheelMultiplier: 0.9, touchMultiplier: 1.4 });
let scrollVel = 0;
if (lenis) {
  lenis.on('scroll', (e) => { ScrollTrigger.update(); scrollVel = e.velocity; });
  gsap.ticker.add((t) => lenis.raf(t * 1000));
  gsap.ticker.lagSmoothing(0);
}
function goTo(target) {
  const el = typeof target === 'number' ? sections[target] : target;
  if (!el) return;
  if (lenis) lenis.scrollTo(el, { duration: 1.6, easing: (t) => 1 - Math.pow(1 - t, 4) });
  else el.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth' });
}
document.querySelectorAll('[data-goto]').forEach((a) => a.addEventListener('click', (e) => {
  e.preventDefault();
  goTo(+a.dataset.goto);
}));

// --------------------------------------------------------------- WebGL scene
let gl = null;
try {
  gl = initGL();
} catch (err) {
  console.warn('WebGL disabled:', err);
  document.documentElement.classList.add('no-gl');
}

function initGL() {
  const canvas = document.getElementById('gl');
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false, powerPreference: 'high-performance' });
  if (!renderer.capabilities.isWebGL2) throw new Error('WebGL2 missing');
  const dpr = Math.min(devicePixelRatio, isMobile ? 1.5 : 1.75);
  renderer.setPixelRatio(dpr);
  renderer.setSize(innerWidth, innerHeight);
  renderer.setClearColor(0x05090b, 1);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, innerWidth / innerHeight, 0.1, 100);
  camera.position.set(0, 0, 12);

  const lowEnd = isMobile || (navigator.hardwareConcurrency || 8) <= 4;
  const SIZE = lowEnd ? 160 : 256; // 25,600 or 65,536 particles
  const particles = new Particles(renderer, SIZE);
  const group = new THREE.Group();
  group.add(particles.points);
  scene.add(group);

  // Layout: where each shape sits, based on visible screen width/height at z=0.
  let layout = [];
  let helixScale = 1;
  function computeLayout() {
    const h = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * camera.position.z;
    const w = h * camera.aspect;
    const narrow = camera.aspect < 1;
    const side = narrow ? 0 : w * 0.21;
    const fit = narrow ? Math.min(1, w / 6.6) : Math.min(1, h / 7.2);
    const up = narrow ? h * 0.2 : 0;
    helixScale = narrow ? 0.75 : 1;
    layout = [
      { x: side, y: up, s: fit * 0.92 },          // nebula
      { x: side, y: up, s: fit },                  // star
      { x: 0, y: narrow ? h * 0.12 : -h * 0.06, s: helixScale }, // helix
      { x: -side, y: up, s: fit * 0.85 },          // GitHub star
      { x: side, y: up, s: fit * 0.92 },           // knot
      { x: side * 1.05, y: narrow ? h * 0.25 : h * 0.04, s: fit * (narrow ? 0.88 : 0.85) }, // prism
      { x: 0, y: narrow ? h * 0.18 : h * 0.17, s: fit * (narrow ? 0.9 : 0.68) }, // @
    ];
    particles.setShapes(buildShapes(particles.count, layout, particles.rnd));
  }
  computeLayout();
  // Narrow screen: shapes sit behind the text, so dim them a bit.
  particles.material.uniforms.uOpacity.value = camera.aspect < 1 ? 0.7 : 1;

  // Post-processing: bloom makes the particles glow.
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth / 2, innerHeight / 2), isMobile ? 0.55 : 0.75, 0.55, 0.08);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());

  particles.material.uniforms.uSize.value = (lowEnd ? 46 : 34) * dpr * (innerHeight / 900);

  let resizeT;
  addEventListener('resize', () => {
    renderer.setSize(innerWidth, innerHeight);
    composer.setSize(innerWidth, innerHeight);
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    particles.material.uniforms.uSize.value = (lowEnd ? 46 : 34) * dpr * (innerHeight / 900);
    clearTimeout(resizeT);
    resizeT = setTimeout(computeLayout, 200);
  });

  // Mouse -> point on plane z=0 (in group local space) so particles avoid the cursor.
  const ndc = new THREE.Vector2(9, 9), ray = new THREE.Raycaster(), plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
  const hit = new THREE.Vector3(), mouseSmooth = new THREE.Vector2();
  let mouseEnergy = 0, lastMove = 0;
  addEventListener('pointermove', (e) => {
    ndc.set((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1);
    lastMove = performance.now();
  }, { passive: true });

  return { renderer, scene, camera, particles, group, composer, ndc, ray, plane, hit, mouseSmooth, get layout() { return layout; }, get helixScale() { return helixScale; },
    get mouseEnergy() { return mouseEnergy; }, set mouseEnergy(v) { mouseEnergy = v; }, get lastMove() { return lastMove; } };
}

// ------------------------------------------------- scroll -> shape state
const state = { a: 0, b: 0, blend: 0, cvP: 0, intro: 1 };
const shiftA = new THREE.Vector3(), shiftB = new THREE.Vector3();

function readScroll() {
  const vh = innerHeight;
  let idx = 0, blend = 0;
  for (let i = 1; i < sections.length; i++) {
    const top = sections[i].getBoundingClientRect().top;
    const k = THREE.MathUtils.clamp((vh * 0.92 - top) / (vh * 0.7), 0, 1);
    if (k > 0) { idx = i; blend = k; }
  }
  if (blend > 0) { state.a = idx - 1; state.b = idx; state.blend = blend; }
  else { state.a = state.b = idx; state.blend = 0; }
  const cv = sections[CV_INDEX].getBoundingClientRect();
  state.cvP = THREE.MathUtils.clamp((vh * 0.3 - cv.top) / (cv.height - vh * 0.6), 0, 1);
}

function helixShift(out) {
  const s = gl.helixScale;
  return out.set((HELIX_LEN * 0.36 - state.cvP * HELIX_LEN * 0.8) * s, 0, 0);
}

// ----------------------------------------------------------------- render
const clock = new THREE.Clock();
function frame() {
  const dt = clock.getDelta(), t = clock.elapsedTime;
  readScroll();
  if (!gl) return;
  const { particles, group, camera, ray, plane, hit, ndc, mouseSmooth } = gl;

  shiftA.set(0, 0, 0); shiftB.set(0, 0, 0);
  if (state.a === CV_INDEX) helixShift(shiftA);
  if (state.b === CV_INDEX) helixShift(shiftB);
  particles.setState(state.a, state.b, state.blend, shiftA, shiftB);

  // Camera and group: slight sway + mouse parallax. Less in CV, where the helix is long.
  mouseSmooth.lerp(ndc.x > 5 ? new THREE.Vector2() : ndc, 0.05);
  const inCv = (state.a === CV_INDEX ? 1 - state.blend : 0) + (state.b === CV_INDEX ? state.blend : 0);
  const sway = reduced ? 0 : 1 - inCv * 0.85;
  group.rotation.y = (Math.sin(t * 0.12) * 0.35 + mouseSmooth.x * 0.25) * sway;
  group.rotation.x = (Math.cos(t * 0.09) * 0.12 - mouseSmooth.y * 0.15) * sway;
  camera.position.x = mouseSmooth.x * 0.35;
  camera.position.y = mouseSmooth.y * 0.25;
  camera.lookAt(0, 0, 0);
  group.updateMatrixWorld();

  // Mouse point in local coordinates.
  const u = particles.simU;
  const moving = performance.now() - gl.lastMove < 120;
  gl.mouseEnergy += ((moving ? 1 : 0.25) - gl.mouseEnergy) * 0.06;
  if (ndc.x < 5) {
    ray.setFromCamera(ndc, camera);
    if (ray.ray.intersectPlane(plane, hit)) u.uMouse.value.copy(group.worldToLocal(hit));
  }
  u.uMouseStr.value = reduced ? 0 : gl.mouseEnergy * (isMobile ? 0.8 : 1.2);
  u.uTurb.value = reduced ? 0.05 : 0.3;
  const kick = Math.min(Math.abs(scrollVel) * 0.03, 1.2) + state.intro * 3;
  u.uKick.value += (kick - u.uKick.value) * 0.1;

  particles.update(t, dt);
  gl.composer.render();
}
gsap.ticker.add(frame);

// -------------------------------------------------------------- intro
const introEl = document.querySelector('.intro');
const countEl = document.querySelector('[data-intro-count]');
const intro = gsap.timeline({ defaults: { ease: 'power3.out' } });
const c = { v: 0 };
if (reduced) {
  introEl.remove();
  state.intro = 0;
} else {
  intro
    .to(c, { v: 100, duration: 1.5, ease: 'power2.inOut', onUpdate: () => (countEl.textContent = Math.round(c.v)) })
    .to(state, { intro: 0, duration: 2.2, ease: 'power2.out' }, 0.5)
    .to('.intro__inner', { yPercent: -40, opacity: 0, duration: 0.7, ease: 'power3.in' }, 1.5)
    .to(introEl, { opacity: 0, duration: 0.8, onComplete: () => introEl.remove() }, 1.9);
}

// ------------------------------------------------------- text animations
document.fonts.ready.then(() => {
  document.querySelectorAll('[data-split]').forEach((el) => {
    if (reduced) return;
    const split = SplitText.create(el, { type: 'lines,chars', mask: 'lines', linesClass: 'line' });
    const first = el.closest('.hero');
    gsap.from(split.chars, {
      yPercent: 115, rotate: 8, opacity: 0,
      duration: 1.1, ease: 'expo.out', stagger: { each: 0.025 },
      delay: first ? 1.7 : 0,
      scrollTrigger: first ? undefined : { trigger: el, start: 'top 85%', toggleActions: 'play none none reverse' },
    });
  });
  ScrollTrigger.refresh();
});

if (!reduced) {
  document.querySelectorAll('[data-fade]').forEach((el) => {
    const hero = el.closest('.hero');
    gsap.from(el, {
      y: 28, opacity: 0, filter: 'blur(8px)', duration: 1.1, ease: 'power3.out',
      delay: hero ? 2.0 + [...hero.querySelectorAll('[data-fade]')].indexOf(el) * 0.12 : 0,
      scrollTrigger: hero ? undefined : { trigger: el, start: 'top 88%', toggleActions: 'play none none reverse' },
    });
  });
  gsap.from('[data-bar]', {
    scaleX: 0, duration: 1.6, ease: 'power3.out', stagger: 0.35,
    scrollTrigger: { trigger: '[data-clock]', start: 'top 82%', toggleActions: 'play none none reverse' },
  });
  gsap.utils.toArray('.job, .tiles li, .card, .origin-card, .design').forEach((el) => {
    gsap.from(el, {
      y: 60, opacity: 0, rotateX: -12, transformPerspective: 900, duration: 1, ease: 'power3.out',
      scrollTrigger: { trigger: el, start: 'top 90%', toggleActions: 'play none none reverse' },
    });
  });
  gsap.from('.bar, .rail-nav', { opacity: 0, y: -12, duration: 1, delay: 2.1, ease: 'power2.out' });
}

// ----------------------------------------------------- CV years
const yearOut = document.querySelector('[data-year-out]');
let curYear = +yearOut.textContent;
const yearObj = { v: curYear };
const jobs = [...document.querySelectorAll('.job[data-year]')];
let activeJob = null;
// The last card whose top has passed 65% of the screen is current. Robust to jumps (nav clicks).
function syncYear() {
  const line = innerHeight * 0.65;
  let cur = jobs[0];
  for (const j of jobs) if (j.getBoundingClientRect().top < line) cur = j;
  if (cur === activeJob) return;
  activeJob?.classList.remove('is-active');
  cur.classList.add('is-active');
  activeJob = cur;
  const y = +cur.dataset.year;
  if (y === curYear) return;
  curYear = y;
  gsap.to(yearObj, { v: y, duration: 0.8, ease: 'power2.out', overwrite: true, onUpdate: () => (yearOut.textContent = Math.round(yearObj.v)) });
}
ScrollTrigger.create({ trigger: '#cv', start: 'top bottom', end: 'bottom top', onUpdate: syncYear, onRefresh: syncYear });

// ----------------------------------------------------- GitHub numbers
(function githubStats() {
  const USER = 'StephanThierry', KEY = 'protek.gh', TTL = 6 * 3600 * 1000;
  const starsEl = document.querySelector('[data-gh-stars]'), reposEl = document.querySelector('[data-gh-repos]');
  let target = +starsEl.textContent;
  let cache = null;
  try { cache = JSON.parse(localStorage.getItem(KEY)); } catch (e) { /* private window */ }
  if (cache && cache.stars > 0) { target = cache.stars; if (cache.repos) reposEl.textContent = cache.repos; }
  starsEl.textContent = reduced ? target : 0;
  // The number follows scroll: 0 when entering at the bottom, total at mid-viewport.
  let st = null;
  const show = () => { if (st) starsEl.textContent = Math.round(st.progress * target); };
  if (!reduced) {
    st = ScrollTrigger.create({ trigger: starsEl, start: 'top bottom', end: 'center center', onUpdate: show, onRefresh: show });
  }
  if (cache && Date.now() - cache.t < TTL) return;
  fetch(`https://api.github.com/users/${USER}/repos?per_page=100&type=owner`)
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then((list) => {
      list = list.filter((r) => !r.fork);
      const sum = list.reduce((a, r) => a + (r.stargazers_count || 0), 0);
      if (!list.length || !sum) return;
      target = sum;
      reposEl.textContent = list.length;
      if (reduced) starsEl.textContent = sum; else show();
      try { localStorage.setItem(KEY, JSON.stringify({ t: Date.now(), stars: sum, repos: list.length })); } catch (e) { /* ignore */ }
    })
    .catch(() => {});
})();

// ---------------------------------------------- navigation and progress
const navLinks = [...document.querySelectorAll('.rail-nav a')];
sections.forEach((sec, i) => {
  ScrollTrigger.create({
    trigger: sec, start: 'top 50%', end: 'bottom 50%',
    onToggle: (self) => self.isActive && navLinks.forEach((a, j) => a.classList.toggle('is-active', i === j)),
  });
});
gsap.to('.progress span', { scaleX: 1, ease: 'none', scrollTrigger: { start: 0, end: 'max', scrub: true } });
gsap.to('.scrollcue', { opacity: 0, scrollTrigger: { start: 0, end: 200, scrub: true } });

// ---------------------------------------------------- micro-interactions
if (finePointer && !reduced) {
  const cursor = document.querySelector('.cursor');
  const xTo = gsap.quickTo(cursor, 'x', { duration: 0.35, ease: 'power3' });
  const yTo = gsap.quickTo(cursor, 'y', { duration: 0.35, ease: 'power3' });
  addEventListener('pointermove', (e) => { xTo(e.clientX); yTo(e.clientY); cursor.classList.add('is-on'); }, { passive: true });
  document.addEventListener('pointerover', (e) => cursor.classList.toggle('is-link', !!e.target.closest('a, button, .rail-nav')));
  document.addEventListener('pointerleave', () => cursor.classList.remove('is-on'));

  document.querySelectorAll('[data-magnet]').forEach((el) => {
    const mx = gsap.quickTo(el, 'x', { duration: 0.6, ease: 'elastic.out(1, 0.4)' });
    const my = gsap.quickTo(el, 'y', { duration: 0.6, ease: 'elastic.out(1, 0.4)' });
    el.addEventListener('pointermove', (e) => {
      const r = el.getBoundingClientRect();
      mx((e.clientX - r.left - r.width / 2) * 0.35);
      my((e.clientY - r.top - r.height / 2) * 0.35);
    });
    el.addEventListener('pointerleave', () => { mx(0); my(0); });
  });

  document.querySelectorAll('[data-tilt]').forEach((el) => {
    el.addEventListener('pointermove', (e) => {
      const r = el.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width - 0.5, py = (e.clientY - r.top) / r.height - 0.5;
      gsap.to(el, { rotateY: px * 10, rotateX: -py * 10, transformPerspective: 800, duration: 0.5, ease: 'power2.out' });
      el.style.setProperty('--mx', `${(px + 0.5) * 100}%`);
      el.style.setProperty('--my', `${(py + 0.5) * 100}%`);
    });
    el.addEventListener('pointerleave', () => gsap.to(el, { rotateY: 0, rotateX: 0, duration: 0.8, ease: 'elastic.out(1, 0.5)' }));
  });
}
