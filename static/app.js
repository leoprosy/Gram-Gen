// Écrans : accueil, bibliothèque, validation, statistiques, réglages.
import { html, raw, ico, kbd, pill, pl, barre, barreHaut, seg, select, enonce, fiche, ilya, dans, duree, TYPES, STATUTS, api, toast, montrer, aller, router, routes, globales, ctrl, saisie, surBouton } from './base.js';
import { surveiller, aFaire, actsMaj, ligneMaj } from './maj.js';
import { demarrer, ecran as ecranSeance } from './seance.js';
import { panneau, choisirConcept, generer, importerFichier, nouveauConcept, chercher } from './panneau.js';

const enc = encodeURIComponent;
globales.push((e) => {
  if (location.hash.startsWith('#/seance') && !ctrl(e, 'n')) return false;
  if (ctrl(e, 'n')) { panneau({ apres: () => { if (!location.hash.startsWith('#/seance')) router(); } }); return true; }
  if (ctrl(e, 'k')) { focusRecherche = true; if (location.hash.startsWith('#/bibliotheque')) router(); else aller('#/bibliotheque'); return true; }
  return false;
});
let focusRecherche = false;

// ── Accueil ──────────────────────────────────────────────────
routes[''] = async () => {
  const d = await api('GET', 'accueil');
  let minutes = d.duree;
  const total = d.dus.en + d.dus.es;
  const cible = () => choisirConcept('Entraînement ciblé', 'Un seul point, hors planning.', (c) => demarrer('cible', { concept: c }));
  const rafale = () => choisirConcept('Rafale contraste', 'Le concept et ses voisins, mélangés. 3 minutes.', (c) => demarrer('rafale', { concept: c }));
  const generation = async (code) => generer((await api('GET', 'concepts')).find((c) => c.code === code), router);
  const commencer = () => demarrer('jour', { duree: minutes });
  const v = {
    acts: {
      ...actsMaj, commencer, cible, rafale, ajouter: () => panneau({ apres: router }), minutes: (x) => { minutes = +x; dessiner(); },
      faible: (el) => demarrer('cible', { concept: el.dataset.code }), generer: (el) => generation(el.dataset.code), file: () => aller('#/validation'),
    },
    touche(e) {
      if (e.ctrlKey || e.altKey || e.metaKey) return false;
      if (e.key === 'Enter' && total && !surBouton(e)) { commencer(); return true; }
      if (e.key === '1') { cible(); return true; }
      if (e.key === '2' && total) { rafale(); return true; }
    },
  };
  const mode = (i, act, icone, touche, titre, texte, off) => html`<button type="button" class="carte col g12 up" style="--i:${i}" data-act="${act}" ${raw(off ? 'disabled' : '')}>
    <span class="row" style="justify-content:space-between;width:100%"><span class="icone">${ico(icone, 20)}</span>${kbd(touche)}</span>
    <span class="col g2"><span class="fort">${titre}</span><span class="cap">${texte}</span></span></button>`;
  const dessiner = () => montrer(v, html`${barreHaut('#/')}<main class="page">
    <div class="up"><h1>Aujourd'hui</h1><p class="cap">${new Date().toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })}</p></div>
    <div class="deux"><div class="col g16">
      ${total ? html`<section class="carte lg col g24 up" style="--i:1" aria-labelledby="t-seance">
        <div class="col g8"><h2 class="hero" id="t-seance">${pl(total, 'exercice')} à réviser</h2>
          <div class="row wrap g8" style="font-size:14px">${['en', 'es'].map((l) => html`<span class="row g6">${pill(l)}${d.dus[l]}</span><span style="color:var(--text-3)">·</span>`)}<span style="color:var(--text-2)">environ ${Math.min(minutes, Math.ceil(total * 40 / 60))} min</span></div></div>
        ${seg('minutes', [[10, '10 min'], [15, '15 min'], [25, '25 min']], minutes, 'Durée de la séance')}
        <button type="button" class="btn p xl" data-act="commencer">Commencer la séance${kbd('Entrée')}</button>
        <p class="cap">Série : ${pl(d.serie, 'jour')}</p></section>
        <div class="modes" style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px">
          ${mode(2, 'cible', 'cible', '1', 'Entraînement ciblé', 'Un seul point de grammaire, en continu.')}
          ${mode(3, 'rafale', 'eclair', '2', 'Rafale contraste', 'Deux notions voisines, mélangées vite.')}
          ${mode(4, '', 'page', 'V2', 'Examen blanc', 'Chronométré, sans indice, noté.', true)}</div>`
    : html`<section class="carte lg col g24 up" style="--i:1" aria-labelledby="t-seance">
        <span class="icone" style="width:48px;height:48px">${ico('juste', 24)}</span>
        <div class="col g8"><h2 class="hero" id="t-seance">Tout est à jour</h2><p style="color:var(--text-2)">Aucun exercice à réviser aujourd'hui.</p></div>
        <p class="cap">Série : ${pl(d.serie, 'jour')}</p></section>
        <div class="modes" style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px">
          ${mode(2, 'cible', 'cible', '1', 'Entraînement ciblé', 'Un seul point de grammaire, en continu.')}
          ${mode(3, 'ajouter', 'plus', 'Ctrl N', 'Ajouter des exercices', 'Saisir une faute vue en colle ou en DS.')}</div>`}
    </div><aside class="col g24">
      <section class="carte col g8 up" style="--i:2"><h2 class="section">Points faibles</h2>
        ${d.faibles.length ? html`<div class="col g4">${d.faibles.map((c) => html`<button type="button" class="survol col g8" style="padding:12px;margin:0 -12px" data-act="faible" data-code="${c.code}" aria-label="Entraînement ciblé : ${c.titre}, maîtrise ${c.maitrise} %">
          <span class="row g8" style="width:100%">${pill(c.langue)}<span class="f1 fort tronque">${c.titre}</span><span class="cap num">${c.maitrise} %</span></span><span class="barre" aria-hidden="true"><span style="--v:${c.maitrise}%"></span></span></button>`)}</div>`
    : html`<p class="cap">Ils apparaîtront après la première séance.</p>`}</section>
      ${(d.reservoirs.length > 0 || d.a_valider > 0 || aFaire()) && html`<section class="carte col g16 up" style="--i:3"><h2 class="section">À traiter</h2><div class="col g8">${ligneMaj()}
        ${d.reservoirs.map((c) => html`<div class="bandeau orange mince">${ico('alerte')}<span class="f1"><b class="fort">${c.titre}</b> — ${c.non_vus ? `plus que ${pl(c.non_vus, 'exercice non vu', 'exercices non vus')}` : 'plus aucun exercice non vu'}</span><button type="button" class="btn f" style="color:var(--text)" data-act="generer" data-code="${c.code}">Générer</button></div>`)}
        ${d.a_valider > 0 && html`<button type="button" class="creux survol row g12" style="min-height:48px;padding:0 12px 0 16px;font-size:14px" data-act="file"><span class="f1">${pl(d.a_valider, 'exercice')} à valider</span><span class="row" style="color:var(--text-2)">${ico('droite')}</span></button>`}
      </div></section>`}
    </aside></div></main>`, "Aujourd'hui");
  dessiner();
};
routes.seance = () => ecranSeance();

