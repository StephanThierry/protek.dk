import './style.css';
import { playground } from './playground.js';
import { jar } from './jar.js';

const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const root = document.documentElement;

// Years of experience follow the calendar.
document.querySelectorAll('[data-years-since]').forEach((el) => {
  const n = new Date().getFullYear() - parseInt(el.dataset.yearsSince, 10);
  if (n > 0) el.textContent = n;
});

// Scroll-driven CSS animations where supported, otherwise an IntersectionObserver fallback.
const sda = CSS.supports('animation-timeline: view()');
if (!sda) {
  root.classList.add('no-sda');
  const io = new IntersectionObserver((ents) => ents.forEach((en) => en.isIntersecting && en.target.classList.add('is-in')), { rootMargin: '0px 0px -12% 0px' });
  document.querySelectorAll('.job, .origin__stage, .poi__card, .topics li').forEach((el) => io.observe(el));
}

// --------------------------------------------------------- playground
document.fonts.ready.then(() => {
  try { playground(document.querySelector('.play'), { reduced }); }
  catch (e) { console.warn('Physics disabled:', e); }
});

// --------------------------------------------------------- CV filter with View Transitions
const jobs = [...document.querySelectorAll('.job')];
jobs.forEach((j, i) => (j.style.viewTransitionName = `job-${i}`));
document.querySelectorAll('.chip').forEach((chip) => {
  chip.addEventListener('click', () => {
    const f = chip.dataset.filter;
    const apply = () => {
      document.querySelectorAll('.chip').forEach((c) => { const on = c === chip; c.classList.toggle('is-on', on); c.setAttribute('aria-pressed', on); });
      jobs.forEach((j) => { j.hidden = f !== 'alle' && !j.dataset.tags.split(' ').includes(f); });
      document.querySelector('.cv__grid').dataset.filter = f;
    };
    if (document.startViewTransition && !reduced) document.startViewTransition(apply);
    else apply();
  });
});

// --------------------------------------------------------- GitHub jar
const countEl = document.querySelector('[data-gh-count]');
const reposEl = document.querySelector('[data-gh-repos]');
const theJar = jar(document.querySelector('.jar'), { reduced, counter: (n) => (countEl.textContent = n) });

(function githubStats() {
  const USER = 'StephanThierry', KEY = 'protek.gh', TTL = 6 * 3600 * 1000;
  let cache = null;
  try { cache = JSON.parse(localStorage.getItem(KEY)); } catch (e) { /* private window */ }
  theJar.setTarget(cache && cache.stars > 0 ? cache.stars : 264);
  if (cache?.repos) reposEl.textContent = cache.repos;
  if (cache && Date.now() - cache.t < TTL) return;
  fetch(`https://api.github.com/users/${USER}/repos?per_page=100&type=owner`)
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then((list) => {
      list = list.filter((r) => !r.fork);
      const sum = list.reduce((a, r) => a + (r.stargazers_count || 0), 0);
      if (!list.length || !sum) return;
      reposEl.textContent = list.length;
      theJar.setTarget(sum);
      try { localStorage.setItem(KEY, JSON.stringify({ t: Date.now(), stars: sum, repos: list.length })); } catch (e) { /* ignore */ }
    })
    .catch(() => {});
})();

// --------------------------------------------------------- active section in the menu
const links = [...document.querySelectorAll('.top__nav a')];
const secs = links.map((a) => document.querySelector(a.getAttribute('href')));
const navIO = new IntersectionObserver((ents) => {
  ents.forEach((en) => {
    if (!en.isIntersecting) return;
    links.forEach((a, i) => a.classList.toggle('is-on', secs[i] === en.target));
  });
}, { rootMargin: '-45% 0px -50% 0px' });
secs.forEach((s) => s && navIO.observe(s));
