// Fenêtres : ajout rapide / édition, choix d'un concept, générer, importer, nouveau concept.
import { html, raw, ico, kbd, pill, pl, seg, select, enonce, TYPES, CONSIGNES, STATUTS, api, toast, fenetre, aller, ctrl, saisie } from './base.js';

const fermerX = html`<button type="button" class="btn f ico" data-act="fermer" aria-label="Fermer" style="margin:-8px -8px 0 0">${ico('croix', 20)}</button>`;

// ponytail: recherche floue par sous-suite, à remplacer par un vrai score au-delà de quelques centaines de concepts
function floue(nom, q) {
  const s = (t) => t.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
  const n = s(nom), cherche = s(q).replace(/\s/g, ''), pos = [];
  for (let j = 0, i = 0; j < n.length && i < cherche.length; j++) if (n[j] === cherche[i]) { pos.push(j); i++; }
  if (pos.length < cherche.length) return null;
  return { pos: n.length === nom.length ? pos : [], etendue: pos.length ? pos.at(-1) - pos[0] : 0 };
}
export const chercher = (concepts, q) => concepts.map((c) => ({ c, m: floue(c.titre, q) })).filter((x) => x.m).sort((a, b) => a.m.etendue - b.m.etendue);
const surligne = (nom, pos) => [...nom].map((l, i) => pos.includes(i) ? html`<mark>${l}</mark>` : l);

/** Bilan d'un import, avec le chemin vers la file de validation. */
function bilanImport(b, apres) {
  const f = fenetre({
    nom: 'Bilan de l\'import', apres,
    acts: { fermer: () => f.fermer(), valider: () => { f.apres = null; f.fermer(); aller('#/validation'); } },
    touche: (e) => { if (e.key === 'Enter' && b.ajoutes && !e.target.closest('button')) { f.apres = null; f.fermer(); aller('#/validation'); return true; } },
    rendu: () => html`<div class="row g12" style="align-items:flex-start"><h2 class="h1 f1">${pl(b.ajoutes, 'exercice ajouté', 'exercices ajoutés')}</h2>${fermerX}</div>
      <div class="col g16" style="overflow-y:auto">
      ${b.ajoutes > 0 && html`<p class="cap">Ils attendent dans « À valider ».</p>`}
      ${b.doublons.length > 0 && html`<div class="col g4"><h3 class="section">${pl(b.doublons.length, 'doublon ignoré', 'doublons ignorés')}</h3><ul class="cap">${b.doublons.slice(0, 20).map((d) => html`<li>${d}</li>`)}</ul></div>`}
      ${b.erreurs.length > 0 && html`<div class="col g4"><h3 class="section">${pl(b.erreurs.length, 'erreur')}</h3><ul class="cap">${b.erreurs.slice(0, 20).map((d) => html`<li>N° ${d.n} — ${d.message}</li>`)}</ul></div>`}
      </div>
      <div class="row g8" style="justify-content:flex-end"><button type="button" class="btn f" data-act="fermer">Fermer${kbd('Échap')}</button>${b.ajoutes > 0 && html`<button type="button" class="btn p" data-act="valider" data-focus>Valider maintenant${kbd('Entrée')}</button>`}</div>`,
  });
}
/** Texte collé → JSON, en tolérant la clôture ```json des assistants. */
function lireJson(t) {
  try { return JSON.parse(t.trim().replace(/^```(?:json)?\s*/i, '').replace(/```$/, '')); } catch { throw new Error('Ce texte n\'est pas du JSON valide.'); }
}
export function importerFichier(apres) {
  const i = document.createElement('input');
  i.type = 'file';
  i.accept = '.json,application/json';
  i.onchange = async () => bilanImport(await api('POST', 'import', { donnees: lireJson(await i.files[0].text()) }), apres);
  i.click();
}

