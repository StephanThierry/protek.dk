// Ebru-vandet: en Navier–Stokes-væskesimulering (stable fluids) skrevet i TSL og kørt på GPU'en
// gennem three.js' WebGPURenderer. Hver delberegning er en fuldskærms-QuadMesh, der skriver til en
// render target (ping-pong). WebGPU bruges, hvor browseren kan; ellers falder rendereren selv tilbage
// til WebGL2, og den samme TSL-kode oversættes til GLSL i stedet for WGSL.
//
// Blæk lagres som absorbans (Beer–Lambert): papir * exp(-blæk). Det giver subtraktiv farveblanding,
// så indigo over okker bliver grøn-sort, ligesom rigtig marmorering på vand.
import * as THREE from 'three/webgpu';
import {
  Fn, uniform, texture, uv, vec2, vec3, vec4, float, exp, dot, length, abs, clamp, mix, fract, floor, mod,
  sin, max, normalize, select, smoothstep, screenCoordinate,
} from 'three/tsl';

const srgbToLinear = (hex) => new THREE.Color(hex); // THREE.Color konverterer hex til lineært arbejdsrum

// Papirets farve. Blækkets absorbans udledes af, hvordan farven ser ud mættet på papiret.
export const PAPER = 0xf2ece1;
export function absorbance(hex, strength = 1) {
  const p = srgbToLinear(PAPER), c = srgbToLinear(hex);
  const a = (ch) => -Math.log(Math.max(c[ch] / p[ch], 0.015));
  return new THREE.Vector3(a('r'), a('g'), a('b')).multiplyScalar(strength);
}

