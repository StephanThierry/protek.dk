import './style.css';
import { liveStory } from './flow.js';

const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

// Years of experience and today's date follow the calendar.
document.querySelectorAll('[data-years-since]').forEach((el) => {
  const n = new Date().getFullYear() - parseInt(el.dataset.yearsSince, 10);
  if (n > 0) el.textContent = n;
});
const today = new Date().toLocaleDateString('da-DK', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
document.querySelectorAll('[data-today]').forEach((el) => {
  el.textContent = today.charAt(0).toUpperCase() + today.slice(1);
  el.dateTime = new Date().toISOString().slice(0, 10);
});

// --------------------------------------------------------- the living front page
const perfEl = document.querySelector('[data-perf]');
const fmt = new Intl.NumberFormat('da-DK', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
(async () => {
  try {
    await document.fonts.ready;
    await Promise.all([
      document.fonts.load('400 18px "Newsreader"', 'Det begyndte æøå'),
      document.fonts.load('400 17px "Newsreader"', 'Det begyndte æøå'),
      document.fonts.load('800 90px "Newsreader"', 'D'),
    ]);
    await liveStory(document.querySelector('[data-story]'), {
      reduced,
      onPerf: (ms) => { perfEl.textContent = ` · ${fmt.format(Math.max(ms, 0.1))} ms pr. sats`; },
    });
  } catch (e) {
    console.warn('Live typesetting disabled, showing plain text:', e);
  }
})();

// --------------------------------------------------------- Stock exchange: GitHub numbers and ticker
const starsEl = document.querySelector('[data-gh-stars]');
const reposEl = document.querySelector('[data-gh-repos]');
const tickerEl = document.querySelector('[data-ticker]');

function ticker(stars, repos) {
  const items = [
    `★ Stjerner <b>${stars}</b> <em>▲</em>`, `Repos <b>${repos}</b>`, 'Sikkerhed', 'Machine learning <b>99,9 %</b>',
    'Serverdrift <em>★</em>', 'DevOps', 'Protek <b>est. 1998</b>', 'TravelMind Group', 'Harness Engineering <em>▲</em>',
  ];
  const run = items.map((t) => `<span>${t}</span>`).join('');
  tickerEl.innerHTML = run + run;
}

function countTo(el, to) {
  const from = parseInt(el.textContent, 10) || 0;
  if (reduced || from === to) { el.textContent = to; return; }
  const t0 = performance.now(), dur = 1200;
  const step = (now) => {
    const k = Math.min(1, (now - t0) / dur);
    el.textContent = Math.round(from + (to - from) * (1 - (1 - k) ** 3));
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

(function githubStats() {
  const USER = 'StephanThierry', KEY = 'protek.gh', TTL = 6 * 3600 * 1000;
  let cache = null;
  try { cache = JSON.parse(localStorage.getItem(KEY)); } catch (e) { /* private window */ }
  const set = (stars, repos) => { countTo(starsEl, stars); reposEl.textContent = repos; ticker(stars, repos); };
  set(cache?.stars > 0 ? cache.stars : 264, cache?.repos || 23);
  if (cache && Date.now() - cache.t < TTL) return;
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

// --------------------------------------------------------- clippings slide in
if (!reduced && 'IntersectionObserver' in window) {
  document.documentElement.classList.add('reveal');
  const io = new IntersectionObserver((ents) => ents.forEach((en) => {
    if (en.isIntersecting) { en.target.classList.add('is-in'); io.unobserve(en.target); }
  }), { rootMargin: '0px 0px -8% 0px' });
  document.querySelectorAll('.clip, .feature, .ad, .strip, .market > *').forEach((el) => io.observe(el));
}

// --------------------------------------------------------- active section in the menu
const links = [...document.querySelectorAll('.sections a')];
const secs = links.map((a) => document.querySelector(a.getAttribute('href')));
const navIO = new IntersectionObserver((ents) => {
  ents.forEach((en) => {
    if (!en.isIntersecting) return;
    links.forEach((a, i) => a.classList.toggle('is-on', secs[i] === en.target));
  });
}, { rootMargin: '-40% 0px -55% 0px' });
secs.forEach((s) => s && navIO.observe(s));