export async function choisirConcept(titre, sous, suite) {
  const concepts = (await api('GET', 'concepts')).filter((c) => c.actifs);
  let q = '', actif = 0;
  const visibles = () => chercher(concepts, q).map((x) => x.c);
  const prendre = (code) => { f.fermer(); suite(code); };
  const f = fenetre({
    nom: titre,
    acts: { fermer: () => f.fermer(), q: (v) => { q = v; actif = 0; f.maj(); }, prendre: (el) => prendre(el.dataset.code) },
    touche(e) {
      const l = visibles();
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { actif = Math.max(0, Math.min(l.length - 1, actif + (e.key === 'ArrowDown' ? 1 : -1))); f.maj(); f.el.querySelector('.item.on')?.scrollIntoView({ block: 'nearest' }); return true; }
      if (e.key === 'Enter' && saisie(e) && l[actif]) { prendre(l[actif].code); return true; }
    },
    rendu: () => html`<div class="row g12" style="align-items:flex-start"><div class="f1 col g2"><h2 class="h1">${titre}</h2><span class="cap">${sous}</span></div>${fermerX}</div>
      <div class="avec-icone">${ico('loupe')}<input id="cherche-concept" data-focus type="search" class="champ" data-input="q" value="${q}" placeholder="Rechercher un concept" aria-label="Rechercher un concept" autocomplete="off"></div>
      <div class="choix col g2" data-defil="choix">${visibles().map((c, i) => html`<button type="button" class="item ${i === actif ? 'on' : ''}" style="flex:none" data-act="prendre" data-code="${c.code}">${pill(c.langue)}<span class="nom f1 tronque">${c.titre}</span><span class="cap num">${c.vu ? c.maitrise + ' %' : 'nouveau'}</span></button>`)}</div>`,
  });
}

/** Générer : prépare le prompt, puis importe la réponse de l'assistant. Aucun appel IA dans le MVP. */
export function generer(concept, apres) {
  let nombre = 10, difficulte = 2, types = new Set(['trous', 'qcm', 'choix', 'theme']), prompt = null, colle = '', erreur = '';
  const copier = async () => {
    if (!types.size) return;
    prompt = (await api('POST', `concepts/${encodeURIComponent(concept.code)}/prompt`, { nombre, difficulte, types: [...types] })).prompt;
    let ok = true;
    try { await navigator.clipboard.writeText(prompt); } catch { ok = false; }
    f.maj();
    if (ok) toast('Prompt copié.'); else f.el.querySelector('#prompt')?.select();
    f.el.querySelector('#colle').focus();
  };
  const importer = async () => {
    try {
      const b = await api('POST', 'import', { donnees: lireJson(colle), source: 'ia' });
      f.fermer();
      bilanImport(b, apres);
    } catch (e) { erreur = e.message; f.maj(); }
  };
  const f = fenetre({
    nom: 'Générer des exercices',
    acts: {
      fermer: () => f.fermer(), copier, importer, nombre: (v) => { nombre = +v; }, difficulte: (v) => { difficulte = +v; },
      type: (v, el) => { types[v ? 'add' : 'delete'](el.value); f.maj(); }, colle: (v) => { colle = v; f.el.querySelector('#importer').disabled = !v.trim(); }, retour: () => { prompt = null; f.maj(); },
    },
    touche: (e) => { if (e.key === 'Enter' && !prompt && !e.target.closest('button')) { copier(); return true; } if (prompt && e.ctrlKey && e.key === 'Enter' && colle.trim()) { importer(); return true; } },
    rendu: () => html`<div class="row g12" style="align-items:flex-start"><div class="f1 col g2"><h2 class="h1">Générer des exercices</h2><span class="row g8 cap">${pill(concept.langue)}${concept.titre}</span></div>${fermerX}</div>
      ${prompt ? html`
        <div class="col g16" style="overflow-y:auto;margin:-4px;padding:4px">
        <p style="font-size:14px">Le prompt est dans le presse-papiers. Le coller dans Claude, puis coller ici sa réponse.</p>
        <details><summary class="lien row g4" style="display:inline-flex">Voir le prompt<span class="chev row">${ico('bas')}</span></summary><textarea id="prompt" class="champ mono" rows="8" readonly>${prompt}</textarea></details>
        <div class="col g8"><label class="lab" for="colle">Réponse de l'assistant</label><textarea id="colle" class="champ mono" rows="8" data-input="colle" placeholder="[ { &quot;concepts&quot;: … } ]">${colle}</textarea>${erreur && html`<span class="erreur" role="alert">${erreur}</span>`}<span class="cap">Les exercices arrivent dans « À valider ».</span></div>
        </div>
        <div class="row g8" style="justify-content:flex-end"><button type="button" class="btn f" data-act="retour">Retour</button><button type="button" class="btn p" id="importer" data-act="importer" ${raw(colle.trim() ? '' : 'disabled')}>Importer${kbd('Ctrl ↵')}</button></div>`
      : html`
        <div class="col g8"><span class="lab">Nombre</span>${seg('nombre', [[5, '5'], [10, '10'], [20, '20']], nombre, 'Nombre')}</div>
        <fieldset class="col g8"><legend class="lab" style="padding-bottom:8px">Types</legend><div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px 16px">${Object.entries(TYPES).map(([k, l]) => html`<label class="coche"><input type="checkbox" id="t-${k}" value="${k}" data-change="type" ${raw(types.has(k) ? 'checked' : '')}>${l}</label>`)}</div></fieldset>
        <div class="col g8"><span class="lab">Difficulté</span>${seg('difficulte', [[1, '1'], [2, '2'], [3, '3']], difficulte, 'Difficulté')}</div>
        <div class="row g8" style="justify-content:flex-end"><button type="button" class="btn f" data-act="fermer">Annuler${kbd('Échap')}</button><button type="button" class="btn p" data-focus data-act="copier" ${raw(types.size ? '' : 'disabled')}>Copier le prompt${kbd('Entrée')}</button></div>`}`,
  });
}

