import Matter from 'matter-js';

const { Engine, Bodies, Body, Composite, Constraint, Events, Vector } = Matter;

// Turns a DOM element into a physics body. The element follows the body every frame (translate + rotate).
// The name letters start as static ("frozen") bodies in their place in the heading
// and wake up when grabbed or hit by something.

const COLORS = { red: '#E2412B', blue: '#2348C4', yellow: '#F4B71E', ink: '#141210' };

export function playground(root, { reduced = false } = {}) {
  const world = root.querySelector('.play__world');
  const words = [...root.querySelectorAll('.play__name .word')];
  const portrait = root.querySelector('.play__portrait');
  const hint = root.querySelector('.hint');

  const engine = Engine.create({ enableSleeping: false });
  engine.gravity.y = 1.1;
  const items = []; // { el, body, w, h, home?, letter? }
  let walls = [];
  let W = 0, H = 0;

  // --------------------------------------------------- letters
  const chars = [];
  words.forEach((word) => {
    const text = word.textContent;
    word.textContent = '';
    for (const c of text) {
      const s = document.createElement('span');
      s.className = 'ch';
      s.textContent = c;
      word.appendChild(s);
      chars.push(s);
    }
  });

  function measureHomes() {
    chars.forEach((c) => { c.style.cssText = ''; c.classList.remove('is-free'); });
    const base = root.getBoundingClientRect();
    return chars.map((c) => {
      const r = c.getBoundingClientRect();
      return { x: r.left - base.left + r.width / 2, y: r.top - base.top + r.height / 2, w: r.width, h: r.height };
    });
  }

  // The letters are absolutely positioned in the heading (to keep its typography), so their
  // coordinate system is offset from the playground by the heading position (ox, oy).
  function placeEl(it) {
    const { x, y } = it.body.position;
    const ox = it.ox || 0, oy = it.oy || 0;
    it.el.style.transform = `translate3d(${x - it.w / 2 - ox}px, ${y - it.h / 2 - oy}px, 0) rotate(${it.body.angle}rad)`;
  }

  function buildLetters() {
    items.filter((it) => it.letter).forEach((it) => Composite.remove(engine.world, it.body));
    for (let i = items.length - 1; i >= 0; i--) if (items[i].letter) items.splice(i, 1);
    const homes = measureHomes();
    const nameEl = root.querySelector('.play__name');
    const nb = nameEl.getBoundingClientRect(), rb = root.getBoundingClientRect();
    const ox = nb.left - rb.left + nameEl.clientLeft, oy = nb.top - rb.top + nameEl.clientTop;
    chars.forEach((el, i) => {
      const h = homes[i];
      const body = Bodies.rectangle(h.x, h.y, h.w * 0.86, h.h * 0.8, {
        friction: 0.5, frictionAir: 0.012, restitution: 0.2, density: 0.003,
        chamfer: { radius: Math.min(h.w, h.h) * 0.08 },
      });
      // Created dynamic and frozen afterwards. If created static, Matter stores infinite mass
      // as "original", and the position becomes NaN when they wake up.
      Body.setStatic(body, true);
      el.style.position = 'absolute';
      el.style.left = '0'; el.style.top = '0';
      el.style.width = `${h.w}px`; el.style.height = `${h.h}px`;
      const it = { el, body, w: h.w, h: h.h, ox, oy, home: { x: h.x, y: h.y }, letter: true };
      body.plugin.item = it;
      el._item = it;
      items.push(it);
      Composite.add(engine.world, body);
      placeEl(it);
    });
  }

  function wake(body) {
    if (body.isStatic && body.plugin.item?.letter) {
      Body.setStatic(body, false);
      body.plugin.item.el.classList.add('is-free');
      body.plugin.item.homing = false;
    }
  }

  // --------------------------------------------------- walls
  function buildWalls() {
    Composite.remove(engine.world, walls);
    const t = 200;
    walls = [
      Bodies.rectangle(W / 2, H + t / 2, W * 3, t, { isStatic: true }),
      Bodies.rectangle(-t / 2, H / 2 - 400, t, H * 3, { isStatic: true }),
      Bodies.rectangle(W + t / 2, H / 2 - 400, t, H * 3, { isStatic: true }),
      Bodies.rectangle(W / 2, -900 - t / 2, W * 3, t, { isStatic: true }),
    ];
    Composite.add(engine.world, walls);
  }

  // --------------------------------------------------- shapes
  function makeShape(kind, size, color, x, y) {
    let body, el;
    const opts = { friction: 0.3, frictionAir: 0.008, restitution: 0.45, density: 0.0015 };
    if (kind === 'circle' || kind === 'ring' || kind === 'portrait') {
      body = Bodies.circle(x, y, size / 2, opts);
      el = document.createElement(kind === 'portrait' ? 'div' : 'div');
      el.className = `shape shape--${kind}`;
      el.style.setProperty('--c', color);
      if (kind === 'portrait') { el.appendChild(portrait); portrait.hidden = false; }
      el.style.width = el.style.height = `${size}px`;
      const it = { el, body, w: size, h: size };
      return finish(it);
    }
    let verts;
    if (kind === 'triangle') verts = [{ x: 0, y: -size * 0.58 }, { x: size * 0.5, y: size * 0.29 }, { x: -size * 0.5, y: size * 0.29 }];
    else if (kind === 'half') {
      verts = [];
      for (let i = 0; i <= 16; i++) { const a = Math.PI + (i / 16) * Math.PI; verts.push({ x: Math.cos(a) * size / 2, y: Math.sin(a) * size / 2 }); }
    } else {
      const s = size * 0.86;
      verts = [{ x: -s / 2, y: -s / 2 }, { x: s / 2, y: -s / 2 }, { x: s / 2, y: s / 2 }, { x: -s / 2, y: s / 2 }];
    }
    body = Bodies.fromVertices(x, y, [verts], opts);
    const rel = body.vertices.map((v) => ({ x: v.x - body.position.x, y: v.y - body.position.y }));
    const mx = Math.max(...rel.map((p) => Math.abs(p.x))), my = Math.max(...rel.map((p) => Math.abs(p.y)));
    const w = mx * 2, h = my * 2;
    el = document.createElement('div');
    el.className = `shape shape--${kind}`;
    el.style.width = `${w}px`; el.style.height = `${h}px`;
    el.innerHTML = `<svg viewBox="${-mx} ${-my} ${w} ${h}" width="${w}" height="${h}"><polygon points="${rel.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')}" fill="${color}"/></svg>`;
    return finish({ el, body, w, h });

    function finish(it) {
      body.plugin.item = it;
      el._item = it;
      world.appendChild(el);
      items.push(it);
      Composite.add(engine.world, body);
      placeEl(it);
      return it;
    }
  }

  function spawnShapes() {
    const wide = W > 900;
    const unit = Math.max(46, Math.min(W, H) * (wide ? 0.13 : 0.17));
    const nameBottom = Math.max(...items.filter((i) => i.letter).map((i) => i.home.y + i.h / 2));
    const list = [
      ['portrait', unit * 1.5, COLORS.ink],
      ['circle', unit * 1.2, COLORS.red],
      ['square', unit * 1.1, COLORS.blue],
      ['triangle', unit * 1.25, COLORS.yellow],
      ['half', unit * 1.3, COLORS.ink],
      ['ring', unit * 0.8, COLORS.blue],
      ['square', unit * 0.6, COLORS.yellow],
      ['circle', unit * 0.55, COLORS.ink],
      ['triangle', unit * 0.7, COLORS.red],
    ];
    list.forEach(([kind, size, color], i) => {
      let x, y;
      if (reduced) {
        x = wide ? W * (0.6 + 0.38 * (i / list.length)) : W * ((i + 0.5) / list.length);
        y = H - size;
      } else if (wide) {
        x = W * (0.6 + Math.random() * 0.34);
        y = -size - i * unit * 1.1;
      } else {
        x = W * (0.12 + Math.random() * 0.76);
        y = nameBottom + size * 0.8 - i * 4;
      }
      const it = makeShape(kind, size, color, x, y);
      Body.setAngle(it.body, Math.random() * Math.PI);
      if (!reduced && !wide) {
        // Mobile: shapes pop up below the name with a small upward nudge, without toppling the letters.
        it.el.style.opacity = '0';
        setTimeout(() => {
          it.el.style.transition = 'opacity .4s'; it.el.style.opacity = '1';
          Body.setStatic(it.body, false);
          Body.setVelocity(it.body, { x: (Math.random() - 0.5) * 6, y: 1 });
        }, 300 + i * 160);
        Body.setStatic(it.body, true);
      }
    });
  }

  // Anything hitting a frozen letter hard enough wakes it.
  Events.on(engine, 'collisionStart', (e) => {
    for (const p of e.pairs) {
      const a = p.bodyA, b = p.bodyB;
      const speed = Math.max(a.speed || 0, b.speed || 0);
      if (speed < 2.2) continue;
      if (a.isStatic && !b.isStatic) wake(a);
      if (b.isStatic && !a.isStatic) wake(b);
    }
  });

  // --------------------------------------------------- drag and throw
  let drag = null;
  root.addEventListener('pointerdown', (e) => {
    const el = e.target.closest('.ch, .shape');
    if (!el || !el._item) return;
    e.preventDefault();
    const it = el._item;
    wake(it.body);
    const p = local(e);
    const off = Vector.rotate(Vector.sub(p, it.body.position), -it.body.angle);
    const c = Constraint.create({ pointA: p, bodyB: it.body, pointB: off, stiffness: 0.12, damping: 0.08, length: 0 });
    Composite.add(engine.world, c);
    drag = { c, el, id: e.pointerId };
    el.setPointerCapture(e.pointerId);
    el.classList.add('is-grabbed');
    root.classList.add('is-touched');
  });
  root.addEventListener('pointermove', (e) => {
    if (drag && e.pointerId === drag.id) drag.c.pointA = local(e);
  });
  const end = (e) => {
    if (!drag || e.pointerId !== drag.id) return;
    Composite.remove(engine.world, drag.c);
    drag.el.classList.remove('is-grabbed');
    drag = null;
  };
  root.addEventListener('pointerup', end);
  root.addEventListener('pointercancel', end);

  // Click on empty space: a small explosion.
  root.addEventListener('click', (e) => {
    if (e.target.closest('.ch, .shape, a, button, .play__intro')) return;
    const p = local(e);
    for (const it of items) {
      const d = Vector.sub(it.body.position, p), dist = Vector.magnitude(d);
      if (dist > 320) continue;
      wake(it.body);
      if (it.body.isStatic) continue;
      const f = (1 - dist / 320) * 0.06 * it.body.mass;
      Body.applyForce(it.body, it.body.position, Vector.mult(Vector.normalise({ x: d.x, y: d.y - 40 }), f));
    }
    root.classList.add('is-touched');
  });

  function local(e) {
    const r = root.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }

  // --------------------------------------------------- tidy up
  function reset() {
    for (const it of items) {
      if (!it.letter) continue;
      if (it.body.isStatic) continue;
      it.homing = true;
      Body.setStatic(it.body, true); // moved home manually so they do not push
      it.from = { x: it.body.position.x, y: it.body.position.y, a: it.body.angle };
      it.t = 0;
    }
  }
  root.querySelector('[data-reset]')?.addEventListener('click', reset);

  // --------------------------------------------------- loop
  let running = false, last = 0, acc = 0;
  const STEP = 1000 / 60;
  function tick(now) {
    if (!running) return;
    acc += Math.min(now - last, 100);
    last = now;
    while (acc >= STEP) { Engine.update(engine, STEP); acc -= STEP; }
    for (const it of items) {
      if (it.homing) {
        it.t = Math.min(1, it.t + 0.03);
        const k = 1 - Math.pow(1 - it.t, 3);
        Body.setPosition(it.body, { x: it.from.x + (it.home.x - it.from.x) * k, y: it.from.y + (it.home.y - it.from.y) * k });
        Body.setAngle(it.body, it.from.a * (1 - k));
        if (it.t >= 1) { it.homing = false; it.el.classList.remove('is-free'); }
      }
      if (!it.body.isStatic || it.homing) placeEl(it);
    }
    requestAnimationFrame(tick);
  }
  function start() { if (running) return; running = true; last = performance.now(); acc = 0; requestAnimationFrame(tick); }
  function stop() { running = false; }

  new IntersectionObserver(([en]) => (en.isIntersecting ? start() : stop())).observe(root);

  // --------------------------------------------------- startup and resize
  function size() {
    W = root.clientWidth; H = root.clientHeight;
  }
  size();
  buildWalls();
  buildLetters();
  spawnShapes();
  root.classList.add('is-live');

  let lastW = W, rt;
  addEventListener('resize', () => {
    clearTimeout(rt);
    rt = setTimeout(() => {
      size();
      buildWalls();
      if (Math.abs(W - lastW) > 40) {
        lastW = W;
        buildLetters(); // new font size: re-measure and reposition the letters
        for (const it of items) if (!it.letter) {
          Body.setPosition(it.body, { x: Math.min(Math.max(it.body.position.x, 40), W - 40), y: Math.min(it.body.position.y, H - 60) });
          placeEl(it);
        }
      }
    }, 200);
  });

  // Hint disappears after first touch
  root.addEventListener('pointerdown', () => hint?.classList.add('is-gone'), { once: true });
}
