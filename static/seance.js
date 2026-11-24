// Séance : saisie, verdict, fin. Trois modes : jour, cible, rafale.
import { html, raw, ico, kbd, pill, pl, enonce, fiche, api, toast, montrer, aller, ctrl, surBouton, fenetreOuverte } from './base.js';

const CARACTERES = ['á', 'é', 'í', 'ó', 'ú', 'ñ', 'ü', '¿', '¡'];
const ALT = { a: 'á', e: 'é', i: 'í', o: 'ó', u: 'ú', n: 'ñ', U: 'ü', '?': '¿', '!': '¡' };
const RAFALE = 180;
let S = null, horloge;

export async function demarrer(mode, options = {}) {
  const { exercices } = await api('POST', 'seance', { mode, ...options });
  if (!exercices.length) return toast(mode === 'rafale' ? 'Aucun QCM ni choix contrasté actif pour ce concept.' : 'Aucun exercice actif à tirer.');
  S = { mode, file: exercices, i: 0, resultats: [], rejoue: mode !== 'jour', occupe: false };
  clearInterval(horloge);
  if (mode === 'rafale') {
    S.fin = Date.now() + RAFALE * 1000;
    horloge = setInterval(() => {
      const el = document.getElementById('chrono');
      if (el) el.textContent = chrono();
      if (Date.now() >= S.fin && !S.termine) terminer();
    }, 500);
  }
  nouveau();
  aller('#/seance');
}
export function ecran() {
  if (!S) return aller('#/');
  dessiner();
}