export function nouveauConcept(langue, categories, apres) {
  const c = { langue, titre: '', categorie: '', fiche: '' };
  let erreur = '';
  const creer = async () => {
    try { const { code } = await api('POST', 'concepts', c); f.fermer(); apres(code); } catch (e) { erreur = e.message; f.maj(); }
  };
  const champ = (k) => (v) => { c[k] = v; };
  const f = fenetre({
    nom: 'Nouveau concept',
    acts: { fermer: () => f.fermer(), creer, langue: champ('langue'), titre: champ('titre'), categorie: champ('categorie'), fiche: champ('fiche') },
    touche: (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.target.tagName === 'INPUT')) { creer(); return true; } },
    rendu: () => html`<div class="row g12" style="align-items:flex-start"><h2 class="h1 f1">Nouveau concept</h2>${fermerX}</div>
      ${seg('langue', [['es', 'Espagnol'], ['en', 'Anglais']], c.langue, 'Langue')}
      <div class="col g8"><label class="lab" for="nc-titre">Titre</label><input id="nc-titre" data-focus class="champ" data-input="titre" value="${c.titre}"></div>
      <div class="col g8"><label class="lab" for="nc-cat">Catégorie</label><input id="nc-cat" class="champ" list="cats" data-input="categorie" value="${c.categorie}"><datalist id="cats">${categories.map((x) => html`<option value="${x}">`)}</datalist></div>
      <div class="col g8"><label class="lab" for="nc-fiche">Règle (3 lignes)</label><textarea id="nc-fiche" class="champ" rows="3" data-input="fiche">${c.fiche}</textarea></div>
      ${erreur && html`<span class="erreur" role="alert">${erreur}</span>`}
      <div class="row g8" style="justify-content:flex-end"><button type="button" class="btn f" data-act="fermer">Annuler${kbd('Échap')}</button><button type="button" class="btn p" data-act="creer">Créer${kbd('Entrée')}</button></div>`,
  });
}

