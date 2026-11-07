// Every Blender element on the page as a live, rotating GLB. One shared WebGL canvas (fixed, full viewport)
// draws each model into the rectangle of its frame with scissor viewports, so ten models cost one context.
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';

const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const TAU = Math.PI * 2;

// Gradient along the helix: teal -> violet, as in the Cycles render (Blender exports only the base colour).
function helixGradient(root) {
  const a = new THREE.Color('#2BB3A6'), b = new THREE.Color('#9B8CFF');
  root.traverse((o) => {
    if (!o.isMesh || !/^Strand/.test(o.name)) return;
    const pos = o.geometry.attributes.position;
    const col = new Float32Array(pos.count * 3);
    const c = new THREE.Color();
    for (let i = 0; i < pos.count; i++) {
      const t = THREE.MathUtils.clamp((pos.getX(i) + o.position.x + 5) / 10, 0, 1);
      c.copy(a).lerp(b, t);
      col.set([c.r, c.g, c.b], i * 3);
    }
    o.geometry.setAttribute('color', new THREE.BufferAttribute(col, 3));
    o.material = o.material.clone();
    o.material.color.set('#ffffff');
    o.material.vertexColors = true;
  });
}

// Printed PLA: matte mint with layer lines drawn from the object height (exaggerated layer height so the lines read on screen).
function printMaterial() {
  const m = new THREE.MeshPhysicalMaterial({ color: '#7CF0C2', roughness: 0.5, clearcoat: 0.15 });
  m.onBeforeCompile = (sh) => {
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nvarying float vH;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvH = position.y;');
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', '#include <common>\nvarying float vH;')
      .replace('#include <color_fragment>', `#include <color_fragment>
        float l = fract(vH / 0.045);
        diffuseColor.rgb *= 0.86 + 0.14 * smoothstep(0.0, 0.35, l) * smoothstep(1.0, 0.65, l);`);
  };
  return m;
}

// name -> how to load, orient and animate it. `dir` is the camera direction, `fill` how much of the frame it fills.
const DEFS = {
  star: {
    url: 'models/star.glb', dir: [0.2, 0.85, 0.75], fill: 1.3,
    tick: (v, t) => { v.pivot.rotation.y = t * 0.25; },
  },
  helix: {
    url: 'models/helix.glb', dir: [0, 0.12, 1], fill: 0.92, fitLong: true,
    setup: (m) => { helixGradient(m); },
    tick: (v, t) => { v.pivot.rotation.x = t * 0.6; },   // lies along X and spins around it
  },
  ghstar: {
    url: 'models/ghstar.glb', dir: [0, 0.15, 1], fill: 0.9,
    setup: (m) => { m.rotation.x = Math.PI / 2; },
    tick: (v, t) => { v.pivot.rotation.y = t * 0.5; },
  },
  knot: {
    url: 'models/knot.glb', dir: [0, 0.2, 1], fill: 0.95,
    setup: (m) => {
      m.rotation.x = 0.9;
      m.traverse((o) => {
        if (o.isMesh) {
          o.material.iridescence = 1;
          o.material.iridescenceIOR = 1.4;
          o.material.iridescenceThicknessMinimum = 300;
          o.material.iridescenceThicknessMaximum = 520;
        }
      });
    },
    tick: (v, t) => { v.pivot.rotation.y = t * 0.35; v.pivot.rotation.x = Math.sin(t * 0.3) * 0.25; },
  },
  prism: {
    url: 'models/prism.glb', dir: [0, 0.1, 1], fill: 1.5,
    setup: (m) => {
      m.rotation.x = Math.PI / 2;
      m.traverse((o) => {
        if (o.isMesh && o.name === 'Prism') {
          o.material = new THREE.MeshPhysicalMaterial({
            color: '#dff4f2', roughness: 0.05, metalness: 0, transparent: true, opacity: 0.32,
            clearcoat: 1, side: THREE.DoubleSide, depthWrite: false,
          });
          o.renderOrder = 2;
        }
      });
    },
    tick: (v, t) => { v.pivot.rotation.y = Math.sin(t * 0.4) * 0.9; v.pivot.rotation.x = Math.sin(t * 0.27) * 0.15; },
  },
  bust: {
    // marble bust: head from TRELLIS, finished in Blender (build_bust); turns slowly on its plinth
    url: 'models/bust.glb', dir: [0, 0.14, 1], fill: 1.0,
    tick: (v, t) => { v.pivot.rotation.y = t * 0.4; },
  },
  layers: {
    url: 'models/layers.glb', dir: [0.35, 0.65, 0.8], fill: 1.15,
    setup: (m, v) => {
      v.layers = [];
      m.traverse((o) => {
        const k = /^L(\d+)/.exec(o.name);
        if (k && o.parent === m) v.layers.push({ o, i: +k[1], y: o.position.y });
      });
    },
    tick: (v, t) => {
      v.pivot.rotation.y = t * 0.3;
      // slicer: the 8 layers pull apart and stack back together
      const s = 0.5 + 0.5 * Math.sin(t * 0.9);
      for (const L of v.layers) L.o.position.y = L.y - L.i * 0.24 * (1 - s);
    },
  },
  print: {
    url: 'models/star.glb', dir: [0.35, 0.6, 0.8], fill: 1.3,
    setup: (m) => {
      const pla = printMaterial();
      const drop = [];
      m.traverse((o) => {
        if (/ring/.test(o.name)) drop.push(o);
        else if (o.isMesh) o.material = pla;
      });
      drop.forEach((o) => o.parent.remove(o));
    },
    tick: (v, t) => { v.pivot.rotation.y = -t * 0.3; },
  },
  dancers: {
    url: 'models/dancers.glb', dir: [0, 0.06, 1], fill: 1.0, tone: THREE.NeutralToneMapping,
    setup: (m, v, gltf) => {
      v.mixer = new THREE.AnimationMixer(m);
      gltf.animations.forEach((c) => v.mixer.clipAction(c).play());
      if (reduced) v.mixer.setTime(9 / 24);
    },
    tick: (v, t, dt) => { if (!reduced) v.mixer.update(dt); },
  },
};