// ── Bibliothèque ─────────────────────────────────────────────
const B = { langue: 'es', q: '', type: '', statut: '' };
routes.bibliotheque = async (code) => {
  const concepts = await api('GET', 'concepts');
  const par = Object.fromEntries(concepts.map((c) => [c.code, c]));
  if (code && par[code]) { if (B.code !== code) Object.assign(B, { type: '', statut: '' }); B.code = code; B.langue = par[code].langue; }
  if (!par[B.code] || par[B.code].langue !== B.langue) B.code = concepts.find((c) => c.langue === B.langue)?.code;
  const c = par[B.code];
  const exercices = c ? await api('GET', `exercices?concept=${enc(c.code)}`) : [];
  let edition = false;
  const ouvrir = (x) => panneau({ exercice: x, apres: router });
  const v = {
    acts: {
      q: (x) => { B.q = x; dessiner(); }, langue: (x) => { B.langue = x; aller(`#/bibliotheque/${enc(concepts.find((y) => y.langue === x)?.code || '')}`); },
      concept: (el) => aller(`#/bibliotheque/${enc(el.dataset.code)}`), type: (x) => { B.type = x; dessiner(); }, statut: (x) => { B.statut = x; dessiner(); },
      editer: () => { edition = true; dessiner(); document.getElementById('fiche').focus(); },
      fiche: async (x) => { await api('PATCH', `concepts/${enc(c.code)}`, { fiche: x }); c.fiche = x; toast('Règle enregistrée.'); },
      ouvrir: (el) => ouvrir(exercices.find((x) => x.id === +el.dataset.id)), importer: () => importerFichier(router),
      ajouter: () => panneau({ concept: c.code, apres: router }), generer: () => generer(c, router),
      nouveau: () => nouveauConcept(B.langue, [...new Set(concepts.map((x) => x.categorie))], (x) => aller(`#/bibliotheque/${enc(x)}`)),
    },
    touche(e) {
      if (ctrl(e, 'g') && c) { generer(c, router); return true; }
      if (ctrl(e, 'n') && c) { panneau({ concept: c.code, apres: router }); return true; }
      if (e.key === 'Enter' && e.target.id === 'recherche') { const x = trouves()[0]; if (x) aller(`#/bibliotheque/${enc(x.code)}`); return true; }
    },
  };
  const trouves = () => B.q.trim() ? chercher(concepts.filter((x) => x.langue === B.langue), B.q).map((x) => x.c) : concepts.filter((x) => x.langue === B.langue);
  const dessiner = () => {
    const lignes = exercices.filter((x) => (!B.type || x.type === B.type) && (!B.statut ? x.statut !== 'archive' : x.statut === B.statut));
    const cats = [...new Set(trouves().map((x) => x.categorie))];
    const etat = (x) => x.code === B.code ? ['on', '(sélectionné)'] : x.acquis ? ['ok', '(maîtrisé)'] : ['', x.vu ? '(en cours)' : '(nouveau)'];
    montrer(v, html`${barreHaut('#/bibliotheque')}<main class="biblio">
      <aside class="volet up">
        <div class="avec-icone">${ico('loupe')}<input id="recherche" type="search" class="champ" style="padding-right:56px" aria-label="Rechercher un concept" placeholder="Rechercher" value="${B.q}" data-input="q" autocomplete="off">${kbd('Ctrl K')}</div>
        ${seg('langue', [['es', 'Espagnol'], ['en', 'Anglais']], B.langue, 'Langue', 'etale')}
        <nav aria-label="Concepts" data-defil="concepts">${cats.map((k) => html`<div class="col g2"><h2 class="section">${k}</h2>${trouves().filter((x) => x.categorie === k).map((x) => { const [d, t] = etat(x); return html`<button type="button" class="item ${x.code === B.code ? 'on' : ''}" ${raw(x.code === B.code ? 'aria-current="page"' : '')} data-act="concept" data-code="${x.code}"><span class="dot ${d}"></span><span class="nom f1 tronque" title="${x.titre}">${x.titre}</span><span class="vh">${t}</span></button>`; })}</div>`)}
          ${!cats.length && html`<p class="cap" style="padding:0 8px">Aucun concept trouvé.</p>`}</nav>
        <button type="button" class="btn f" style="justify-content:flex-start" data-act="nouveau">${ico('plus')}Nouveau concept</button>
      </aside>
      ${c && html`<div class="fiche-concept">
        <div class="row wrap g16 up" style="--i:1"><div class="col g4" style="flex:1 1 240px"><div class="row g8"><h1>${c.titre}</h1>${pill(c.langue)}</div><span class="cap">${c.categorie}</span></div>
          <div class="row wrap g8"><button type="button" class="btn f" data-act="importer">${ico('importer')}Importer</button><button type="button" class="btn" data-act="ajouter">${ico('plus')}Ajouter${kbd('Ctrl N')}</button><button type="button" class="btn p" data-act="generer">Générer des exercices${kbd('Ctrl G')}</button></div></div>
        <section class="carte col g8 up" style="--i:2"><div class="row g8"><h2 class="section f1">Règle</h2><span class="cap row g4">${ico('crayon', 14)}Cliquer pour modifier</span></div>
          ${edition ? html`<textarea class="champ editable" id="fiche" rows="3" aria-label="Règle de ${c.titre}" data-change="fiche">${c.fiche}</textarea>`
    : html`<button type="button" class="champ editable" data-act="editer" aria-label="Modifier la règle de ${c.titre}">${c.fiche ? fiche(c.fiche) : 'Écrire la règle en trois lignes.'}</button>`}</section>
        <div class="row wrap up" style="--i:3;gap:48px;padding:0 4px;align-items:flex-start">
          <div class="chiffre"><span class="cap">Maîtrise</span><b>${c.vu ? `${c.maitrise} %` : '—'}</b>${barre(c.maitrise, 'Maîtrise')}</div>
          <div class="chiffre"><span class="cap">Réservoir</span><b>${c.non_vus} <small>${c.non_vus > 1 ? 'non vus' : 'non vu'}</small></b></div>
          <div class="chiffre"><span class="cap">Prochaine révision</span><b>${dans(c.echeance)}</b></div></div>
        ${c.voisins.length > 0 && html`<section class="col g12 up" style="--i:4;padding:0 4px"><h2 class="section">Concepts voisins</h2><div class="row wrap g8">${c.voisins.map((x) => html`<button type="button" class="chip" data-act="concept" data-code="${x}">${pill(par[x].langue)}${par[x].titre}</button>`)}</div></section>`}
        <section class="col g8 up" style="--i:5"><div class="row wrap g4" style="padding:0 4px"><h2 class="section f1">Exercices · ${lignes.length}</h2>
          <label class="filtre survol">Type ${select('type', [['', 'Tous'], ...Object.entries(TYPES)], B.type, 'id="f-type"')}${ico('bas', 14)}</label>
          <label class="filtre survol">Statut ${select('statut', [['', 'Tous'], ...Object.entries(STATUTS)], B.statut, 'id="f-statut"')}${ico('bas', 14)}</label></div>
          <div class="table"><div><div class="ligne" aria-hidden="true"><span>Type</span><span>Énoncé</span><span>Statut</span><span>Vu</span></div>
          <ul>${lignes.map((x) => html`<li><button type="button" class="ligne survol" data-act="ouvrir" data-id="${x.id}"><span style="color:var(--text-2)">${TYPES[x.type]}</span><span class="tronque">${x.enonce.replace(/\{\{\d+\}\}/g, '___')}</span><span><span class="pill ${x.statut}">${STATUTS[x.statut]}</span></span><span class="cap">${ilya(x.vu)}</span></button></li>`)}</ul>
          ${!lignes.length && html`<p style="padding:24px 12px;font-size:14px;color:var(--text-2)">Aucun exercice pour ces filtres.</p>`}</div></div></section>
      </div>`}</main>`, 'Bibliothèque');
  };
  dessiner();
  if (focusRecherche) { focusRecherche = false; document.getElementById('recherche').focus(); }
};