// ── Ajout rapide / édition ───────────────────────────────────
/** Sans `exercice` : ajout. `apres()` est appelé après chaque enregistrement. */
export async function panneau({ exercice = null, concept = null, apres = () => {} } = {}) {
  const concepts = await api('GET', 'concepts');
  const par = Object.fromEntries(concepts.map((c) => [c.code, c]));
  const depart = exercice?.concepts[0] || concept;
  const e = {
    langue: depart ? par[depart].langue : localStorage.langue || 'es', concept: depart || null, q: depart ? par[depart].titre : '',
    type: exercice?.type || 'trous', enonce: exercice?.enonce || '', consigne: exercice?.consigne || '',
    reponses: exercice ? (exercice.type === 'trous' ? exercice.reponses.map((r) => [...r]) : [[...exercice.reponses]]) : [['']],
    distracteurs: exercice?.distracteurs.length ? [...exercice.distracteurs] : ['', '', ''],
    indice: exercice?.indice || '', explication: exercice?.explication || '', difficulte: exercice?.difficulte || 2, statut: exercice?.statut,
  };
  let actif = 0, doublon = null, erreur = '', liste = false, options = !!exercice;
  const choix = () => ['qcm', 'choix'].includes(e.type);
  const consigne = () => e.consigne || CONSIGNES[e.type].replace('{langue}', e.langue === 'es' ? 'espagnol' : 'anglais');
  const suggestions = () => liste && e.q.trim() ? chercher(concepts.filter((c) => c.langue === e.langue), e.q).slice(0, 5) : [];
  /** Une liste de réponses par blanc. */
  const ajuster = () => {
    const n = e.type === 'trous' ? Math.max(1, (e.enonce.match(/\{\{\d+\}\}/g) || []).length) : 1;
    while (e.reponses.length < n) e.reponses.push(['']);
    e.reponses.length = n;
    if (choix()) e.reponses = [[e.reponses[0][0] || '']];
  };
  const prendre = (c) => { e.concept = c.code; e.q = c.titre; liste = false; f.maj(); f.el.querySelector('#p-type').focus(); };

  async function enregistrer(continuer) {
    ajuster();
    const corps = {
      concepts: e.concept ? [e.concept, ...(exercice?.concepts.slice(1) || []).filter((c) => c !== e.concept)] : [],
      type: e.type, consigne: e.consigne, enonce: e.enonce, reponses: e.type === 'trous' ? e.reponses : e.reponses[0],
      distracteurs: choix() ? e.distracteurs : [], indice: e.indice, explication: e.explication, difficulte: e.difficulte,
      ...(exercice ? { statut: e.statut } : {}),
    };
    try {
      await (exercice ? api('PUT', `exercices/${exercice.id}`, corps) : api('POST', 'exercices', corps));
    } catch (err) {
      doublon = err.data.doublon || null;
      erreur = doublon ? '' : err.message;
      f.maj();
      return f.el.querySelector('[role=alert]')?.scrollIntoView({ block: 'nearest' });
    }
    localStorage.langue = e.langue;
    toast(exercice ? 'Exercice enregistré.' : 'Exercice ajouté.');
    f.apres = apres;   // à la fermeture : redessiner l'écran fermerait le panneau
    if (!continuer) return f.fermer();
    Object.assign(e, { enonce: '', reponses: [['']], distracteurs: ['', '', ''], indice: '', explication: '' });
    doublon = null; erreur = '';
    f.maj();
    f.el.querySelector('#p-enonce').focus();
  }
  async function supprimer() {
    if (!confirm('Supprimer cet exercice ?')) return;
    await api('DELETE', `exercices/${exercice.id}`);
    f.apres = apres;
    f.fermer();
    toast('Exercice supprimé.');
  }
  const rendreApercu = () => { const a = f.el.querySelector('#apercu'); if (a) a.innerHTML = apercu(); };

  const f = fenetre({
    nom: exercice ? 'Modifier l\'exercice' : 'Nouvel exercice', classe: 'panneau',
    acts: {
      fermer: () => f.fermer(), ajouter: () => enregistrer(false), continuer: () => enregistrer(true), supprimer,
      voir: async () => { const x = (await api('GET', 'exercices')).find((y) => y.id === doublon); f.fermer(); if (x) panneau({ exercice: x, apres }); },
      langue: (v) => { Object.assign(e, { langue: v, concept: null, q: '' }); f.maj(); },
      q: (v) => { Object.assign(e, { q: v, concept: null }); actif = 0; liste = true; f.maj(); },
      prendre: (el) => prendre(par[el.dataset.code]),
      type: (v) => { e.type = v; e.consigne = ''; ajuster(); f.maj(); },
      statut: (v) => { e.statut = v; },
      enonce: (v) => { const n = e.reponses.length; e.enonce = v; ajuster(); doublon = null; if (e.reponses.length !== n) f.maj(); else rendreApercu(); },
      consigne: (v) => { e.consigne = v; rendreApercu(); }, indice: (v) => { e.indice = v; }, explication: (v) => { e.explication = v; },
      difficulte: (v) => { e.difficulte = +v; },
      rep: (v, el) => { e.reponses[el.dataset.b][el.dataset.i] = v; }, dis: (v, el) => { e.distracteurs[el.dataset.i] = v; },
      plus: (el) => { const l = e.reponses[el.dataset.b]; l.push(''); f.maj(); f.el.querySelector(`#r-${el.dataset.b}-${l.length - 1}`).focus(); },
      moins: (el) => { e.reponses[el.dataset.b].splice(el.dataset.i, 1); f.maj(); },
      options: () => { options = !options; },
    },
    touche(ev) {
      if (ev.target.id === 'p-concept') {
        const l = suggestions();
        if (ev.key === 'Escape' && l.length) { liste = false; f.maj(); return true; }
        if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') { actif = Math.max(0, Math.min(l.length - 1, actif + (ev.key === 'ArrowDown' ? 1 : -1))); f.maj(); return true; }
        if ((ev.key === 'Enter' || ev.key === 'Tab') && !ev.ctrlKey && !ev.shiftKey && l[actif]) { prendre(l[actif].c); return true; }
      }
      if (ev.ctrlKey && ev.key === 'Enter') { enregistrer(!exercice); return true; }
      if (ev.key === 'Enter' && ev.target.tagName === 'INPUT' && ev.target.id !== 'p-concept') { enregistrer(false); return true; }
      return ctrl(ev, 'n');
    },
    rendu: () => html`
      <div class="tete"><h2 class="h1 f1">${exercice ? 'Modifier l\'exercice' : 'Nouvel exercice'}</h2><button type="button" class="btn f" data-act="fermer" aria-label="Fermer (Échap)" style="padding:0 8px 0 10px">${kbd('Échap')}${ico('croix', 20)}</button></div>
      <div class="corps" data-defil="panneau">
        <div class="col g8"><span class="lab">Langue</span>${seg('langue', [['en', 'EN'], ['es', 'ES']], e.langue, 'Langue')}</div>
        <div class="col g8" style="position:relative"><label class="lab" for="p-concept">Concept</label>
          <div class="avec-icone">${ico('loupe')}<input id="p-concept" ${raw(depart ? '' : 'data-focus')} type="text" role="combobox" aria-expanded="${suggestions().length > 0}" aria-controls="p-liste" aria-autocomplete="list" autocomplete="off" class="champ" placeholder="Rechercher un concept" value="${e.q}" data-input="q"></div>
          ${suggestions().length > 0 && html`<ul id="p-liste" class="liste" role="listbox" aria-label="Suggestions">${suggestions().map(({ c, m }, i) => html`<li role="option" aria-selected="${i === actif}" data-act="prendre" data-code="${c.code}">${pill(c.langue)}<span class="f1">${surligne(c.titre, m.pos)}</span><span class="cap" style="font-size:12px">${c.categorie}</span></li>`)}</ul>`}
        </div>
        <div class="col g8"><label class="lab" for="p-type">Type</label><div class="select">${select('type', Object.entries(TYPES), e.type, 'id="p-type" class="champ"')}${ico('bas')}</div></div>
        <div class="col g8"><label class="lab" for="p-enonce">Énoncé</label><textarea id="p-enonce" ${raw(depart ? 'data-focus' : '')} class="champ" rows="4" style="min-height:112px;padding:12px;border-radius:12px;font-size:16px" data-input="enonce" aria-describedby="p-aide">${e.enonce}</textarea>
          <span class="cap" id="p-aide">${e.type === 'trous' ? html`Marque les blancs avec <span class="mono">{{1}}</span>, <span class="mono">{{2}}</span>…` : choix() ? html`Marque le blanc avec <span class="mono">___</span>.` : e.type === 'theme' ? 'La phrase française, de 8 à 20 mots.' : ''}</span></div>
        ${e.reponses.map((l, b) => html`<fieldset class="col g8"><legend class="lab" style="padding-bottom:8px">${choix() ? 'Bonne réponse' : e.reponses.length > 1 ? `Réponses acceptées, blanc ${b + 1}` : 'Réponses acceptées'}</legend>
          ${l.map((v, i) => html`<div class="row g4"><input id="r-${b}-${i}" class="champ f1" value="${v}" data-input="rep" data-b="${b}" data-i="${i}" aria-label="Réponse ${i + 1}" lang="${e.langue}" autocomplete="off">${l.length > 1 && html`<button type="button" class="btn f ico" data-act="moins" data-b="${b}" data-i="${i}" aria-label="Supprimer la réponse ${i + 1}">${ico('croix')}</button>`}</div>`)}
          ${!choix() && html`<button type="button" class="lien" style="align-self:flex-start" data-act="plus" data-b="${b}">+ Ajouter une variante</button>`}</fieldset>`)}
        ${choix() && html`<fieldset class="col g8"><legend class="lab" style="padding-bottom:8px">Distracteurs</legend>${[0, 1, 2].map((i) => html`<input id="d-${i}" class="champ" value="${e.distracteurs[i] || ''}" data-input="dis" data-i="${i}" aria-label="Distracteur ${i + 1}" lang="${e.langue}" autocomplete="off">`)}</fieldset>`}
        <details ${raw(options ? 'open' : '')}><summary class="row g4" style="display:inline-flex;min-height:32px;font-size:14px;font-weight:500" data-act="options">Plus d'options<span class="chev row">${ico('bas')}</span></summary>
          <div class="col g16" style="padding-top:12px">
            ${exercice && html`<div class="col g8"><label class="lab" for="p-statut">Statut</label><div class="select">${select('statut', Object.entries(STATUTS), e.statut, 'id="p-statut" class="champ"')}${ico('bas')}</div></div>`}
            <div class="col g8"><label class="lab" for="p-consigne">Consigne</label><input id="p-consigne" class="champ" value="${e.consigne}" placeholder="${consigne()}" data-input="consigne"></div>
            <div class="col g8"><label class="lab" for="p-indice">Indice</label><input id="p-indice" class="champ" value="${e.indice}" data-input="indice"></div>
            <div class="col g8"><label class="lab" for="p-expl">Explication</label><textarea id="p-expl" class="champ" rows="2" data-input="explication">${e.explication}</textarea></div>
            <div class="col g8"><span class="lab">Difficulté</span>${seg('difficulte', [[1, '1'], [2, '2'], [3, '3']], e.difficulte, 'Difficulté')}</div>
          </div></details>
        <section class="creux col g12"><h3 class="section">Aperçu en séance</h3><div id="apercu">${apercu()}</div></section>
      </div>
      <div class="pied">
        ${doublon && html`<div class="bandeau faux mince" role="alert">${ico('faux', 18)}<span class="f1">Un exercice presque identique existe déjà.</span><button type="button" class="lien" data-act="voir">Voir</button></div>`}
        ${erreur && html`<div class="bandeau faux mince" role="alert">${ico('faux', 18)}<span class="f1">${erreur}</span></div>`}
        <div class="row g8">${exercice ? html`<button type="button" class="btn f" style="margin-left:-12px" data-act="supprimer">Supprimer</button><span class="f1"></span><button type="button" class="btn p" data-act="ajouter">Enregistrer${kbd('Ctrl ↵')}</button>`
    : html`<button type="button" class="btn f" style="margin-left:-12px" data-act="fermer">Annuler</button><span class="f1"></span><button type="button" class="btn" data-act="continuer">Ajouter et continuer${kbd('Ctrl ↵')}</button><button type="button" class="btn p" data-act="ajouter">Ajouter</button>`}</div>
      </div>`,
  });
  function apercu() {
    return html`<div class="col" style="gap:10px;background:var(--surface);border-radius:12px;padding:16px;box-shadow:var(--shadow-sm)">
      <div class="meta" style="gap:6px;font-size:12px">${pill(e.langue)}<span>·</span><span>${e.concept ? par[e.concept].titre : 'Concept à choisir'}</span><span>·</span><span>${TYPES[e.type]}</span></div>
      <p class="cap" style="font-size:12px">${consigne()}</p><p style="font-size:17px;line-height:1.45;font-weight:500;overflow-wrap:anywhere">${e.enonce ? enonce(e.enonce) : '…'}</p>
      <div class="champ row" style="min-height:36px;color:var(--text-3)" aria-hidden="true">Ta réponse…</div></div>`;
  }
}