export function initViews() {
  const frames = [...document.querySelectorAll('[data-model]')];
  if (!frames.length) return;

  const canvas = document.createElement('canvas');
  canvas.className = 'views';
  canvas.setAttribute('aria-hidden', 'true');
  document.body.appendChild(canvas);
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  } catch (e) {
    console.warn('WebGL disabled, keeping the Cycles renders:', e);
    canvas.remove();
    return;
  }
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setClearColor(0x000000, 0);
  const env = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;

  const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
  const views = [];

  const makeView = (frame) => {
    const def = DEFS[frame.dataset.model];
    if (!def) return;
    const scene = new THREE.Scene();
    scene.environment = env;
    scene.environmentIntensity = 0.4;
    const key = new THREE.DirectionalLight(0xfff4e8, 2.4);
    key.position.set(-4, 5, 6);
    const rim = new THREE.DirectionalLight(0x9fddf7, 2.0);
    rim.position.set(5, -1, -5);
    const fill = new THREE.DirectionalLight(0x7cf0c2, 0.6);
    fill.position.set(-5, -3, 2);
    scene.add(key, rim, fill);
    const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 200);
    const pivot = new THREE.Group();
    scene.add(pivot);
    const v = { frame, el: frame.querySelector('img') || frame, def, scene, camera, pivot, ready: false, radius: 1 };
    views.push(v);

    loader.load(def.url, (gltf) => {
      const m = gltf.scene;
      def.setup?.(m, v, gltf);
      // centre on the pivot so it rotates in place
      const box = new THREE.Box3().setFromObject(m);
      const c = box.getCenter(new THREE.Vector3());
      m.position.sub(c);
      const holder = new THREE.Group();
      holder.add(m);
      pivot.add(holder);
      v.radius = box.getBoundingSphere(new THREE.Sphere()).radius;
      v.size = box.getSize(new THREE.Vector3());
      v.ready = true;
      frame.classList.add('is-live');
    }, undefined, (e) => console.warn(`${def.url} failed, keeping the render:`, e));
  };

  // Load each model when its frame comes within a screen of the viewport.
  const io = new IntersectionObserver((entries) => {
    entries.forEach((en) => {
      if (en.isIntersecting) { io.unobserve(en.target); makeView(en.target); }
    });
  }, { rootMargin: '100% 0px' });
  frames.forEach((f) => io.observe(f));

  const size = () => renderer.setSize(innerWidth, innerHeight, false);
  addEventListener('resize', size);
  size();

  const timer = new THREE.Timer();
  const dir = new THREE.Vector3();
  let t = 0;
  (function frame() {
    requestAnimationFrame(frame);
    timer.update();
    const dt = Math.min(timer.getDelta(), 0.05);
    if (!reduced) t += dt;
    const H = innerHeight;
    renderer.setScissorTest(false);
    renderer.clear();
    renderer.setScissorTest(true);
    for (const v of views) {
      if (!v.ready) continue;
      const r = v.el.getBoundingClientRect();
      if (r.bottom < 0 || r.top > H || r.width < 2) continue;
      v.def.tick?.(v, t, dt);
      const aspect = r.width / r.height;
      v.camera.aspect = aspect;
      // fit the bounding sphere to the frame, whichever side is shorter
      const half = THREE.MathUtils.degToRad(v.camera.fov / 2);
      const fitH = v.radius / Math.sin(half);
      const fitW = v.radius / Math.sin(Math.atan(Math.tan(half) * aspect));
      let dist = Math.max(fitH, fitW) / v.def.fill;
      if (v.def.fitLong) {
        // long object spinning around X: fit its length to the width, its spin radius to the height
        const rr = Math.hypot(v.size.y, v.size.z) / 2;
        dist = Math.max((v.size.x / 2) / (Math.tan(half) * aspect), rr / Math.tan(half)) / v.def.fill + rr;
      }
      dir.fromArray(v.def.dir).normalize().multiplyScalar(dist);
      v.camera.position.copy(dir);
      v.camera.lookAt(0, 0, 0);
      v.camera.updateProjectionMatrix();
      renderer.toneMapping = v.def.tone ?? THREE.AgXToneMapping;
      renderer.toneMappingExposure = 1.0;
      renderer.setViewport(r.left, H - r.bottom, r.width, r.height);
      renderer.setScissor(r.left, H - r.bottom, r.width, r.height);
      renderer.render(v.scene, v.camera);
    }
  })();
}
