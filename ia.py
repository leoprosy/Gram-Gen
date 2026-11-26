"""Appels à Claude : jugement des réponses libres (étage 3) et génération d'exercices.

Tout échec (pas de clé, hors ligne, refus) lève Indisponible : l'app retombe alors sur le
tranchage à la main et le copier-coller du prompt. Rien d'autre ne dépend de ce module.
"""

import json
import os

MODELE = "claude-opus-5-5"
VERDICTS = ("juste", "maladroit", "faute_point", "faute_ailleurs")
CODES = ("grammaire", "conjugaison", "accent", "orthographe", "barbarisme", "lexique", "contresens", "omission")


class Indisponible(Exception):
    pass


def disponible(cle: str) -> bool:
    return bool(cle or os.environ.get("ANTHROPIC_API_KEY"))


def appeler(cle, systeme: str, texte: str, schema: dict, effort="low", delai=60) -> dict:
    """Un message, une réponse JSON conforme à `schema`."""
    if not disponible(cle):
        raise Indisponible("Aucune clé d'API.")
    try:
        import anthropic
    except ImportError:
        raise Indisponible("Cette installation n'embarque pas l'accès à Claude : réinstaller Gram-Gen.")
    client = anthropic.Anthropic(api_key=cle or None, timeout=delai, max_retries=1)
    try:
        r = client.beta.messages.create(
            model=MODELE, max_tokens=16000, system=systeme,
            messages=[{"role": "user", "content": texte}],
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}})
    except anthropic.AuthenticationError:
        raise Indisponible("Clé d'API refusée.")
    except anthropic.RateLimitError:
        raise Indisponible("Trop de requêtes : réessayer dans un instant.")
    except anthropic.APIStatusError as e:
        raise Indisponible(f"Erreur de l'API ({e.status_code}).")
    except anthropic.APIConnectionError:
        raise Indisponible("Pas de connexion.")
    if r.stop_reason != "end_turn":
        raise Indisponible("Réponse refusée ou incomplète." if r.stop_reason == "refusal" else "Réponse incomplète.")
    return json.loads(next(b.text for b in r.content if b.type == "text"))


def _objet(**props):
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


_TEXTE, _LISTE = {"type": "string"}, {"type": "array", "items": {"type": "string"}}

JUGEMENT = _objet(verdict={"type": "string", "enum": list(VERDICTS)},
                  code_erreur={"type": "string", "enum": [*CODES, "aucun"]}, commentaire=_TEXTE)

SYSTEME_JUGE = (
    "Tu corriges les réponses d'un étudiant francophone de prépa ECG (concours BCE) à des exercices de grammaire. "
    "Juge uniquement la langue : une réponse correcte et naturelle qui diffère des références est juste. "
    "Verdicts : « juste » ; « maladroit » (correcte mais peu idiomatique) ; « faute_point » (faute sur le point de "
    "grammaire visé) ; « faute_ailleurs » (point visé réussi, mais une autre faute). Un accent manquant ou faux en "
    "espagnol est une faute (code « accent »). Code « aucun » si la réponse est juste ou maladroite. "
    "Le commentaire tient en une phrase, en français, et nomme la faute s'il y en a une.")


def juger(cle, ex: dict, concept: dict, donne: str) -> dict:
    texte = "\n".join([
        f"Langue : {'espagnol' if concept['langue'] == 'es' else 'anglais'}.",
        f"Point visé : {concept['titre']}.", f"Consigne : {ex['consigne']}", f"Énoncé : {ex['enonce']}",
        "Réponses de référence :", *(f"- {r}" for r in ex["reponses"]), f"Réponse de l'étudiant : {donne}"])
    v = appeler(cle, SYSTEME_JUGE, texte, JUGEMENT)
    if v.get("verdict") not in VERDICTS:
        raise Indisponible("Verdict illisible.")
    return v


EXERCICES = _objet(exercices={"type": "array", "items": _objet(
    concepts=_LISTE, type={"type": "string"}, consigne=_TEXTE, enonce=_TEXTE,
    reponses={"type": "array", "items": _LISTE}, distracteurs=_LISTE, indice=_TEXTE, explication=_TEXTE,
    difficulte={"type": "integer"})})


def generer(cle, prompt: str) -> list:
    """Exercices au format d'échange. Le schéma impose une liste de listes pour « reponses » : on l'aplatit hors trous."""
    sortie = appeler(cle, "Tu écris des exercices de grammaire pour Gram-Gen.",
                     prompt + "\n\nIci, « reponses » est toujours une liste de listes : "
                              "une par blanc pour « trous », une seule liste pour les autres types.",
                     EXERCICES, effort="medium", delai=300)["exercices"]
    for x in sortie:
        if x.get("type") != "trous":
            x["reponses"] = [r for liste in x.get("reponses") or [] for r in liste]
    return sortie
