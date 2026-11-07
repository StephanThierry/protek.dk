import './style.css';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

// Years of experience, counted from the start year.
$$('[data-years-since]').forEach((el) => {
  el.textContent = new Date().getFullYear() - Number(el.dataset.yearsSince);
});

// ---------------------------------------------------------------- hero: the live star (GLB from Blender)

(function hero() {
  const canvas = $('#star');
  const stage = $('.hero__stage');
  const hud = $('[data-hud-rot]');
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
  } catch (e) {
    console.warn('WebGL disabled, showing the render instead:', e);
    document.body.classList.add('no-gl');
    return;
  }
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.toneMapping = THREE.AgXToneMapping;
  renderer.toneMappingExposure = 0.95;
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.3;

  const key = new THREE.DirectionalLight(0xfff4e8, 2.2);
  key.position.set(-4, 5, 6);
  const rim = new THREE.DirectionalLight(0x9fddf7, 2.6);
  rim.position.set(5, -2, -4);
  const fill = new THREE.PointLight(0x7cf0c2, 6, 20);
  fill.position.set(-5, -3, 2);
  scene.add(key, rim, fill);

  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
  camera.position.set(0, 0, 12.8);

  // Pivot: user rotation goes on `spin`, the model itself is turned from glTF Y-up to face the camera.
  const spin = new THREE.Group();
  scene.add(spin);

  new GLTFLoader().load('models/star.glb', (gltf) => {
    const m = gltf.scene;
    m.rotation.x = Math.PI / 2;
    m.traverse((o) => {
      if (o.isMesh && o.material && o.material.emissiveIntensity !== undefined && o.name.includes('ring')) {
        o.material.emissiveIntensity *= 1.4;
      }
    });
    spin.add(m);
    document.body.classList.add('gl-ready');
  }, undefined, (e) => {
    console.warn('star.glb failed to load, showing the render instead:', e);
    document.body.classList.add('no-gl');
  });

  // Rotation state: drag with inertia, slow idle spin, slight lean toward the pointer.
  let yaw = -0.35, pitch = -0.5, vy = 0, vp = 0, dragging = false, lx = 0, ly = 0;
  let leanX = 0, leanY = 0, tx = 0, ty = 0;
  stage.addEventListener('pointerdown', (e) => {
    dragging = true; lx = e.clientX; ly = e.clientY;
    stage.setPointerCapture(e.pointerId);
    stage.classList.add('is-dragging');
  });
  stage.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    vy = (e.clientX - lx) * 0.006; vp = (e.clientY - ly) * 0.006;
    yaw += vy; pitch += vp;
    lx = e.clientX; ly = e.clientY;
  });
  const end = () => { dragging = false; stage.classList.remove('is-dragging'); };
  stage.addEventListener('pointerup', end);
  stage.addEventListener('pointercancel', end);
  addEventListener('pointermove', (e) => {
    tx = (e.clientX / innerWidth - 0.5) * 0.3;
    ty = (e.clientY / innerHeight - 0.5) * 0.3;
  }, { passive: true });

  function resize() {
    const r = stage.getBoundingClientRect();
    renderer.setSize(r.width, r.height, false);
    camera.aspect = r.width / r.height;
    camera.position.z = camera.aspect < 0.8 ? 15 : 12.8;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(stage);
  resize();

  let visible = true, last = performance.now();
  new IntersectionObserver(([en]) => { visible = en.isIntersecting; }).observe(stage);

  function frame(now) {
    requestAnimationFrame(frame);
    const dt = Math.min((now - last) / 1000, 0.05);
    last = now;
    if (!visible) return;
    if (!dragging) {
      yaw += vy; pitch += vp;
      vy *= 0.94; vp *= 0.94;
      yaw += dt * (reduced ? 0.05 : 0.18);
      pitch += (-0.5 - pitch) * dt * 0.8; // ease back toward the resting tilt
    }
    leanX += (tx - leanX) * 0.05;
    leanY += (ty - leanY) * 0.05;
    spin.rotation.set(pitch + leanY, yaw + leanX, 0, 'XYZ');
    if (hud) hud.textContent = `rot ${(((yaw * 180 / Math.PI) % 360) + 360).toFixed(0) % 360}°`;
    renderer.render(scene, camera);
  }
  requestAnimationFrame(frame);
})();

// ---------------------------------------------------------------- the three AI dancers (animated GLB from Blender)

