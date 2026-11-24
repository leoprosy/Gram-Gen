// Socle : rendu échappé, API, icônes, composants, routage, clavier.

export const TYPES = window.TYPES, CONSIGNES = window.CONSIGNES;
export const STATUTS = { actif: 'Actif', a_valider: 'À valider', retire: 'Retiré', archive: 'Archivé' };

// ── Rendu ────────────────────────────────────────────────────
class Html extends String {}
export const raw = (s) => new Html(s);
const echappe = (v) => String(v).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
const rendre = (v) => v instanceof Html ? v : Array.isArray(v) ? v.map(rendre).join('')
  : v === null || v === undefined || v === false ? '' : echappe(v);
/** Gabarit balisé : toute valeur est échappée, sauf un autre gabarit. */
export const html = (s, ...v) => raw(s.reduce((a, x, i) => a + x + (i < v.length ? rendre(v[i]) : ''), ''));

const ICONES = {
  reglages: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
  cible: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
  eclair: '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
  page: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
  plus: '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
  croix: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
  droite: '<polyline points="9 18 15 12 9 6"/>', gauche: '<polyline points="15 18 9 12 15 6"/>', bas: '<polyline points="6 9 12 15 18 9"/>',
  alerte: '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
  juste: '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
  faux: '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>',
  indice: '<path d="M9 18h6"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.3h6c0-1 .4-1.8 1-2.3A7 7 0 0 0 12 2z"/>',
  drapeau: '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/>',
  loupe: '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
  importer: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
  crayon: '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  boite: '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
};
export const ico = (n, t = 16) => raw(`<svg class="i" aria-hidden="true" width="${t}" height="${t}" viewBox="0 0 24 24">${ICONES[n]}</svg>`);
export const kbd = (t) => html`<kbd aria-hidden="true">${t}</kbd>`;
export const pill = (l) => html`<span class="pill">${l.toUpperCase()}</span>`;
export const pl = (n, mot, pluriel = mot + 's') => `${n} ${n > 1 ? pluriel : mot}`;
export const barre = (p, nom) => html`<span class="barre" role="progressbar" aria-label="${nom}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${p}"><span style="--v:${p}%"></span></span>`;

/** Choix segmenté. options : [[valeur, libellé], …] ; le changement part vers acts[nom](valeur). */
export const seg = (nom, options, cur, label, cls = '') => html`<div class="seg ${cls}" role="radiogroup" aria-label="${label}">${options.map(([v, l]) =>
  html`<label><input type="radio" id="seg-${nom}-${v}" name="${nom}" value="${v}" data-change="${nom}" ${raw(String(v) === String(cur) ? 'checked' : '')}>${l}</label>`)}</div>`;
export const select = (nom, options, cur, attrs = '') => html`<select name="${nom}" data-change="${nom}" ${raw(attrs)}>${options.map(([v, l]) =>
  html`<option value="${v}" ${raw(v === cur ? 'selected' : '')}>${l}</option>`)}</select>`;

/** Énoncé : {{1}} et ___ deviennent des blancs. */
export const enonce = (texte) => texte.split(/(\{\{\d+\}\}|_{2,})/).map((p) =>
  /^\{\{\d+\}\}$|^_{2,}$/.test(p) ? raw('<span class="blanc"><span class="vh">blanc</span></span>') : html`${p}`);
/** Fiche-règle : **gras** et `forme`. */
export const fiche = (t) => raw(String(html`${t}`).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/&#96;(.+?)&#96;|`(.+?)`/g, '<code>$1$2</code>'));

// ── Dates ────────────────────────────────────────────────────
const jours = (iso) => { const d = new Date(iso.slice(0, 10) + 'T00:00'), n = new Date(); n.setHours(0, 0, 0, 0); return Math.round((d - n) / 864e5); };
export const ilya = (iso) => {
  if (!iso) return 'jamais';
  const j = -jours(iso);
  return j <= 0 ? "aujourd'hui" : j === 1 ? 'hier' : j < 14 ? `il y a ${j} j` : j < 60 ? `il y a ${Math.round(j / 7)} sem.` : `il y a ${Math.round(j / 30)} mois`;
};
export const dans = (iso) => {
  if (!iso) return 'À découvrir';
  const j = jours(iso);
  return j <= 0 ? "Aujourd'hui" : j === 1 ? 'Demain' : `Dans ${j} jours`;
};
export const duree = (s) => { const m = Math.round(s / 60), h = Math.floor(m / 60); return h ? `${h} h ${String(m % 60).padStart(2, '0')}` : `${m} min`; };

// ── API ──────────────────────────────────────────────────────
export async function api(methode, url, corps) {
  let r;
  try {
    r = await fetch('/api/' + url, { method: methode, headers: corps === undefined ? {} : { 'Content-Type': 'application/json' }, body: corps === undefined ? undefined : JSON.stringify(corps) });
  } catch { throw Object.assign(new Error('Le serveur local ne répond plus. Relancer Gram-Gen.'), { data: {} }); }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(data.erreur || 'Erreur inattendue.'), { status: r.status, data });
  return data;
}
let minuterie;
export function toast(t) {
  const el = document.getElementById('toast');
  el.textContent = t;
  el.classList.add('on');
  clearTimeout(minuterie);
  minuterie = setTimeout(() => el.classList.remove('on'), 2600);
}
addEventListener('unhandledrejection', (e) => toast(e.reason?.message || 'Erreur inattendue.'));