// ── File de validation ───────────────────────────────────────
const SOURCES = { ia: 'IA', mcp: 'MCP', import: 'Import', theme: 'Thème corrigé', manuel: 'Manuel' };
const V = { src: null, cur: null, total: 0 };
routes.validation = async () => {
  let attente, par;
  const charger = async () => {
    [attente, par] = await Promise.all([api('GET', 'exercices?statut=a_valider'), api('GET', 'concepts').then((l) => Object.fromEntries(l.map((c) => [c.code, c])))]);
    V.total = Math.max(attente.length, V.depart === location.hash ? V.total : 0);
    V.depart = location.hash;
  };
  await charger();
  const compte = (s) => attente.filter((x) => x.source === s).length;
  const etat = () => {
    if (!V.src || !compte(V.src)) V.src = Object.keys(SOURCES).find(compte) || 'ia';
    const l = attente.filter((x) => x.source === V.src), i = Math.max(0, l.findIndex((x) => x.id === V.cur));
    V.cur = l[i]?.id ?? null;
    return { l, i, x: l[i] };
  };
  const sortir = async (ids, statut) => {
    const { i } = etat();
    if (statut) await api('POST', 'exercices/statut', { ids, statut }); else for (const id of ids) await api('DELETE', `exercices/${id}`);
    attente = attente.filter((x) => !ids.includes(x.id));
    const l = attente.filter((x) => x.source === V.src);
    V.cur = l[Math.min(i, l.length - 1)]?.id ?? null;
    dessiner();
  };
  let occupe = false;
  const unSeul = (f) => async () => { const { x } = etat(); if (!x || occupe) return; occupe = true; try { await f(x); } finally { occupe = false; } };
  const accepter = unSeul((x) => sortir([x.id], 'actif')), supprimer = unSeul((x) => sortir([x.id]));
  const editer = unSeul((x) => panneau({ exercice: x, apres: async () => { await charger(); dessiner(); } }));
  const bouger = (d) => { const { l, i } = etat(); V.cur = l[Math.max(0, Math.min(l.length - 1, i + d))]?.id ?? null; dessiner(); document.querySelector('.item.haut.on')?.scrollIntoView({ block: 'nearest' }); };
  const quitter = () => { V.depart = null; aller('#/'); };
  const v = {
    acts: {
      quitter, accepter, supprimer, editer, src: (el) => { V.src = el.dataset.src; V.cur = null; dessiner(); }, cur: (el) => { V.cur = +el.dataset.id; dessiner(); },
      lot: () => { const { l } = etat(); if (confirm(`Accepter ${pl(l.length, 'exercice')} sans les relire ?`)) sortir(l.map((x) => x.id), 'actif'); },
    },
    touche(e) {
      if (e.key === 'Escape') { quitter(); return true; }
      if (e.ctrlKey || e.altKey || saisie(e)) return false;
      const f = { a: accepter, s: supprimer, e: editer, arrowdown: () => bouger(1), arrowup: () => bouger(-1) }[e.key.toLowerCase()];
      if (f && !e.repeat) { f(); return true; }
    },
  };
  const bloc = (t, contenu) => html`<div class="creux col g6"><h3 class="section">${t}</h3>${contenu}</div>`;
  const dessiner = () => {
    const { l, x } = etat(), fait = V.total - attente.length;
    montrer(v, html`<div class="plein">
      <header class="top prog"><button type="button" class="btn f" data-act="quitter">${ico('gauche')}Accueil${kbd('Échap')}</button>
        <span class="barre" role="progressbar" aria-label="Progression de la validation" aria-valuemin="0" aria-valuemax="${V.total}" aria-valuenow="${fait}"><span style="--v:${V.total ? Math.round(100 * fait / V.total) : 0}%"></span></span>
        <span class="cap num">${attente.length ? pl(attente.length, 'restant') : 'Terminé'}</span></header>
      <main class="file">
        <aside class="volet up" data-defil="file"><div class="col g2"><h2 class="section">Sources</h2>${['ia', 'mcp', 'import', 'theme', ...(compte('manuel') ? ['manuel'] : [])].map((s) => { const n = compte(s), on = s === V.src && n > 0; return html`<button type="button" id="src-${s}" class="item ${on ? 'on' : ''}" aria-pressed="${on}" ${raw(n ? '' : 'disabled')} data-act="src" data-src="${s}"><span class="dot ${on ? 'on' : 'rien'}"></span><span class="nom f1">${SOURCES[s]}</span><span class="num" style="font-size:13px">${n}</span></button>`; })}</div>
          ${l.length > 0 && html`<div class="col g2"><h2 class="section">En attente · ${l.length}</h2>${l.map((y) => { const on = y.id === V.cur; return html`<button type="button" id="att-${y.id}" class="item haut ${on ? 'on' : ''}" aria-current="${on}" data-act="cur" data-id="${y.id}"><span class="dot ${on ? 'on' : 'rien'}"></span><span class="f1 col g4"><span class="tronque">${y.enonce.replace(/\{\{\d+\}\}/g, '___')}</span><span class="row g6">${pill(y.concepts[0].slice(0, 2))}<span class="cap tronque" style="font-size:12px">${par[y.concepts[0]]?.titre}</span></span></span></button>`; })}</div>`}</aside>
        ${x ? html`<div class="apercu"><div><span class="cap">Aperçu en séance · ${SOURCES[x.source]}</span>
          <section class="carte lg col g24 up" style="--i:1"><div class="col g12"><div class="meta">${pill(x.concepts[0].slice(0, 2))}<span>·</span><span>${par[x.concepts[0]]?.titre}</span><span>·</span><span>${TYPES[x.type]}</span></div>
            <div class="col g4"><p class="cap">${x.consigne}</p><p class="enonce">${enonce(x.enonce)}</p></div></div>
            <div class="champ reponse" style="min-height:64px;color:var(--text-3)" aria-hidden="true">Ta réponse…</div></section>
          <div class="col g8 up" style="--i:2">
            ${x.type === 'trous' ? x.reponses.map((r, i) => bloc(x.reponses.length > 1 ? `Réponses acceptées, blanc ${i + 1}` : 'Réponses acceptées', puces(r))) : bloc('Réponses acceptées', puces(x.reponses))}
            ${x.distracteurs.length > 0 && bloc('Distracteurs', puces(x.distracteurs))}${x.indice && bloc('Indice', html`<p>${x.indice}</p>`)}${x.explication && bloc('Explication', html`<p>${x.explication}</p>`)}</div></div></div>`
    : html`<div class="vide"><div class="up" style="--i:1"><span class="icone">${ico('boite', 28)}</span><div class="col g4"><h1>Rien à valider</h1><p class="cap">Les exercices générés ou importés arrivent ici avant d'entrer en séance.</p></div><button type="button" class="btn" data-act="quitter">Retour à l'accueil${kbd('Échap')}</button></div></div>`}
      </main>
      ${x && html`<footer class="dock large"><div><button type="button" class="lien cap" data-act="lot">Tout accepter pour cette source (${l.length})</button><span class="f1"></span>
        <button type="button" class="btn f" data-act="supprimer">Supprimer${kbd('S')}</button><button type="button" class="btn" data-act="editer">Éditer${kbd('E')}</button><button type="button" class="btn p" style="margin:0" data-act="accepter">Accepter${kbd('A')}</button></div></footer>`}
    </div>`, 'File de validation');
  };
  dessiner();
};
const puces = (l) => html`<ul style="list-style:disc;padding-left:20px">${l.map((a) => html`<li>${a}</li>`)}</ul>`;