(function dancers() {
  const box = $('.dance');
  const canvas = $('#dance');
  if (!box || !canvas) return;
  let started = false;

  const start = () => {
    started = true;
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    } catch (e) {
      box.classList.add('no-gl');
      return;
    }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.toneMapping = THREE.NeutralToneMapping; // keeps the brand colours true
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    const scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environmentIntensity = 0.35;
    const key = new THREE.DirectionalLight(0xfff4e8, 2.4);
    key.position.set(-3, 4, 6);
    const rim = new THREE.DirectionalLight(0x9fddf7, 1.6);
    rim.position.set(4, 2, -5);
    scene.add(key, rim);
    const camera = new THREE.PerspectiveCamera(30, 2.5, 0.1, 100);
    camera.position.set(0, 0.5, 8.5);
    camera.lookAt(0, 0.2, 0);

    let mixer = null;
    new GLTFLoader().load('models/dancers.glb', (gltf) => {
      scene.add(gltf.scene);
      mixer = new THREE.AnimationMixer(gltf.scene);
      gltf.animations.forEach((clip) => mixer.clipAction(clip).play());
      if (reduced) mixer.setTime(9 / 24); // a still pose, no dancing
      box.classList.add('gl-ready');
    }, undefined, (e) => {
      console.warn('dancers.glb failed to load, showing the render instead:', e);
      box.classList.add('no-gl');
    });

    const resize = () => {
      const r = box.getBoundingClientRect();
      renderer.setSize(r.width, r.height, false);
      camera.aspect = r.width / r.height;
      // keep all three in frame on narrow screens
      camera.position.z = camera.aspect < 2.5 ? 8.5 * 2.5 / camera.aspect : 8.5;
      camera.updateProjectionMatrix();
    };
    new ResizeObserver(resize).observe(box);
    resize();

    let visible = true;
    new IntersectionObserver(([en]) => { visible = en.isIntersecting; }).observe(box);
    const timer = new THREE.Timer();
    (function frame() {
      requestAnimationFrame(frame);
      timer.update();
      const dt = timer.getDelta();
      if (!visible) return;
      if (mixer && !reduced) mixer.update(dt);
      renderer.render(scene, camera);
    })();
  };

  // Only spin up the second WebGL context when the block comes close.
  new IntersectionObserver(([en], obs) => {
    if (en.isIntersecting && !started) { obs.disconnect(); start(); }
  }, { rootMargin: '400px 0px' }).observe(box);
})();

// ---------------------------------------------------------------- reveal on scroll

const io = new IntersectionObserver((entries) => {
  entries.forEach((en) => {
    if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); }
  });
}, { rootMargin: '0px 0px -12% 0px' });
$$('.reveal, .job').forEach((el) => io.observe(el));

// ---------------------------------------------------------------- renders: tilt toward the pointer, drift with scroll

if (!reduced) {
  const frames = $$('[data-tilt]');
  frames.forEach((f) => {
    f.addEventListener('pointermove', (e) => {
      const r = f.getBoundingClientRect();
      f.style.setProperty('--rx', `${((e.clientY - r.top) / r.height - 0.5) * -8}deg`);
      f.style.setProperty('--ry', `${((e.clientX - r.left) / r.width - 0.5) * 10}deg`);
    });
    f.addEventListener('pointerleave', () => {
      f.style.setProperty('--rx', '0deg');
      f.style.setProperty('--ry', '0deg');
    });
  });
  let ticking = false;
  const drift = () => {
    ticking = false;
    const h = innerHeight;
    frames.forEach((f) => {
      const r = f.getBoundingClientRect();
      if (r.bottom < 0 || r.top > h) return;
      const p = (r.top + r.height / 2 - h / 2) / h; // -1..1 around the viewport centre
      f.style.setProperty('--drift', `${(p * -28).toFixed(1)}px`);
    });
  };
  addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(drift); } }, { passive: true });
  drift();
}

// ---------------------------------------------------------------- CV: big year follows the job in view

(function cvYear() {
  const jobs = $$('.job');
  const out = $('[data-year-out]');
  if (!out) return;
  const seen = new IntersectionObserver((entries) => {
    entries.forEach((en) => { if (en.isIntersecting) out.textContent = en.target.dataset.year; });
  }, { rootMargin: '-45% 0px -45% 0px' });
  jobs.forEach((j) => seen.observe(j));
})();

// ---------------------------------------------------------------- GitHub numbers (cached for an hour)

(function github() {
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
