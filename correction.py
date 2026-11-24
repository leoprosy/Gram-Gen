"""Correction, étages 1 (exact normalisé) et 2 (tolérant). Aucun accès à la base."""

import difflib
import re
import unicodedata
from itertools import product

# Types à phrase libre : une réponse non reconnue n'est pas forcément fausse.
LIBRES = {"theme", "transformation", "erreur"}

CONTRACTIONS = [(r"\bcan't\b", "can not"), (r"\bwon't\b", "will not"), (r"\bshan't\b", "shall not"),
                (r"\bcannot\b", "can not"), (r"n't\b", " not"), (r"'re\b", " are"), (r"'ve\b", " have"),
                (r"'ll\b", " will"), (r"\bi'm\b", "i am"), (r"\blet's\b", "let us")]


def normaliser(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "")
    s = re.sub("[’‘ʼ`´]", "'", s)
    s = re.sub("[“”«»\"]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)
    s = re.sub(r"[.…]+$", "", s).strip()
    return s[:1].lower() + s[1:]


def sans_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def developper(s: str, langue: str) -> set:
    """Formes pleines d'une réponse normalisée (don't → do not, he's → he is / he has)."""
    if langue != "en":
        return {s}
    s = re.sub(r"\bI\b", "i", s)
    for motif, plein in CONTRACTIONS:
        s = re.sub(motif, plein, s, flags=re.I)

    # ponytail: 's et 'd levés par le mot suivant, pas par une vraie analyse ; suffisant pour des phrases courtes
    def options(lettre, suivant):
        if lettre == "s":
            return [" is"] if suivant.endswith("ing") else [" is", " has", "'s"]
        if suivant == "have":
            return [" would"]
        return [" had"] if suivant == "better" else [" would", " had"]

    marques = list(re.finditer(r"'(s|d)\b(?=\s*(\w*))", s))
    formes = set()
    for combi in product(*(options(m.group(1), m.group(2)) for m in marques)):
        sortie, pos = "", 0
        for m, plein in zip(marques, combi):
            sortie += s[pos:m.start()] + plein
            pos = m.end()
        formes.add((sortie + s[pos:]).strip())   # « 'll go » seul dans un blanc
    return formes


def _une_lettre(a: str, b: str) -> bool:
    """Distance d'édition de 1 (ou deux lettres voisines inversées)."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    return (a[i + 1:] == b[i + 1:] or a[i + 1:] == b[i:] or a[i:] == b[i + 1:]
            or (a[i:i + 2] == b[i:i + 2][::-1] and a[i + 2:] == b[i + 2:]))


def _mots(s):
    return re.findall(r"[\w'-]+|[^\w\s]", s)


def coquille(donne: str, attendu: str, enonce: str):
    """
    Faute de frappe « hors du mot visé » : un seul mot diffère d'une lettre, et
    le mot attendu figure tel quel dans l'énoncé (l'élève ne faisait que le recopier).
    """
    d, a = _mots(donne), _mots(attendu)
    if len(d) != len(a):
        return None
    ecarts = [(x, y) for x, y in zip(d, a) if x != y]
    if len(ecarts) == 1 and _une_lettre(*ecarts[0]) and ecarts[0][1] in _mots(normaliser(enonce)):
        return {"donne": ecarts[0][0], "attendu": ecarts[0][1]}
    return None


def comparer(donne: str, reponses: list, langue: str, type_: str, enonce: str) -> dict:
    """Une réponse contre sa liste de références."""
    d = normaliser(donne)
    if not d:
        return {"resultat": "faux", "reference": reponses[0]}
    formes = developper(d, langue)
    for r in reponses:
        if formes & developper(normaliser(r), langue):
            return {"resultat": "juste", "reference": r}
    plates = {sans_accents(f) for f in formes}
    for r in reponses:
        n = normaliser(r)
        if plates & {sans_accents(f) for f in developper(n, langue)}:
            return {"resultat": "accent", "reference": r,
                    "accents": [[x, y] for x, y in zip(_mots(d), _mots(n)) if x != y]}
    if type_ in LIBRES:
        for r in reponses:
            c = coquille(d, normaliser(r), enonce)
            if c:
                return {"resultat": "juste", "reference": r, "coquille": c}
    proche = max(reponses, key=lambda r: difflib.SequenceMatcher(None, d, normaliser(r)).ratio())
    return {"resultat": "averifier" if type_ in LIBRES else "faux", "reference": proche}


def diff(donne: str, attendu: str):
    """Mots de chaque côté, avec un drapeau « différent » : [[mot, bool], …] ×2."""
    def cle(m):
        return normaliser(m).strip(".,;:!?¿¡")

    d, a = donne.split(), attendu.split()
    sm = difflib.SequenceMatcher(None, [cle(m) for m in d], [cle(m) for m in a], autojunk=False)
    gauche, droite = [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        gauche += [[m, op != "equal"] for m in d[i1:i2]]
        droite += [[m, op != "equal"] for m in a[j1:j2]]
    return gauche, droite


RANG = {"juste": 0, "accent": 1, "averifier": 2, "faux": 3}


def corriger(ex: dict, donnees: list, langue: str) -> dict:
    """Verdict d'un exercice. `donnees` : une chaîne par blanc (une seule hors phrase à trous)."""
    par_blanc = ex["reponses"] if ex["type"] == "trous" else [ex["reponses"]]
    donnees = (list(donnees) + [""] * len(par_blanc))[:len(par_blanc)]
    v = [comparer(d, r, langue, ex["type"], ex["enonce"]) for d, r in zip(donnees, par_blanc)]
    pire = max(v, key=lambda x: RANG[x["resultat"]])["resultat"]
    donne, reference = " · ".join(donnees), " · ".join(x["reference"] for x in v)
    gauche, droite = diff(donne, reference)
    autres = [] if len(par_blanc) > 1 else [r for r in par_blanc[0] if r != v[0]["reference"]]
    return {"resultat": pire, "donne": donne, "reference": reference, "autres": autres,
            "diff_donne": gauche, "diff_attendu": droite,
            "accents": [a for x in v for a in x.get("accents", [])],
            "coquille": next((x["coquille"] for x in v if x.get("coquille")), None)}
