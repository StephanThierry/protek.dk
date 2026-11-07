// Den levende forside.
// Artiklen sættes linje for linje med Pretext (ingen DOM-målinger) i 1–3 spalter. Hvert linjebånd får
// sine ledige "slots" ved at trække forhindringerne fra spaltebredden: portrættet er en cirkel, og
// stjernen er sin egen alfa-maske, så teksten løber ind mellem takkerne. Alt sættes om hver frame.
import { prepareWithSegments, layoutNextLine, layout, measureNaturalWidth, prepare, clearCache } from '@chenglou/pretext';

const FAMILY = '"Newsreader"';
const MASK = 220; // opløsning på stjernens alfa-maske

export async function liveStory(story, { reduced, onPerf } = {}) {
  const flow = story.querySelector('[data-flow]');
  const capEl = flow.querySelector('[data-cap]');
  const paras = [...story.querySelectorAll('.story__src p')].map((p) => p.textContent.replace(/\s+/g, ' ').trim());
  const capLetter = paras[0][0];
  paras[0] = paras[0].slice(1);
  capEl.textContent = capLetter;

  // ------------------------------------------------------------ forhindringer
  const portraitEl = flow.querySelector('[data-ob="portrait"]');
  const starEl = flow.querySelector('[data-ob="star"]');
  const starImg = starEl.querySelector('img');
  const portraitImg = new Image();
  portraitImg.src = new URL('img/stephan_profile.jpg', document.baseURI).href;
  await Promise.all([starImg.decode(), portraitImg.decode()]);
  const alpha = buildMask(starImg);

  const obs = {
    portrait: { el: portraitEl, kind: 'circle', fx: 0, fy: 0, x: 0, y: 0, D: 0, ox: 0, oy: 0, a: 0 },
    star: { el: starEl, kind: 'mask', fx: 0, fy: 0, x: 0, y: 0, D: 0, ox: 0, oy: 0, a: -0.35 },
  };
  let placed = false;

  // ------------------------------------------------------------ mål og typografi
  let m = null;
  let H = 0;
  const prepCache = new Map();
  let prepared = [];
  let capBox = { w: 0, h: 0 };

  function metrics() {
    const W = Math.floor(flow.clientWidth);
    const cols = W >= 920 ? 3 : W >= 580 ? 2 : 1;
    const gap = cols === 1 ? 0 : W >= 920 ? 40 : 28;
    const size = W >= 580 ? 18 : 17;
    const lh = W >= 580 ? 29 : 27;
    const colW = Math.floor((W - gap * (cols - 1)) / cols);
    return { W, cols, gap, size, lh, colW, indent: Math.round(size * 1.3), minSlot: Math.round(size * 3.4) };
  }

  function prepareAll() {
    const font = `400 ${m.size}px ${FAMILY}`;
    if (!prepCache.has(font)) prepCache.set(font, paras.map((t) => prepareWithSegments(t, font)));
    prepared = prepCache.get(font);
    flow.style.setProperty('--fs', m.size + 'px');
    flow.style.setProperty('--lh', m.lh + 'px');
    flow.style.setProperty('--colw', (m.cols > 1 ? m.colW : 99999) + 'px');
    flow.style.setProperty('--gap', m.gap + 'px');
    // Initialen fylder tre linjer.
    const capSize = Math.round(m.lh * 3.15);
    const capW = measureNaturalWidth(prepare(capLetter, `800 ${capSize}px ${FAMILY}`));
    capBox = { w: Math.ceil(capW) + 10, h: m.lh * 3 };
    capEl.style.fontSize = capSize + 'px';
    capEl.style.lineHeight = m.lh * 3 + 'px';
  }

  function sizeObstacles() {
    const { W, cols } = m;
    obs.portrait.D = Math.round(cols === 1 ? Math.min(W * 0.46, 170) : clamp(W * 0.19, 150, 230));
    obs.star.D = Math.round(cols === 1 ? Math.min(W * 0.62, 230) : clamp(W * 0.27, 200, 330));
    for (const o of Object.values(obs)) {
      o.el.style.width = o.el.style.height = o.D + 'px';
    }
    drawHalftone(portraitEl.querySelector('canvas'), portraitImg, obs.portrait.D);
  }

  // Startgæt på spaltehøjden ud fra tekstmængden og forhindringernes areal; vokser hvis teksten ikke kan være der.
  function estimateHeight() {
    let total = 0;
    for (const p of prepared) total += layout(p, m.colW, m.lh).height;
    const r = obs.portrait.D / 2 + 16;
    const area = Math.PI * r * r + (obs.star.D * 0.62) ** 2 + capBox.w * capBox.h;
    const h = (total + (area / m.colW) * 1.5) / m.cols;
    return Math.ceil(h / m.lh) * m.lh + m.lh * 2;
  }

  function place() {
    if (!placed) {
      // Første placering: portrættet over spalteskel 1|2, stjernen over 2|3 længere nede.
      const one = m.cols === 1;
      obs.portrait.fx = one ? 0.7 : m.cols === 2 ? 0.5 : 0.345;
      obs.portrait.fy = one ? 0.16 : 0.3;
      obs.star.fx = one ? 0.3 : m.cols === 2 ? 0.62 : 0.68;
      obs.star.fy = one ? 0.62 : 0.62;
      placed = true;
    }
    for (const o of Object.values(obs)) { o.x = o.fx * m.W; o.y = o.fy * H; }
  }

  // ------------------------------------------------------------ intervaller
  function circleBlock(o, y0, y1, out) {
    const r = o.D / 2 + 16;
    const cx = o.x + o.ox, cy = o.y + o.oy;
    if (y1 < cy - r || y0 > cy + r) return;
    const ny = clamp(cy, y0, y1) - cy;
    const half = Math.sqrt(r * r - ny * ny);
    out.push([cx - half, cx + half]);
  }

  function maskBlock(o, y0, y1, out) {
    const half = o.D * 0.5, pad = 12;
    const cx = o.x + o.ox, cy = o.y + o.oy;
    if (y1 < cy - half - pad || y0 > cy + half + pad) return;
    const c = Math.cos(o.a), s = Math.sin(o.a);
    const rows = [y0 - pad, y0, (y0 + y1) / 2, y1, y1 + pad];
    for (const yy of rows) {
      const dy = yy - cy;
      if (dy < -half || dy > half) continue;
      let on = false, start = 0;
      for (let x = cx - half; x <= cx + half; x += 3) {
        const dx = x - cx;
        const u = (((dx * c + dy * s) / o.D + 0.5) * MASK) | 0;
        const v = (((-dx * s + dy * c) / o.D + 0.5) * MASK) | 0;
        const hit = u >= 0 && v >= 0 && u < MASK && v < MASK && alpha[v * MASK + u] > 90;
        if (hit && !on) { on = true; start = x; }
        else if (!hit && on) { on = false; out.push([start - pad, x + pad]); }
      }
      if (on) out.push([start - pad, cx + half + pad]);
    }
  }

  function slots(x0, x1, blocks) {
    blocks.sort((p, q) => p[0] - q[0]);
    const res = [];
    let cur = x0;
    for (const [a, b] of blocks) {
      if (b <= cur) continue;
      if (a >= x1) break;
      if (a > cur) res.push([cur, a]);
      cur = Math.max(cur, b);
      if (cur >= x1) break;
    }
    if (cur < x1) res.push([cur, x1]);
    return res.filter(([a, b]) => b - a >= m.minSlot);
  }

  // ------------------------------------------------------------ sats
  const pool = [];
  let used = 0;

  function lineEl(i) {
    let el = pool[i];
    if (!el) {
      el = document.createElement('span');
      el.className = 'ln';
      el._t = el._x = el._y = el._w = null;
      flow.appendChild(el);
      pool.push(el);
    }
    return el;
  }

  function compose() {
    const { cols, gap, lh, colW, indent, size } = m;
    let pi = 0, cursor = undefined, paraStart = true, n = 0;
    const blocks = [];
    outer: for (let c = 0; c < cols; c++) {
      const x0 = c * (colW + gap), x1 = x0 + colW;
      for (let y = 0; y + lh <= H; y += lh) {
        blocks.length = 0;
        if (c === 0 && y < capBox.h) blocks.push([x0 - 1, x0 + capBox.w]);
        circleBlock(obs.portrait, y, y + lh, blocks);
        maskBlock(obs.star, y, y + lh, blocks);
        let free = slots(x0, x1, blocks);
        // I smalle spalter giver to halve linjer på hver side af en forhindring dårlig læsning: brug kun den bredeste.
        if (free.length > 1 && colW < 520) free = [free.reduce((p, q) => (q[1] - q[0] > p[1] - p[0] ? q : p))];
        for (const [a, b] of free) {
          const ind = paraStart && pi > 0 ? indent : 0;
          const w = Math.floor(b - a - ind);
          const p = prepared[pi];
          const line = layoutNextLine(p, w, cursor);
          if (!line) { pi++; cursor = undefined; paraStart = true; if (pi >= prepared.length) break outer; continue; }
          // Et ord, der ikke kan være i et smalt slot, må ikke knækkes midt over: spring slottet over.
          if (line.end.graphemeIndex > 0 && b - a < colW - 1) continue;
          const last = line.end.segmentIndex >= p.segments.length;
          const text = line.text.replace(/\s+$/, '');
          let ws = 0;
          if (!last) {
            const spaces = text.split(' ').length - 1;
            if (spaces > 0) { ws = (w - line.width) / spaces; if (ws > size * 0.85) ws = 0; }
          }
          const el = lineEl(n++);
          if (el._t !== text) { el.textContent = text; el._t = text; }
          const x = Math.round((a + ind) * 4) / 4;
          if (el._x !== x || el._y !== y) { el.style.transform = `translate(${x}px,${y}px)`; el._x = x; el._y = y; }
          const wsr = Math.round(ws * 100) / 100;
          if (el._w !== wsr) { el.style.wordSpacing = wsr ? wsr + 'px' : ''; el._w = wsr; }
          el._s = w;
          if (el.hidden) el.hidden = false;
          paraStart = false;
          cursor = line.end;
          if (last) { pi++; cursor = undefined; paraStart = true; if (pi >= prepared.length) break outer; }
        }
      }
    }
    for (let i = n; i < used; i++) pool[i].hidden = true;
    used = n;
    return pi >= prepared.length; // false = teksten kunne ikke være der
  }

  function setH(h) {
    const yp = obs.portrait.y / H, ys = obs.star.y / H;
    H = h;
    obs.portrait.y = yp * H; obs.star.y = ys * H;
  }

  function fit(maxSteps) {
    let ok = compose();
    for (let k = 0; !ok && k < maxSteps; k++) { setH(H + m.lh * 2); ok = compose(); }
    flow.style.height = H + 'px';
  }

  // Balancér spalterne: skru højden ned, til teksten lige netop kan være der, plus lidt luft til at forhindringerne kan vandre.
  function balance() {
    while (H > m.lh * 8) {
      setH(H - m.lh);
      if (!compose()) { setH(H + m.lh * 2); break; }
    }
    compose();
    flow.style.height = H + 'px';
  }

  function relayout() {
    m = metrics();
    prepareAll();
    sizeObstacles();
    H = estimateHeight();
    place();
    applyObstacles();
    fit(60);
    balance();
  }

  function applyObstacles() {
    for (const o of Object.values(obs)) {
      o.el.style.transform = `translate(${o.x + o.ox - o.D / 2}px,${o.y + o.oy - o.D / 2}px) rotate(${o.kind === 'mask' ? o.a : 0}rad)`;
    }
  }

  // ------------------------------------------------------------ træk
  let drag = null;
  for (const [key, o] of Object.entries(obs)) {
    o.el.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      o.el.setPointerCapture(e.pointerId);
      const r = flow.getBoundingClientRect();
      drag = { o, key, left: r.left, top: r.top, dx: e.clientX - r.left - (o.x + o.ox), dy: e.clientY - r.top - (o.y + o.oy) };
      o.el.classList.add('is-grabbed');
      story.classList.add('is-touched');
      wake();
    });
    o.el.addEventListener('pointermove', (e) => {
      if (!drag || drag.o !== o) return;
      o.x = clamp(e.clientX - drag.left - drag.dx - o.ox, 0, m.W);
      o.y = clamp(e.clientY - drag.top - drag.dy - o.oy, 0, H);
      o.fx = o.x / m.W; o.fy = o.y / H;
      dirty = true;
      wake();
    });
    const end = () => { if (drag?.o === o) { drag = null; o.el.classList.remove('is-grabbed'); } };
    o.el.addEventListener('pointerup', end);
    o.el.addEventListener('pointercancel', end);
  }

  // ------------------------------------------------------------ løkken
  let dirty = true, raf = 0, visible = true, t0 = performance.now(), perfAcc = 0, perfN = 0, perfT = 0;
  const drift = !reduced;

  function frame(now) {
    raf = 0;
    const t = (now - t0) / 1000;
    if (drift) {
      // Langsom vandring, så avisen lever, også uden at nogen rører den.
      const A = m.cols === 1 ? 10 : 22;
      if (drag?.o !== obs.portrait) { obs.portrait.ox = Math.sin(t * 0.31) * A; obs.portrait.oy = Math.cos(t * 0.23) * A * 0.8; }
      if (drag?.o !== obs.star) { obs.star.ox = Math.cos(t * 0.19 + 1) * A; obs.star.oy = Math.sin(t * 0.27 + 2) * A; }
      obs.star.a = -0.35 + t * 0.07;
      dirty = true;
    }
    if (dirty) {
      dirty = false;
      const s = performance.now();
      applyObstacles();
      if (!compose()) fit(4);
      perfAcc += performance.now() - s; perfN++;
      if (now - perfT > 600 && onPerf) { onPerf(perfAcc / perfN); perfAcc = perfN = 0; perfT = now; }
    }
    if (visible && (drift || drag)) raf = requestAnimationFrame(frame);
  }
  function wake() { if (!raf && visible) raf = requestAnimationFrame(frame); }

  new IntersectionObserver(([en]) => { visible = en.isIntersecting; if (visible) wake(); }).observe(flow);
  document.addEventListener('visibilitychange', () => { visible = !document.hidden; if (visible) wake(); });

  let lastW = Math.floor(flow.clientWidth);
  new ResizeObserver(() => {
    const w = Math.floor(flow.clientWidth);
    if (w === lastW) return;
    const colsBefore = m?.cols;
    lastW = w;
    m = metrics();
    if (colsBefore && colsBefore !== m.cols) placed = false;
    relayout();
    dirty = true;
    wake();
  }).observe(flow);

  // Webfonte, der lander sent, giver andre bredder: mål forfra.
  document.fonts.addEventListener?.('loadingdone', () => { clearCache(); prepCache.clear(); relayout(); wake(); });

  relayout();
  story.classList.add('is-live');
  wake();
}