// ── Vues, fenêtres, événements ───────────────────────────────
// Vue ou fenêtre : { acts: {nom(el|valeur, e)}, touche(e) → true si traitée }
const racine = document.getElementById('app');
let vue = { acts: {} };
const fenetres = [];
const courante = () => fenetres.at(-1) || vue;

export function montrer(v, contenu, titre) {
  const premiere = vue !== v;
  vue = v;
  racine.classList.toggle('anime', premiere);
  if (titre) document.title = `Gram-Gen — ${titre}`;
  remplacer(racine, contenu);
  if (premiere) scrollTo(0, 0);
}
/** Remplace le contenu en gardant le focus et le curseur sur l'élément de même id. */
export function remplacer(el, contenu) {
  const a = document.activeElement, id = el.contains(a) && a.id, sel = id && 'selectionStart' in a ? a.selectionStart : null;
  const defil = [...el.querySelectorAll('[data-defil]')].map((x) => [x.dataset.defil, x.scrollTop]);
  el.innerHTML = contenu;
  for (const [nom, y] of defil) { const x = el.querySelector(`[data-defil="${nom}"]`); if (x) x.scrollTop = y; }
  const suivant = id && document.getElementById(id);
  if (suivant) { suivant.focus(); if (sel !== null && suivant.type !== 'radio') try { suivant.setSelectionRange(sel, sel); } catch { /* type sans curseur */ } }
}
/** Ouvre un <dialog>. f : { acts, touche, rendu() → html, classe, nom } ; f.maj() redessine, f.fermer() ferme. */
export function fenetre(f) {
  const d = document.createElement('dialog');
  d.className = f.classe || '';
  d.setAttribute('aria-label', f.nom);
  document.body.append(d);
  f.el = d;
  f.maj = () => remplacer(d, f.rendu());
  f.fermer = () => { if (!d.isConnected) return; fenetres.splice(fenetres.indexOf(f), 1); d.close(); d.remove(); f.apres?.(); };
  d.addEventListener('cancel', (e) => { e.preventDefault(); f.fermer(); });
  d.addEventListener('mousedown', (e) => { if (e.target === d) { const r = d.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) f.fermer(); } });
  fenetres.push(f);
  f.maj();
  d.showModal();
  d.querySelector('[data-focus]')?.focus();
  return f;
}
export const fenetreOuverte = () => fenetres.length > 0;

document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-act]');
  if (el && !el.disabled) courante().acts[el.dataset.act]?.(el, e);
});
document.addEventListener('change', (e) => {
  const el = e.target.closest('[data-change]');
  if (el) courante().acts[el.dataset.change]?.(el.type === 'checkbox' ? el.checked : el.value, el);
});
document.addEventListener('input', (e) => {
  const el = e.target.closest('[data-input]');
  if (el) courante().acts[el.dataset.input]?.(el.value, el);
});
export const globales = [];   // raccourcis partout : (e) → true si traité
document.addEventListener('keydown', (e) => {
  if (e.repeat && e.key === 'Enter') return e.preventDefault();
  if (courante().touche?.(e) || (!fenetreOuverte() && globales.some((f) => f(e)))) e.preventDefault();
});
export const ctrl = (e, l) => e.ctrlKey && !e.altKey && !e.shiftKey && e.key.toLowerCase() === l;
export const saisie = (e) => e.target.closest('input:not([type=radio]):not([type=checkbox]), textarea, select');
/** Entrée laissée au bouton ou au lien qui a le focus. */
export const surBouton = (e) => e.target.closest('button, a, summary');

// ── Routage ──────────────────────────────────────────────────
export const routes = {};
export const aller = (h) => { if (location.hash === h) router(); else location.hash = h; };
// En file : deux navigations rapprochées ne peuvent pas s'afficher dans le désordre.
let enCours = Promise.resolve();
export const router = () => enCours = enCours.catch(() => {}).then(() => {
  while (fenetres.length) fenetres.at(-1).fermer();
  const [, nom, arg] = location.hash.split('/');
  return (routes[nom || ''] || routes[''])(arg && decodeURIComponent(arg));
});
addEventListener('hashchange', router);

const LOGO = raw('<svg role="img" aria-label="" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke-linecap="round" stroke-width="1.7"><path d="M2 12h4M14.5 12H18M8 14.5h4.5" stroke="var(--text)"/><path d="M10.25 4.5v5M7.75 7h5" stroke="var(--accent)"/></svg>');
export const barreHaut = (ici) => html`<header class="top">
  <div class="logo">${LOGO}<span>Gram-Gen</span></div>
  <nav aria-label="Navigation principale">${[['#/', "Aujourd'hui"], ['#/bibliotheque', 'Bibliothèque'], ['#/stats', 'Statistiques']].map(([h, t]) =>
    html`<a href="${h}" ${raw(h === ici ? 'aria-current="page"' : '')}>${t}</a>`)}</nav>
  <span class="f1"></span>
  <a href="#/reglages" class="btn f ico" aria-label="Réglages" ${raw(ici === '#/reglages' ? 'aria-current="page" style="color:var(--text)"' : '')}>${ico('reglages', 20)}</a>
</header>`;