// ── Statistiques ─────────────────────────────────────────────
const P = { periode: '7', langue: 'tout' };
let vueStats;
routes.stats = async () => {
  const d = await api('GET', `stats?periode=${P.periode}&langue=${P.langue}`);
  const maj = (k) => (x) => { P[k] = x; router(); };
  if (!vueStats || !document.querySelector('.kpis')) vueStats = { acts: { periode: maj('periode'), langue: maj('langue') } };
  const titreTemps = { 7: 'Temps cette semaine', 30: 'Temps sur 30 jours', tout: 'Temps total' }[P.periode];
  const kpis = [[titreTemps, duree(d.secondes)], ['Exercices faits', d.faits.toLocaleString('fr-FR')], ['Réussite', d.reussite === null ? '—' : `${d.reussite} %`], ['Série', pl(d.serie, 'jour')]];
  const cats = [...new Set(d.concepts.map((c) => c.categorie))];
  const max = Math.max(3600, ...d.temps), pas = Math.ceil(max / 3600 / 3) * 3600, haut = pas * Math.ceil(max / pas), y = (s) => 100 - 100 * s / haut;
  const tendance = (w) => { const s = (a) => a.reduce((p, q) => p + q, 0), e = s(w.slice(-3)) - s(w.slice(0, 3)); return e < 0 ? 'en baisse' : e > 0 ? 'en hausse' : 'stable'; };
  montrer(vueStats, html`${barreHaut('#/stats')}<main class="page" style="gap:24px">
    <div class="row wrap g16 up" style="margin-bottom:8px"><h1 class="f1">Statistiques</h1>${seg('periode', [['7', '7 jours'], ['30', '30 jours'], ['tout', 'Tout']], P.periode, 'Période')}${seg('langue', [['tout', 'Tout'], ['en', 'EN'], ['es', 'ES']], P.langue, 'Langue')}</div>
    <div class="kpis">${kpis.map(([l, x], i) => html`<div class="carte col g4 up" style="--i:${i + 1};padding:20px 24px"><span class="cap">${l}</span><b>${x}</b></div>`)}</div>
    <section class="carte col g20 up" style="--i:5"><h2 class="section">Maîtrise par concept</h2>
      <div class="row wrap" style="gap:32px 48px;align-items:flex-start">${cats.map((k) => html`<div class="col g8"><h3 style="font-size:13px;font-weight:500">${k}</h3><ul class="chaleur">${d.concepts.filter((c) => c.categorie === k).map((c) => html`<li><a class="cell" style="display:block;--v:${c.maitrise}%" href="#/bibliotheque/${enc(c.code)}" aria-label="${c.titre} (${c.langue.toUpperCase()}), maîtrise ${c.maitrise} %, révisé ${ilya(c.vu)}"><span class="bulle" aria-hidden="true"><span class="row g6 fort">${pill(c.langue)}${c.titre}</span><span style="display:block">Maîtrise ${c.maitrise} %</span><span style="display:block;color:var(--text-2)">Révisé ${ilya(c.vu)}</span></span></a></li>`)}</ul></div>`)}</div>
      <div class="row g8 cap"><span>0 %</span><span aria-hidden="true" style="width:160px;height:8px;border-radius:99px;background:linear-gradient(90deg,var(--inset),var(--success))"></span><span>100 %</span><span style="margin-left:8px">Survoler un carré pour le détail</span></div></section>
    <div class="row wrap g24" style="align-items:stretch">
      <section class="carte col g16 up" style="--i:6;flex:1 1 380px"><h2 class="section">Réussite par type</h2>${d.types.length ? html`<ul class="col g12">${d.types.map((t) => html`<li class="li-type"><span>${t.nom}</span><span class="barre gris" aria-hidden="true"><span style="--v:${t.p}%"></span></span><span class="num" style="text-align:right;font-weight:500">${t.p} %</span></li>`)}</ul>` : html`<p class="cap">Aucune réponse sur la période.</p>`}</section>
      <section class="carte col g16 up" style="--i:7;flex:1 1 380px"><div class="row g8"><h2 class="section f1">Fautes les plus fréquentes</h2><span class="cap">8 dernières semaines</span></div>${d.fautes.length ? html`<ul class="col g4">${d.fautes.map((f) => { const m = Math.max(...f.semaines, 1), t = tendance(f.semaines); return html`<li class="li-faute"><span class="row g8"><span class="code tronque">${f.nom}</span><span class="cap" style="font-size:12px;flex:none">${f.langues}</span></span><span class="num fort" style="text-align:right">${f.n}</span><svg role="img" aria-label="${f.nom} : ${pl(f.n, 'faute')}, ${t}" width="72" height="24" viewBox="0 0 72 24" fill="none"><polyline points="${f.semaines.map((s, i) => `${(2 + i * 68 / 7).toFixed(1)},${(22 - s / m * 20).toFixed(1)}`).join(' ')}" stroke="var(--text-2)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg><span class="cap" style="font-size:12px;text-align:right">${t}</span></li>`; })}</ul>` : html`<p class="cap">Aucune faute sur la période.</p>`}</section></div>
    <section class="carte col up" style="--i:8"><div class="row g8"><h2 class="section f1">Temps par semaine</h2><span class="cap">12 dernières semaines</span></div>
      <div class="graphe" role="img" aria-label="Temps de travail par semaine sur 12 semaines : ${duree(d.temps[11])} cette semaine, maximum ${duree(Math.max(...d.temps))}.">
        ${Array.from({ length: haut / pas + 1 }, (_, i) => html`<i style="top:${y(i * pas)}%"><span>${i * pas / 3600} h</span></i>`)}
        <svg aria-hidden="true" viewBox="0 0 1000 200" preserveAspectRatio="none"><polyline points="${d.temps.map((s, i) => `${(i * 1000 / 11).toFixed(1)},${(y(s) * 2).toFixed(1)}`).join(' ')}" fill="none" stroke="var(--text)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></svg>
        <span class="pt" style="top:${y(d.temps[11])}%"></span><span class="val" style="top:${y(d.temps[11])}%">${duree(d.temps[11])}</span></div>
      <div class="axe" aria-hidden="true">${d.temps.map((_, i) => html`<span>${i < 11 ? `S-${11 - i}` : 'Cette sem.'}</span>`)}</div></section>
  </main>`, 'Statistiques');
};