// Stjernens alfa-maske: hvilke pixels er "blæk".
function buildMask(img) {
  const c = document.createElement('canvas');
  c.width = c.height = MASK;
  const g = c.getContext('2d', { willReadFrequently: true });
  g.drawImage(img, 0, 0, MASK, MASK);
  const d = g.getImageData(0, 0, MASK, MASK).data;
  const a = new Uint8Array(MASK * MASK);
  for (let i = 0; i < a.length; i++) a[i] = d[i * 4 + 3];
  return a;
}

// Rastreret avisfoto: prikstørrelse efter lysstyrke, forskudt hver anden række.
function drawHalftone(canvas, img, D) {
  const dpr = Math.min(devicePixelRatio || 1, 2);
  canvas.width = canvas.height = Math.round(D * dpr);
  canvas.style.width = canvas.style.height = D + 'px';
  const g = canvas.getContext('2d');
  const cell = Math.max(3.6, D / 46) * dpr;
  const n = Math.ceil(canvas.width / cell) + 1;
  const s = document.createElement('canvas');
  s.width = s.height = n;
  const sg = s.getContext('2d', { willReadFrequently: true });
  sg.drawImage(img, 0, 0, n, n);
  const px = sg.getImageData(0, 0, n, n).data;
  const R = canvas.width / 2;
  g.clearRect(0, 0, canvas.width, canvas.height);
  g.fillStyle = '#16191A';
  for (let j = 0; j < n; j++) {
    for (let i = 0; i < n; i++) {
      const k = (j * n + i) * 4;
      let lum = (0.299 * px[k] + 0.587 * px[k + 1] + 0.114 * px[k + 2]) / 255;
      lum = clamp((lum - 0.1) / 0.8, 0, 1);
      const r = cell * 0.62 * Math.sqrt(1 - lum);
      if (r < 0.35 * dpr) continue;
      const x = i * cell + (j % 2 ? cell / 2 : 0), y = j * cell;
      if ((x - R) ** 2 + (y - R) ** 2 > (R - 2 * dpr) ** 2) continue;
      g.beginPath();
      g.arc(x, y, r, 0, Math.PI * 2);
      g.fill();
    }
  }
}

function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
