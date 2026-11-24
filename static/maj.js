// Mise à jour : vérifiée une fois au démarrage, affichée dans « À traiter » et dans les réglages.
import { html, raw, ico, api, toast, router, fenetreOuverte } from './base.js';

export const maj = { etat: null, version: '', message: '', occupe: false };

async function charger(methode) {
  Object.assign(maj, await api(methode, 'maj', methode === 'POST' ? {} : undefined));
}
/** Au démarrage : silencieux hors ligne, et ne dérange ni une séance ni une fenêtre ouverte. */
export async function surveiller() {
  await charger('GET').catch(() => {});
  if (aFaire() && ['', '#/'].includes(location.hash) && !fenetreOuverte()) router();
}
export const aFaire = () => ['disponible', 'prete', 'installateur'].includes(maj.etat);

export const actsMaj = {
  async verifier() {
    await charger('GET');
    if (!aFaire()) toast({ a_jour: 'Gram-Gen est à jour.', developpement: 'Version de développement : pas de mise à jour.' }[maj.etat] || maj.message);
    router();
  },
  async majAgir() {
    if (maj.occupe) return;
    maj.occupe = true;
    router();
    try {
      if (maj.etat === 'installateur') await api('POST', 'maj/installateur', {});
      else if (maj.etat === 'prete') await redemarrer();
      else { await charger('POST'); if (maj.etat === 'erreur') toast(maj.message); }
    } finally { maj.occupe = false; router(); }
  },
};
async function redemarrer() {
  try { await window.__TAURI__.core.invoke('restart_app'); } catch { toast('Fermer puis rouvrir Gram-Gen pour terminer la mise à jour.'); }
}

const TEXTES = {
  disponible: ['est disponible', 'Mettre à jour', 'Téléchargement…'],
  prete: ['est prête', 'Redémarrer', 'Redémarrage…'],
  installateur: ['demande un nouvel installateur', 'Télécharger', 'Ouverture…'],
};
export const ligneMaj = () => {
  if (!aFaire()) return '';
  const [texte, bouton, enCours] = TEXTES[maj.etat];
  return html`<div class="creux row g12" style="padding:12px 12px 12px 16px;font-size:14px;line-height:1.45">${ico('importer')}<span class="f1" role="status"><b class="fort">Gram-Gen ${maj.version}</b> ${texte}</span><button type="button" class="btn f" style="color:var(--text);padding:0 8px" data-act="majAgir" ${raw(maj.occupe ? 'disabled' : '')}>${maj.occupe ? enCours : bouton}</button></div>`;
};
