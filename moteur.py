"""Planificateur : SM-2 par concept, maîtrise, retrait, composition d'une séance. Fonctions pures."""

from datetime import date, datetime, timedelta

SECONDES_PAR_EXERCICE = 40
REPOS_JOURS = 14
RETRAIT_JOURS = 7
SEUIL_RESERVOIR = 10
SEUIL_ACQUIS = 80
ECRITS = {"trous", "conjugaison", "theme", "transformation", "erreur"}


def est_faute(resultat, langue, type_, accents="faux"):
    """L'accent espagnol compte faux par défaut ; toujours en conjugaison."""
    return resultat == "faux" or (
        resultat == "accent" and langue == "es" and (accents == "faux" or type_ == "conjugaison"))


def score(resultat, faute):
    return 1.0 if resultat == "juste" else 0.0 if faute else 0.5


def sm2(etat: dict, fautes: list, parfait: bool, jour: date) -> dict:
    """État d'un concept après une séance. `fautes` : un booléen par tentative."""
    intervalle, facilite = etat["intervalle"], etat["facilite"]
    if any(fautes):
        intervalle, facilite = 1.0, max(1.3, round(facilite - 0.2, 2))
    else:
        intervalle *= facilite if parfait else 1.2
    jours = max(1, int(intervalle + 0.5))
    return {"intervalle": intervalle, "facilite": facilite,
            "echeance": (jour + timedelta(days=jours)).isoformat()}


def maitrise(scores: list) -> int:
    """0-100 : 20 dernières tentatives (de la plus ancienne à la plus récente), poids 1…n."""
    s = scores[-20:]
    return round(100 * sum((i + 1) * x for i, x in enumerate(s)) / sum(range(1, len(s) + 1))) if s else 0


def a_retirer(tentatives: list) -> bool:
    """Deux réussites de suite à au moins 7 jours d'écart. [(date ISO, resultat)], chronologique."""
    if len(tentatives) < 2:
        return False
    (d1, r1), (d2, r2) = tentatives[-2:]
    ecart = datetime.fromisoformat(d2) - datetime.fromisoformat(d1)
    return r1 == r2 == "juste" and ecart >= timedelta(days=RETRAIT_JOURS)


def tirer(candidats: list, n: int, acquis: bool, jour: date, exclus=()) -> list:
    """
    n exercices d'un concept : jamais vus d'abord, puis les moins récemment vus, en variant
    les types. Rien de vu depuis moins de 14 jours, sauf réservoir épuisé.
    `candidats` : [{"id", "type", "vu": date ISO ou None}], déjà mélangés.
    """
    limite = (jour - timedelta(days=REPOS_JOURS)).isoformat()
    libres = [c for c in candidats if c["id"] not in exclus]
    libres = [c for c in libres if not c["vu"] or c["vu"][:10] <= limite] or libres
    choisis, types = [], {}
    while libres and len(choisis) < n:
        c = min(libres, key=lambda c: (
            bool(c["vu"]), types.get(c["type"], 0), (c["type"] in ECRITS) != acquis, c["vu"] or ""))
        libres.remove(c)
        choisis.append(c)
        types[c["type"]] = types.get(c["type"], 0) + 1
    return choisis


def repartir(nb_concepts: int, budget: int):
    """(concepts retenus, exercices par concept) pour un budget d'exercices ; 2 à 4 chacun."""
    if not nb_concepts:
        return 0, 0
    return min(nb_concepts, max(1, budget // 2)), max(2, min(4, budget // nb_concepts))


def entrelacer(series: list) -> list:
    """Un exercice de chaque concept à tour de rôle : les voisins alternent."""
    sortie = []
    for i in range(max(map(len, series), default=0)):
        sortie += [s[i] for s in series if i < len(s)]
    return sortie


def voisins_cote_a_cote(concepts: list, voisins: dict) -> list:
    """Réordonne pour que deux concepts voisins se suivent."""
    reste, sortie = list(concepts), []
    while reste:
        suivant = next((c for c in reste if sortie and c in voisins.get(sortie[-1], ())), reste[0])
        reste.remove(suivant)
        sortie.append(suivant)
    return sortie


def serie(jours: set, aujourd_hui: date) -> int:
    """Jours consécutifs travaillés ; la journée en cours ne casse pas la série."""
    d = aujourd_hui if aujourd_hui.isoformat() in jours else aujourd_hui - timedelta(days=1)
    n = 0
    while d.isoformat() in jours:
        n, d = n + 1, d - timedelta(days=1)
    return n