function nouveau() {
  Object.assign(S, { debut: Date.now(), aide: false, verdict: null, choix: null, occupe: false, vue: { acts, touche } });
}
const ex = () => S.file[S.i];
const chrono = () => { const s = Math.max(0, Math.ceil((S.fin - Date.now()) / 1000)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };
const champs = () => [...document.querySelectorAll('[data-reponse]')];
const donnees = () => ex().options ? [S.choix === null ? '' : ex().options[S.choix]] : champs().map((c) => c.value);

// ── Actions ──────────────────────────────────────────────────
async function valider() {
  if (S.occupe || S.verdict) return;
  S.occupe = true;
  S.donnees = donnees();
  S.duree = Math.round((Date.now() - S.debut) / 1000);
  await envoyer();
}
async function envoyer(decision) {
  const e = ex();
  try {
    const v = await api('POST', 'repondre', { exercice: e.id, reponse: S.donnees, mode: S.mode, aide: S.aide, duree: S.duree, decision });
    S.verdict = v;
    if (v.resultat !== 'averifier') S.resultats.push({ ex: e, resultat: v.resultat });
  } finally { S.occupe = false; }
  if (S.mode === 'rafale' && S.verdict.resultat === 'juste') { dessiner(); return setTimeout(() => S?.verdict && ex() === e && suivant(), 450); }
  dessiner();
}
async function suivant() {
  if (S.occupe || S.termine || S.verdict?.resultat === 'averifier') return;
  S.occupe = true;
  if (S.i + 1 >= S.file.length && !S.rejoue) {
    S.rejoue = true;
    const rates = S.resultats.filter((r) => ['faux', 'accent'].includes(r.resultat)).map((r) => r.ex.concepts[0]);
    if (rates.length) S.file.push(...(await api('POST', 'seance/rejouer', { concepts: rates, exclus: S.file.map((e) => e.id) })).exercices);
  }
  if (S.i + 1 >= S.file.length) return terminer();
  S.i += 1;
  nouveau();
  dessiner();
}
async function terminer() {
  clearInterval(horloge);
  S.termine = true;
  S.demain = (await api('POST', 'seance/fin', {})).demain;
  S.vue = { acts, touche };
  dessiner();
}
async function quitter() {
  clearInterval(horloge);
  if (!S.termine) await api('POST', 'seance/fin', {});   // ce qui a été répondu compte
  S = null;
  aller('#/');
}
async function raison() {
  if (S.verdict?.resultat === 'averifier') return envoyer('juste');
  if (S.verdict?.resultat !== 'faux' || ex().options || !S.donnees.some((d) => d.trim())) return;
  await api('POST', `tentatives/${S.verdict.tentative}/juste`, {});
  S.verdict.resultat = S.resultats.at(-1).resultat = 'juste';
  dessiner();
}
async function signaler() {
  await api('POST', 'exercices/statut', { ids: [ex().id], statut: 'retire' });
  toast('Exercice retiré. Il reste dans la bibliothèque, statut « Retiré ».');
  if (S.verdict) return dessiner();
  S.file.splice(S.i, 1);
  if (S.i >= S.file.length) { S.i -= 1; return suivant(); }
  nouveau();
  dessiner();
}
function indice() { if (ex().indice && !S.verdict && !S.aide) { S.aide = true; const v = champs().map((c) => c.value); dessiner(); champs().forEach((c, i) => { c.value = v[i]; }); libelle(); } }
function inserer(c) {
  const el = champs().includes(document.activeElement) ? document.activeElement : S.dernier?.isConnected ? S.dernier : champs()[0];
  if (!el) return;
  el.focus();
  el.setRangeText(c, el.selectionStart, el.selectionEnd, 'end');
  libelle();
}
function choisir(n) {
  if (S.verdict || !ex().options || n >= ex().options.length) return;
  S.choix = n;
  if (S.mode === 'rafale') return valider();
  dessiner();
}
const libelle = () => { const b = document.getElementById('valider'); if (b) b.firstChild.data = donnees().some((d) => d.trim()) ? 'Valider' : 'Je ne sais pas'; };

const acts = {
  quitter, suivant, valider, raison, signaler, indice, terminer: quitter,
  tort: () => envoyer('faux'), touche: (el) => inserer(el.dataset.c), choisir: (el) => choisir(+el.dataset.n),
  saisie: (_, el) => { S.dernier = el; libelle(); },
};
function touche(e) {
  if (e.key === 'Escape') { quitter(); return true; }
  if (S.termine) { if (e.key === 'Enter' && !surBouton(e)) { quitter(); return true; } return false; }
  if (ctrl(e, 'j')) { raison(); return true; }
  if (ctrl(e, 'f')) { if (S.verdict?.resultat === 'averifier') envoyer('faux'); return true; }
  if (e.key === 'Enter' && !e.shiftKey && !surBouton(e)) { if (S.verdict) suivant(); else valider(); return true; }
  if (e.key === 'Tab' && !e.shiftKey && ex().indice && !S.aide && !S.verdict) { indice(); return true; }
  if (ex().options && /^[1-4]$/.test(e.key) && !e.ctrlKey && !e.altKey) { choisir(+e.key - 1); return true; }
  if (e.altKey && !e.ctrlKey && ex().langue === 'es' && !ex().options && !S.verdict) {
    const c = ALT[e.key] || ALT[e.key.toLowerCase()];
    if (c) { inserer(c); return true; }
  }
  return false;
}

// ── Rendu ────────────────────────────────────────────────────
function dessiner() {
  if (!S) return;
  const n = S.termine ? S.file.length : S.i + (S.verdict ? 1 : 0), total = S.file.length;
  montrer(S.vue, html`<div class="plein">
    <header class="top prog">
      <button type="button" class="btn f" data-act="quitter">Quitter${kbd('Échap')}</button>
      <span class="barre" role="progressbar" aria-label="Progression de la séance" aria-valuemin="0" aria-valuemax="${total}" aria-valuenow="${n}"><span style="--v:${Math.round(100 * n / total)}%"></span></span>
      <span class="cap num" id="${S.mode === 'rafale' ? 'chrono' : ''}">${S.mode === 'rafale' && !S.termine ? chrono() : `${n} / ${total}`}</span>
    </header>
    ${S.termine ? ecranFin() : html`
    <main class="scene"><section class="carte lg col g24 up">
      <div class="col g12">
        <div class="meta">${pill(ex().langue)}<span>·</span><span>${ex().concept}</span><span>·</span><span>${ex().type_nom}</span></div>
        <div class="col g4"><p class="cap">${ex().consigne}</p><p class="enonce" id="enonce" lang="${ex().type === 'theme' ? 'fr' : ex().langue}">${enonce(ex().enonce)}</p></div>
      </div>
      ${S.verdict ? verdict() : zoneSaisie()}
    </section></main>
    <footer class="dock"><div>${S.verdict ? dockVerdict() : dockSaisie()}</div></footer>`}
  </div>`, 'Séance');
  if (!fenetreOuverte()) (document.querySelector('[data-reponse]') || (S.verdict && document.querySelector('.dock .p')))?.focus({ preventScroll: true });
  if (!S.termine && !S.verdict) libelle();
}

function zoneSaisie() {
  const e = ex();
  return html`<div class="col g12">
    ${e.options ? html`<div class="options" role="radiogroup" aria-label="Options">${e.options.map((o, i) =>
      html`<button type="button" role="radio" class="option" aria-checked="${S.choix === i}" data-act="choisir" data-n="${i}"><kbd>${i + 1}</kbd><span lang="${e.langue}">${o}</span></button>`)}</div>`
    : Array.from({ length: e.blancs }, (_, i) => e.blancs > 1
      ? html`<input type="text" class="champ reponse" data-reponse data-input="saisie" aria-label="Blanc ${i + 1}" placeholder="Blanc ${i + 1}" autocomplete="off" autocapitalize="off" spellcheck="false" lang="${e.langue}">`
      : html`<textarea class="champ reponse" data-reponse data-input="saisie" aria-label="Ta réponse" aria-describedby="enonce" rows="3" placeholder="Ta réponse…" autocomplete="off" autocapitalize="off" spellcheck="false" lang="${e.langue}"></textarea>`)}
    ${!e.options && e.langue === 'es' && html`<div class="touches" role="group" aria-label="Caractères espagnols">${CARACTERES.map((c) => html`<button type="button" tabindex="-1" data-act="touche" data-c="${c}" aria-label="Insérer ${c}">${c}</button>`)}</div>`}
    ${S.aide && html`<div class="creux" role="status"><p class="section">Indice</p><p>${e.indice}</p></div>`}
  </div>`;
}
const dockSaisie = () => html`
  ${ex().indice && html`<button type="button" class="btn" data-act="indice" ${raw(S.aide ? 'disabled' : '')}>${ico('indice')}Indice${kbd('Tab')}</button>`}
  <button type="button" class="btn f" data-act="signaler">${ico('drapeau')}Signaler</button>
  <button type="button" class="btn p" id="valider" data-act="valider">Valider${kbd('Entrée')}</button>`;

function dockVerdict() {
  const r = S.verdict.resultat;
  if (r === 'averifier') return html`<button type="button" class="btn" data-act="tort">C'était faux${kbd('Ctrl F')}</button><button type="button" class="btn p" data-act="raison">C'était juste${kbd('Ctrl J')}</button>`;
  return html`${r === 'faux' && !ex().options && S.donnees.some((d) => d.trim()) && html`<button type="button" class="btn f" data-act="raison">J'avais raison${kbd('Ctrl J')}</button>`}
    <button type="button" class="btn f" data-act="signaler">${ico('drapeau')}Signaler</button>
    <button type="button" class="btn p" data-act="suivant">Suivant${kbd('Entrée')}</button>`;
}

const mots = (liste, balise) => liste.map(([m, d], i) => html`${i ? ' ' : ''}${d ? balise(m) : m}`);
/** « ESTÁ » avec la lettre fautive surlignée. */
const lettres = ([donne, attendu]) => [...attendu].map((c, i) => c === [...donne][i] ? c.toUpperCase() : html`<mark>${c.toUpperCase()}</mark>`);

function verdict() {
  const v = S.verdict, r = v.resultat;
  const explication = v.explication && html`<p class="cap" style="color:var(--text)">${v.explication}</p>`;
  if (r === 'juste' || r === 'aide') return html`<div class="bandeau ${r === 'juste' ? 'juste' : 'orange'} up" role="status">${ico('juste', 20)}<div class="col g4 f1">
    <p class="titre">${r === 'juste' ? 'Juste' : 'Juste, avec aide'}</p><p lang="${ex().langue}">« ${v.donne} »</p>
    ${v.coquille && html`<p class="cap">Coquille signalée : <del>${v.coquille.donne}</del> → <b>${v.coquille.attendu}</b></p>`}${explication}</div></div>`;
  const plat = (s) => s.normalize('NFD').replace(/\p{M}/gu, '');
  if (r === 'accent') {
    const fautifs = new Set(v.accents.map(([d]) => d.toLowerCase()));
    const manque = v.accents.every(([d]) => d === plat(d));
    return html`<div class="bandeau orange up" role="status">${ico('alerte', 20)}<div class="col g4 f1">
      <p class="titre">Presque</p>
      <p>${manque ? 'Accent manquant' : 'Accent à corriger'} : ${v.accents.map((a, i) => html`${i ? ', ' : ''}${lettres(a)}`)}</p>
      <div><span class="cap">Ta réponse</span><p lang="${ex().langue}">« ${v.donne.split(' ').map((m, i) => html`${i ? ' ' : ''}${fautifs.has(m.toLowerCase().replace(/[^\p{L}\p{M}'-]/gu, '')) ? html`<span class="vague">${m}</span>` : m}`)} »</p></div>
      ${explication}</div></div>`;
  }
  const verif = r === 'averifier';
  return html`<div class="bandeau ${verif ? 'orange' : 'faux'} up" role="status">${ico(verif ? 'alerte' : 'faux', 20)}<div class="col g12 f1">
      <div><p class="titre">${verif ? 'À vérifier' : 'Incorrect'}</p>${verif && html`<p class="cap">Réponse absente de la liste. Comparer avec la référence, puis trancher.</p>`}</div>
      <div><span class="cap">Ta réponse</span><p style="font-size:17px" lang="${ex().langue}">${v.donne.trim() ? mots(v.diff_donne, (m) => html`<del>${m}</del>`) : '—'}</p></div>
      <div><span class="cap">Réponse attendue</span><p style="font-size:17px" lang="${ex().langue}">${mots(v.diff_attendu, (m) => html`<b class="fort">${m}</b>`)}</p></div>
      ${v.autres.length > 0 && html`<details style="font-size:14px"><summary class="lien row g4" style="display:inline-flex">${pl(v.autres.length, 'autre réponse acceptée', 'autres réponses acceptées')}<span class="chev row">${ico('bas')}</span></summary><ul style="list-style:disc;padding-left:20px;margin-top:4px" lang="${ex().langue}">${v.autres.map((a) => html`<li>${a}</li>`)}</ul></details>`}
      ${explication}
    </div></div>
    ${!verif && v.regle.fiche && html`<div class="creux col g4 up" style="--i:1"><p class="section">Règle — ${v.regle.titre}</p><p class="fiche">${fiche(v.regle.fiche)}</p></div>`}`;
}

function ecranFin() {
  const total = S.resultats.length, justes = S.resultats.filter((r) => r.resultat === 'juste' || r.resultat === 'aide').length;
  const par = new Map();
  for (const { ex: e, resultat } of S.resultats) {
    const c = par.get(e.concepts[0]) || { langue: e.langue, titre: e.concept, n: 0, ok: 0 };
    c.n += 1; c.ok += resultat === 'juste' || resultat === 'aide';
    par.set(e.concepts[0], c);
  }
  const etat = (c) => c.ok === c.n ? ['ok', 'Acquis'] : c.ok / c.n >= .6 ? ['moyen', 'Fragile'] : ['ko', 'À revoir'];
  return html`<main class="scene"><section class="carte lg col g24 up">
    <div class="col g4"><p class="section">Séance terminée</p><p class="hero">${justes} / ${total}</p><p class="cap">${total ? Math.round(100 * justes / total) : 0} % de réponses justes</p></div>
    ${total > 0 && html`<div class="col g8"><h2 class="section">Concepts revus</h2><ul class="concepts">${[...par.values()].map((c) => { const [d, t] = etat(c); return html`<li>${pill(c.langue)}<span class="f1" style="font-weight:500">${c.titre}</span><span class="cap num">${c.ok} / ${c.n}</span><span class="etat"><span class="dot ${d}"></span>${t}</span></li>`; })}</ul></div>`}
    ${S.mode === 'jour' && html`<div class="creux" style="padding:12px 16px;font-size:14px"><b class="fort">À revoir demain :</b> ${pl(S.demain, 'concept')}</div>`}
  </section></main>
  <footer class="dock"><div><button type="button" class="btn p" data-act="terminer">Terminer${kbd('Entrée')}</button></div></footer>`;
}