// ── Réglages ─────────────────────────────────────────────────
routes.reglages = async () => {
  const r = await api('GET', 'reglages');
  const regler = (k, conv = String) => async (x) => {
    await api('PATCH', 'reglages', { [k]: conv(x) });
    if (k === 'theme') document.documentElement.dataset.theme = x;
    toast('Réglage enregistré.');
  };
  const ligne = (titre, aide, controle) => html`<div class="reglage"><div class="col" style="flex:1 1 280px"><span style="font-weight:500">${titre}</span><span class="cap">${aide}</span></div>${controle}</div>`;
  const cle = async (x) => { await api('PATCH', 'reglages', { cle_api: x }); toast(x.trim() ? 'Clé enregistrée.' : 'Clé effacée.'); router(); };
  const v = { acts: { ...actsMaj, cle, accents: regler('accents'), duree: regler('duree', Number), nouveaux: regler('nouveaux', Number), theme: regler('theme'), importer: () => importerFichier(() => {}) } };
  montrer(v, html`${barreHaut('#/reglages')}<main class="page" style="max-width:768px;gap:24px"><h1 class="up">Réglages</h1>
    <section class="carte col g16 up" style="--i:1"><h2 class="section">Révision</h2>
      ${ligne('Accent espagnol oublié', 'En conjugaison, il compte toujours faux.', seg('accents', [['faux', 'Faux'], ['demi', 'Demi-faute']], r.accents, 'Accent oublié'))}
      ${ligne('Durée de séance', 'Environ 40 secondes par exercice.', seg('duree', [[10, '10 min'], [15, '15 min'], [25, '25 min']], r.duree, 'Durée de séance'))}
      ${ligne('Nouveaux concepts par jour', 'Ajoutés après les concepts à revoir.', seg('nouveaux', [0, 1, 2, 3, 4, 5].map((n) => [n, n]), r.nouveaux, 'Nouveaux concepts par jour'))}</section>
    <section class="carte col g16 up" style="--i:2"><h2 class="section">Claude</h2>
      ${ligne("Clé d'API Anthropic", r.ia ? 'Active : les réponses libres non reconnues sont jugées par Claude, et « Générer » écrit les exercices lui-même.' : 'Facultative. Sans clé, tu tranches toi-même les réponses « à vérifier ».', html`<input type="password" class="champ" style="max-width:260px" data-change="cle" aria-label="Clé d'API Anthropic" placeholder="${r.cle_api ? '•••••••• (enregistrée)' : 'sk-ant-…'}" autocomplete="off">`)}</section>
    <section class="carte col g16 up" style="--i:2"><h2 class="section">Apparence</h2>${ligne('Thème', '', seg('theme', [['auto', 'Système'], ['clair', 'Clair'], ['sombre', 'Sombre']], r.theme, 'Thème'))}</section>
    <section class="carte col g16 up" style="--i:3"><h2 class="section">Données</h2>
      ${ligne('Importer des exercices', 'Fichier JSON. Les doublons sont rejetés et signalés.', html`<button type="button" class="btn" data-act="importer">${ico('importer')}Importer</button>`)}
      ${ligne('Exporter toute la base', 'Concepts, exercices, tentatives et réglages, en un fichier JSON.', html`<a class="btn" href="/api/export" download>Exporter</a>`)}
      ${ligne('Copies de sécurité', 'Une par jour d\'utilisation, les 7 dernières sont gardées.', html`<span class="cap num">${pl(r.sauvegardes, 'copie')}</span>`)}
      <p class="cap">Dossier des données : <span class="mono">${r.dossier}</span></p></section>
    <section class="carte col g16 up" style="--i:4"><h2 class="section">À propos</h2>
      ${ligne(`Gram-Gen ${r.version}`, 'Le numéro de la dernière version est lu sur GitHub au démarrage ; rien n\'est envoyé.', html`<button type="button" class="btn" data-act="verifier">Vérifier les mises à jour</button>`)}
      ${ligneMaj()}</section>
  </main>`, 'Réglages');
};

router();
setTimeout(surveiller, 1500);
