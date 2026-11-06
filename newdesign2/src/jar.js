import Matter from 'matter-js';

const { Engine, Bodies, Body, Composite, Constraint, Query, Vector } = Matter;

// Krukken: én fysisk stjerne for hver GitHub-stjerne. Tælleren følger med, mens de falder i.
export function jar(root, { counter, reduced = false } = {}) {
  const canvas = root.querySelector('canvas');
  const ctx = canvas.getContext('2d');
  const engine = Engine.create();
  engine.gravity.y = 1;
  let W = 0, H = 0, dpr = 1, pad = 0, r = 8, walls = [];
  const stars = [];
  let target = 0, filled = false, running = false, visible = false;

  function size() {
    dpr = Math.min(devicePixelRatio || 1, 2);
    W = canvas.clientWidth; H = canvas.clientHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    pad = Math.max(14, W * 0.06);
    Composite.remove(engine.world, walls);
    const t = 60, top = H * 0.12;
    walls = [
      Bodies.rectangle(W / 2, H - pad + t / 2, W, t, { isStatic: true, friction: 0.4 }),
      Bodies.rectangle(pad - t / 2, (top + H) / 2 - 300, t, H + 600, { isStatic: true }),
      Bodies.rectangle(W - pad + t / 2, (top + H) / 2 - 300, t, H + 600, { isStatic: true }),
    ];
    Composite.add(engine.world, walls);
  }

  function radiusFor(n) {
    const iw = W - pad * 2, ih = (H - pad) - H * 0.18;
    return Math.max(4, Math.min(16, Math.sqrt((iw * ih * 0.5) / (Math.max(n, 1) * Math.PI))));
  }

  function spawn(n) {
    for (let i = 0; i < n; i++) {
      const k = stars.length;
      const x = pad + r + Math.random() * (W - pad * 2 - r * 2);
      const y = reduced ? H - pad - r - Math.floor(k / ((W - 2 * pad) / (2 * r))) * r * 1.9 : -r * 2 - Math.random() * 40;
      const b = Bodies.circle(x, y, r, { restitution: 0.3, friction: 0.2, frictionAir: 0.01, density: 0.002 });
      Body.setAngle(b, Math.random() * Math.PI);
      Body.setAngularVelocity(b, (Math.random() - 0.5) * 0.3);
      b.plugin.c = k % 23 === 0 ? '#E2412B' : k % 17 === 0 ? '#2348C4' : '#F4B71E';
      stars.push(b);
      Composite.add(engine.world, b);
    }
    counter(stars.length);
  }

  function setTarget(n) {
    target = Math.min(n, 600);
    if (!stars.length) r = radiusFor(target);
    if ((filled || visible) && stars.length < target) fillTick();
  }

  function fillTick() {
    filled = true;
    const per = reduced ? target : Math.max(1, Math.ceil(target / 80));
    const pump = () => {
      if (stars.length >= target) return;
      spawn(Math.min(per, target - stars.length));
      requestAnimationFrame(pump);
    };
    pump();
  }

  function starPath(x, y, rad, a) {
    ctx.beginPath();
    for (let i = 0; i < 10; i++) {
      const rr = i % 2 ? rad * 0.45 : rad;
      const t = a - Math.PI / 2 + (i * Math.PI) / 5;
      ctx[i ? 'lineTo' : 'moveTo'](x + Math.cos(t) * rr, y + Math.sin(t) * rr);
    }
    ctx.closePath();
  }

  function draw() {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    // glasset
    const top = H * 0.12, rad = Math.min(40, W * 0.08);
    ctx.fillStyle = 'rgba(35, 72, 196, 0.06)';
    ctx.strokeStyle = '#141210';
    ctx.lineWidth = 4;
    ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(pad - 2, top);
    ctx.lineTo(pad - 2, H - pad + 2 - rad);
    ctx.quadraticCurveTo(pad - 2, H - pad + 2, pad - 2 + rad, H - pad + 2);
    ctx.lineTo(W - pad + 2 - rad, H - pad + 2);
    ctx.quadraticCurveTo(W - pad + 2, H - pad + 2, W - pad + 2, H - pad + 2 - rad);
    ctx.lineTo(W - pad + 2, top);
    ctx.fill(); ctx.stroke();
    // kant
    ctx.beginPath(); ctx.moveTo(pad - 12, top); ctx.lineTo(pad + 10, top); ctx.moveTo(W - pad - 10, top); ctx.lineTo(W - pad + 12, top); ctx.stroke();
    // stjerner
    ctx.lineWidth = 1.4;
    for (const b of stars) {
      starPath(b.position.x, b.position.y, r * 1.18, b.angle);
      ctx.fillStyle = b.plugin.c; ctx.fill(); ctx.stroke();
    }
    // glasrefleks
    ctx.strokeStyle = 'rgba(255,255,255,0.7)'; ctx.lineWidth = 6;
    ctx.beginPath(); ctx.moveTo(pad + 16, top + 24); ctx.lineTo(pad + 16, top + (H - top) * 0.35); ctx.stroke();
  }

  let last = 0, acc = 0;
  const STEP = 1000 / 60;
  function tick(now) {
    if (!running) return;
    acc += Math.min(now - last, 100); last = now;
    while (acc >= STEP) { Engine.update(engine, STEP); acc -= STEP; }
    draw();
    requestAnimationFrame(tick);
  }
  function start() { if (running) return; running = true; last = performance.now(); requestAnimationFrame(tick); }

  // Træk i stjernerne
  let drag = null;
  canvas.addEventListener('pointerdown', (e) => {
    const p = local(e);
    const hit = Query.point(stars, p)[0] || stars.find((s) => Vector.magnitude(Vector.sub(s.position, p)) < r * 2.2);
    if (!hit) return;
    const c = Constraint.create({ pointA: p, bodyB: hit, pointB: { x: 0, y: 0 }, stiffness: 0.1, damping: 0.1, length: 0 });
    Composite.add(engine.world, c);
    drag = { c, id: e.pointerId };
    canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener('pointermove', (e) => { if (drag && drag.id === e.pointerId) drag.c.pointA = local(e); });
  const end = () => { if (drag) { Composite.remove(engine.world, drag.c); drag = null; } };
  canvas.addEventListener('pointerup', end);
  canvas.addEventListener('pointercancel', end);
  function local(e) { const b = canvas.getBoundingClientRect(); return { x: e.clientX - b.left, y: e.clientY - b.top }; }

  root.querySelector('[data-shake]')?.addEventListener('click', () => {
    for (const s of stars) Body.setVelocity(s, { x: (Math.random() - 0.5) * 14, y: -6 - Math.random() * 14 });
  });

  new IntersectionObserver(([en]) => {
    visible = en.isIntersecting;
    if (visible) { start(); if (!filled && target) fillTick(); }
    else running = false;
  }, { threshold: 0.35 }).observe(root);

  size();
  let rt;
  addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { size(); draw(); }, 150); });

  return { setTarget };
}