export async function createFluid(canvas, opts = {}) {
  const small = Math.min(window.innerWidth, window.innerHeight) < 700;
  const SIM = opts.sim ?? (small ? 112 : 160);       // celler på den korte led
  const DYE = opts.dye ?? (small ? 560 : 1024);     // blæk-opløsning på den korte led
  const ITER = opts.iterations ?? (small ? 12 : 20);

  const renderer = new THREE.WebGPURenderer({ canvas, antialias: false, alpha: false, forceWebGL: !!opts.forceWebGL });
  await renderer.init();
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.autoClear = false;
  const isGPU = !!renderer.backend.isWebGPUBackend;
  const backend = isGPU ? 'WebGPU' : 'WebGL2';
  // QuadMesh-uv har y=0 foroven i både WebGPU og WebGL2 (verificeret i headless Chrome). API'et tager
  // skærmkoordinater (y nedad) og oversætter her, så resten af koden er ligeglad med retningen.
  const flip = true;
  const Y = (y) => (flip ? y : 1 - y);
  const VY = (vy) => (flip ? vy : -vy);

  // ------------------------------------------------------------------ render targets
  const rtOpts = {
    type: THREE.HalfFloatType, format: THREE.RGBAFormat, depthBuffer: false, generateMipmaps: false,
    minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter,
    wrapS: THREE.ClampToEdgeWrapping, wrapT: THREE.ClampToEdgeWrapping,
  };
  const make = (w, h) => new THREE.RenderTarget(w, h, rtOpts);
  const dbl = (w, h) => ({ read: make(w, h), write: make(w, h), swap() { [this.read, this.write] = [this.write, this.read]; } });

  let simW, simH, dyeW, dyeH;
  let vel, dye, prs, div, curl;
  function dims(base, aspect) {
    return aspect >= 1 ? [Math.round(base * aspect), base] : [base, Math.round(base / aspect)];
  }
  function allocate() {
    const w = canvas.clientWidth || window.innerWidth, h = canvas.clientHeight || window.innerHeight;
    const aspect = w / h;
    [simW, simH] = dims(SIM, aspect);
    [dyeW, dyeH] = dims(DYE, aspect);
    for (const t of [vel, dye, prs]) { if (t) { t.read.dispose(); t.write.dispose(); } }
    for (const t of [div, curl]) t?.dispose();
    vel = dbl(simW, simH); prs = dbl(simW, simH); dye = dbl(dyeW, dyeH);
    div = make(simW, simH); curl = make(simW, simH);
    U.simTexel.value.set(1 / simW, 1 / simH);
    U.dyeTexel.value.set(1 / dyeW, 1 / dyeH);
    U.aspect.value = aspect;
  }

  // ------------------------------------------------------------------ uniforms
  const U = {
    simTexel: uniform(new THREE.Vector2()), dyeTexel: uniform(new THREE.Vector2()), aspect: uniform(1),
    dt: uniform(1 / 60), curl: uniform(small ? 14 : 18), velDiss: uniform(0.25), dyeDiss: uniform(0.045),
    drift: uniform(new THREE.Vector2()), pressureDecay: uniform(0.8),
    // splat
    point: uniform(new THREE.Vector2(0.5, 0.5)), radius: uniform(0.002), value: uniform(new THREE.Vector3()),
    valueB: uniform(new THREE.Vector3()), ringR: uniform(0.1), ringW: uniform(0.0004),
    wDisc: uniform(0), wRing: uniform(0), wMask: uniform(0), wSwirl: uniform(0), wComb: uniform(0),
    combFreq: uniform(10), combAxis: uniform(0), combAlt: uniform(1), combPhase: uniform(0),
    // visning
    paper: uniform(srgbToLinear(PAPER)), res: uniform(new THREE.Vector2(1, 1)), sheen: uniform(1),
  };

  // Tomme pladsholdere; .value skiftes før hver pass (samme mønster som three's AfterImageNode).
  const blank = new THREE.Texture();
  const tVel = texture(blank), tSrc = texture(blank), tPrs = texture(blank), tDiv = texture(blank), tCurl = texture(blank);
  const maskTex = new THREE.CanvasTexture(document.createElement('canvas'));
  maskTex.colorSpace = THREE.NoColorSpace;
  maskTex.generateMipmaps = false;
  maskTex.minFilter = THREE.LinearFilter;
  const tMask = texture(maskTex);

  const off = (x, y) => uv().add(vec2(U.simTexel.x.mul(x), U.simTexel.y.mul(y)));

  const material = (node) => {
    const m = new THREE.NodeMaterial();
    m.fragmentNode = node;
    m.depthTest = false; m.depthWrite = false;
    return m;
  };

  // --- hvirvling (curl) og vorticity confinement, som holder de små hvirvler i live
  const curlMat = material(Fn(() => {
    const L = tVel.sample(off(-1, 0)).y, R = tVel.sample(off(1, 0)).y;
    const T = tVel.sample(off(0, 1)).x, B = tVel.sample(off(0, -1)).x;
    return vec4(R.sub(L).sub(T).add(B).mul(0.5), 0, 0, 1);
  })());

  const vortMat = material(Fn(() => {
    const cL = tCurl.sample(off(-1, 0)).x, cR = tCurl.sample(off(1, 0)).x;
    const cT = tCurl.sample(off(0, 1)).x, cB = tCurl.sample(off(0, -1)).x, C = tCurl.sample(uv()).x;
    const g = vec2(abs(cT).sub(abs(cB)), abs(cR).sub(abs(cL))).mul(0.5);
    const f = g.div(length(g).add(0.0001)).mul(U.curl.mul(C));
    const v = tVel.sample(uv()).xy.add(vec2(f.x, f.y.negate()).add(U.drift).mul(U.dt));
    return vec4(clamp(v, -1000, 1000), 0, 1);
  })());

  // --- divergens med lukkede kanter (spejling ved randen)
  const divMat = material(Fn(() => {
    const C = tVel.sample(uv()).xy;
    const uL = off(-1, 0), uR = off(1, 0), uT = off(0, 1), uB = off(0, -1);
    const L = select(uL.x.lessThan(0), C.x.negate(), tVel.sample(uL).x);
    const R = select(uR.x.greaterThan(1), C.x.negate(), tVel.sample(uR).x);
    const T = select(uT.y.greaterThan(1), C.y.negate(), tVel.sample(uT).y);
    const B = select(uB.y.lessThan(0), C.y.negate(), tVel.sample(uB).y);
    return vec4(R.sub(L).add(T).sub(B).mul(0.5), 0, 0, 1);
  })());

  const decayMat = material(Fn(() => vec4(tPrs.sample(uv()).x.mul(U.pressureDecay), 0, 0, 1))());

  // --- Jacobi-iterationer for trykket
  const jacobiMat = material(Fn(() => {
    const s = tPrs.sample(off(-1, 0)).x.add(tPrs.sample(off(1, 0)).x).add(tPrs.sample(off(0, 1)).x).add(tPrs.sample(off(0, -1)).x);
    return vec4(s.sub(tDiv.sample(uv()).x).mul(0.25), 0, 0, 1);
  })());

  // --- træk trykgradienten fra, så feltet bliver divergensfrit (inkompressibelt vand)
  const gradMat = material(Fn(() => {
    const L = tPrs.sample(off(-1, 0)).x, R = tPrs.sample(off(1, 0)).x;
    const T = tPrs.sample(off(0, 1)).x, B = tPrs.sample(off(0, -1)).x;
    return vec4(tVel.sample(uv()).xy.sub(vec2(R.sub(L), T.sub(B))), 0, 1);
  })());

  // --- semi-lagrangsk advektion; dissipation styrer, hvor længe blækket bliver liggende
  const advect = (diss) => material(Fn(() => {
    const coord = uv().sub(tVel.sample(uv()).xy.mul(U.simTexel).mul(U.dt));
    return tSrc.sample(coord).div(float(1).add(diss.mul(U.dt)));
  })());
  const advVelMat = advect(U.velDiss);
  const advDyeMat = advect(U.dyeDiss);

  // --- splat: dråbe, ring, tekstmaske, hvirvel eller kam. Vægtene vælger, hvad der lægges til.
  const splatMat = material(Fn(() => {
    const p = uv().sub(U.point).mul(vec2(U.aspect, 1));
    const d2 = dot(p, p);
    const disc = exp(d2.negate().div(U.radius));
    const rd = length(p).sub(U.ringR);
    const ring = exp(rd.mul(rd).negate().div(U.ringW));
    const m = tMask.sample(uv());
    const add = U.value.mul(disc.mul(U.wDisc).add(ring.mul(U.wRing)))
      .add(U.value.mul(m.r).add(U.valueB.mul(m.g)).mul(U.wMask));
    return vec4(max(tSrc.sample(uv()).rgb.add(add), vec3(0)), 1);
  })());
  // Hastighed: skub, hvirvel (tangentielt felt) og kam. Kammen giver tænder med jævn afstand,
  // skiftevis frem og tilbage (gel-git) eller samme vej, som når man trækker en kam gennem ebru-vandet.
  const velSplatMat = material(Fn(() => {
    const p = uv().sub(U.point).mul(vec2(U.aspect, 1));
    const disc = exp(dot(p, p).negate().div(U.radius));
    const tang = vec2(p.y.negate(), p.x).div(length(p).add(0.02));
    const along = mix(uv().y, uv().x.mul(U.aspect), U.combAxis).mul(U.combFreq).add(U.combPhase);
    const t = fract(along).sub(0.5);
    const tooth = exp(t.mul(t).negate().div(0.004));
    const dir = mix(float(1), mod(floor(along), 2).mul(2).sub(1), U.combAlt);
    const comb = mix(vec2(1, 0), vec2(0, 1), U.combAxis).mul(dir.mul(tooth));
    const add = U.value.xy.mul(disc.mul(U.wDisc))
      .add(tang.mul(disc).mul(U.value.z).mul(U.wSwirl))
      .add(comb.mul(U.value.x).mul(U.wComb));
    return vec4(tVel.sample(uv()).xy.add(add), 0, 1);
  })());

  const clearMat = material(vec4(0, 0, 0, 1));

  // --- visning: papir gennem blæk, en svag våd glans ud fra blækkets hældning og lidt papirkorn
  const displayMat = material(Fn(() => {
    const a = tSrc.sample(uv()).rgb;
    const e = U.dyeTexel.mul(1.5);
    const dens = (o) => dot(tSrc.sample(uv().add(o)).rgb, vec3(0.33));
    const gx = dens(vec2(e.x, 0)).sub(dens(vec2(e.x.negate(), 0)));
    const gy = dens(vec2(0, e.y)).sub(dens(vec2(0, e.y.negate())));
    const n = normalize(vec3(gx.mul(-1.7), gy.mul(-1.7), 1));
    const light = dot(n, normalize(vec3(-0.45, 0.6, 0.85)));
    const spec = max(dot(n, normalize(vec3(-0.2, 0.35, 1))), 0).pow(60).mul(0.22);
    const sc = screenCoordinate.xy;
    const grain = fract(sin(dot(sc, vec2(12.9898, 78.233))).mul(43758.5453)).sub(0.5).mul(0.035);
    const fiber = sin(sc.x.mul(0.013).add(sin(sc.y.mul(0.021)).mul(3))).mul(0.012);
    const ink = U.paper.mul(exp(a.negate()));
    const shade = mix(float(1), light.mul(0.18).add(0.86), smoothstep(0.0, 0.35, dot(a, vec3(0.33))).mul(U.sheen));
    return vec4(ink.mul(shade).add(spec.mul(U.sheen)).add(grain).add(fiber), 1);
  })());

  // ------------------------------------------------------------------ afvikling
  const quad = new THREE.QuadMesh();
  const run = (mat, target) => { quad.material = mat; renderer.setRenderTarget(target); quad.render(renderer); };

  const queue = [];
  const combs = [];
  let disposed = false;

  function resetWeights() { U.wDisc.value = U.wRing.value = U.wMask.value = U.wSwirl.value = U.wComb.value = 0; }

  function applySplat(s) {
    resetWeights();
    // Uden punkt (maske, rydning) bruges midten; NaN her ville gøre hele feltet NaN, også når vægten er 0.
    U.point.value.set(s.x ?? 0.5, Y(s.y ?? 0.5));
    // størrelser er givet i forhold til den korte led, så en dråbe er lige rund og stor på mobil og desktop
    const k = Math.min(1, U.aspect.value);
    U.radius.value = ((s.r ?? 0.03) * k) ** 2;
    if (s.kind === 'force') {
      U.wDisc.value = 1; U.value.value.set(s.dx, VY(s.dy), 0);
      tVel.value = vel.read.texture; run(velSplatMat, vel.write); vel.swap();
      if (s.ink) {
        U.value.value.copy(s.ink);
        tSrc.value = dye.read.texture; run(splatMat, dye.write); dye.swap();
      }
    } else if (s.kind === 'drop' || s.kind === 'ring') {
      if (s.kind === 'ring') { U.wRing.value = 1; U.ringR.value = s.ringR * k; U.ringW.value = (s.ringW * k) ** 2; } else U.wDisc.value = 1;
      U.value.value.copy(s.ink);
      tSrc.value = dye.read.texture; run(splatMat, dye.write); dye.swap();
    } else if (s.kind === 'swirl') {
      U.wSwirl.value = 1; U.value.value.set(0, 0, s.strength);
      tVel.value = vel.read.texture; run(velSplatMat, vel.write); vel.swap();
    } else if (s.kind === 'mask') {
      U.wMask.value = s.amount; U.value.value.copy(s.inkA); U.valueB.value.copy(s.inkB);
      tSrc.value = dye.read.texture; run(splatMat, dye.write); dye.swap();
    } else if (s.kind === 'clear') {
      for (const t of [vel, dye, prs]) { run(clearMat, t.read); run(clearMat, t.write); }
    }
  }

  function applyComb(c, now) {
    const k = Math.min(1, (now - c.t0) / c.ms);
    // blød ind- og udtoning, mens kammen trækkes gennem vandet
    const env = Math.sin(Math.PI * k);
    resetWeights();
    U.wComb.value = 1;
    U.combFreq.value = c.freq; U.combAxis.value = c.axis; U.combAlt.value = c.alt ? 1 : 0; U.combPhase.value = c.phase;
    U.value.value.set(c.amp * env, 0, 0);
    tVel.value = vel.read.texture; run(velSplatMat, vel.write); vel.swap();
    return k >= 1;
  }

  let last = performance.now();
  let frames = 0, fpsT = last, fps = 60;

  function step(now) {
    if (disposed) return;
    const dt = Math.min((now - last) / 1000, 1 / 30);
    last = now;
    U.dt.value = dt || 1 / 60;
    frames++;
    if (now - fpsT > 1000) { fps = Math.round(frames * 1000 / (now - fpsT)); frames = 0; fpsT = now; }

    while (queue.length) applySplat(queue.shift());
    for (let i = combs.length - 1; i >= 0; i--) if (applyComb(combs[i], now)) combs.splice(i, 1);

    tVel.value = vel.read.texture; run(curlMat, curl);
    tCurl.value = curl.texture; tVel.value = vel.read.texture; run(vortMat, vel.write); vel.swap();
    tVel.value = vel.read.texture; run(divMat, div);
    tPrs.value = prs.read.texture; run(decayMat, prs.write); prs.swap();
    tDiv.value = div.texture;
    for (let i = 0; i < ITER; i++) { tPrs.value = prs.read.texture; run(jacobiMat, prs.write); prs.swap(); }
    tPrs.value = prs.read.texture; tVel.value = vel.read.texture; run(gradMat, vel.write); vel.swap();
    tVel.value = vel.read.texture; tSrc.value = vel.read.texture; run(advVelMat, vel.write); vel.swap();
    tVel.value = vel.read.texture; tSrc.value = dye.read.texture; run(advDyeMat, dye.write); dye.swap();
    U.drift.value.multiplyScalar(0.86);

    tSrc.value = dye.read.texture;
    run(displayMat, null);
  }

  // ------------------------------------------------------------------ størrelse
  let lastW = 0, lastH = 0;
  function resize(force = false) {
    const w = canvas.clientWidth || window.innerWidth, h = canvas.clientHeight || window.innerHeight;
    renderer.setSize(w, h, false);
    U.res.value.set(w, h);
    // Mobilens adresselinje ændrer højden en smule; simuleringen bevares, medmindre formatet skifter.
    const changed = !lastW || Math.abs(w / h - lastW / lastH) > 0.12 || Math.abs(w - lastW) > 40;
    if (force || changed) { allocate(); lastW = w; lastH = h; return true; }
    return false;
  }
  resize(true);
  renderer.setAnimationLoop(step);

  // ------------------------------------------------------------------ tekst som blæk
  function writeText(lines, inkA, inkB, { amount = 1, y = 0.42, size = 0.17, font = 'Fraunces' } = {}) {
    const w = dyeW, h = dyeH;
    // En GPU-tekstur kan ikke skifte størrelse efter første upload, så der laves en ny, når formatet ændres.
    let c = tMask.value.image;
    if (!c || c.width !== w || c.height !== h) {
      c = document.createElement('canvas');
      c.width = w; c.height = h;
      const t = new THREE.CanvasTexture(c);
      t.colorSpace = THREE.NoColorSpace; t.generateMipmaps = false; t.minFilter = THREE.LinearFilter;
      t.flipY = !flip;
      const old = tMask.value;
      tMask.value = t;
      old.dispose();
    }
    const g = c.getContext('2d');
    g.fillStyle = '#000'; g.fillRect(0, 0, w, h);
    let px = Math.round(Math.min(h * size, w * 0.16));
    g.textAlign = 'center'; g.textBaseline = 'middle';
    const fit = () => {
      g.font = `600 ${px}px "${font}", Georgia, serif`;
      const widest = Math.max(...lines.map((l) => g.measureText(l.text).width));
      return widest;
    };
    while (fit() > w * 0.86 && px > 10) px -= 2;
    g.filter = `blur(${Math.max(1, px * 0.025)}px)`;
    lines.forEach((l, i) => {
      g.fillStyle = l.channel === 'g' ? '#00ff00' : '#ff0000';
      g.fillText(l.text, w / 2, h * y + (i - (lines.length - 1) / 2) * px * 1.02);
    });
    g.filter = 'none';
    tMask.value.needsUpdate = true;
    queue.push({ kind: 'mask', amount, inkA, inkB });
  }

  const api = {
    backend, renderer,
    get fps() { return fps; },
    get cells() { return `${simW}×${simH}`; },
    resize,
    // x, y i 0..1 af skærmen, y nedad som i CSS
    drop(x, y, ink, r = 0.04) { queue.push({ kind: 'drop', x, y, ink, r }); },
    ring(x, y, ink, ringR, ringW = 0.012) { queue.push({ kind: 'ring', x, y, ink, ringR, ringW }); },
    force(x, y, dx, dy, r = 0.035, ink = null) { queue.push({ kind: 'force', x, y, dx, dy, r, ink }); },
    swirl(x, y, strength, r = 0.12) { queue.push({ kind: 'swirl', x, y, strength, r }); },
    comb({ freq = 9, axis = 0, alt = true, amp = 900, ms = 1400, phase = Math.random() } = {}) {
      combs.push({ freq, axis, alt, amp, ms, phase, t0: performance.now() });
    },
    drift(dx, dy) { U.drift.value.x += dx; U.drift.value.y += VY(dy); },
    clear() { queue.push({ kind: 'clear' }); },
    writeText,
    set dyeDissipation(v) { U.dyeDiss.value = v; },
    dispose() { disposed = true; renderer.setAnimationLoop(null); renderer.dispose(); },
    onLost(cb) {
      const dev = renderer.backend.device;
      if (dev?.lost) dev.lost.then((info) => { if (!disposed && info.reason !== 'destroyed') cb(info); });
    },
  };
  return api;
}
