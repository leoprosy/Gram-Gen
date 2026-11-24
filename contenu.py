"""Format d'échange d'un exercice : validation, empreinte, import, prompt de génération."""

import json
import re
import unicodedata
from datetime import datetime

TYPES = {"trous": "Phrase à trous", "conjugaison": "Conjugaison", "theme": "Thème ciblé",
         "transformation": "Transformation", "choix": "Choix contrasté", "qcm": "QCM",
         "erreur": "Repérage d'erreur"}
CONSIGNES = {"trous": "Complète la phrase.", "conjugaison": "Conjugue le verbe.",
             "theme": "Traduis en {langue}.", "transformation": "Transforme la phrase.",
             "choix": "Choisis la bonne forme.", "qcm": "Choisis la bonne réponse.",
             "erreur": "Trouve et corrige l'erreur."}
STATUTS = ("actif", "a_valider", "retire", "archive")
JSON_CHAMPS = ("concepts", "reponses", "distracteurs")


class Invalide(ValueError):
    pass


def maintenant():
    return datetime.now().isoformat(timespec="seconds")


def empreinte(enonce: str, langue: str) -> str:
    """Énoncé sans casse ni ponctuation. La langue en fait partie : un même thème sert aux deux."""
    s = unicodedata.normalize("NFC", enonce).casefold()
    return f"{langue}:" + " ".join(re.sub(r"[\W_]+", " ", s).split())


def ligne(row) -> dict:
    ex = dict(row)
    for c in JSON_CHAMPS:
        ex[c] = json.loads(ex[c])
    return ex


def _textes(valeur, nom):
    if not isinstance(valeur, list) or not all(isinstance(v, str) for v in valeur):
        raise Invalide(f"« {nom} » doit être une liste de textes.")
    return [v.strip() for v in valeur if v.strip()]


def valider(brut, concepts: dict) -> dict:
    """Objet du format d'échange → champs propres. Lève Invalide. `concepts` : code → langue."""
    if not isinstance(brut, dict):
        raise Invalide("Chaque exercice doit être un objet JSON.")
    codes = _textes(brut.get("concepts"), "concepts")
    if not codes:
        raise Invalide("Choisir un concept.")
    inconnus = [c for c in codes if c not in concepts]
    if inconnus:
        raise Invalide(f"Concept inconnu : {', '.join(inconnus)}.")
    langue = concepts[codes[0]]
    if any(concepts[c] != langue for c in codes):
        raise Invalide("Tous les concepts doivent être de la même langue.")
    type_ = brut.get("type")
    if not isinstance(type_, str) or type_ not in TYPES:
        raise Invalide(f"Type inconnu : {type_}.")
    champs = {k: brut.get(k) or "" for k in ("consigne", "enonce", "indice", "explication")}
    if not all(isinstance(v, str) for v in champs.values()):
        raise Invalide("Consigne, énoncé, indice et explication doivent être du texte.")
    champs = {k: v.strip() for k, v in champs.items()}
    enonce = champs["enonce"]
    if empreinte(enonce, "") == ":":
        raise Invalide("L'énoncé est vide.")
    reponses = brut.get("reponses")
    if type_ == "trous":
        blancs = re.findall(r"\{\{(\d+)\}\}", enonce)
        if not blancs or blancs != [str(i + 1) for i in range(len(blancs))]:
            raise Invalide("Marquer les blancs avec {{1}}, {{2}}… dans l'ordre.")
        if isinstance(reponses, list) and reponses and all(isinstance(r, str) for r in reponses):
            reponses = [reponses] if len(blancs) == 1 else [[r] for r in reponses]
        if not isinstance(reponses, list) or len(reponses) != len(blancs):
            raise Invalide(f"Il faut une liste de réponses par blanc ({len(blancs)}).")
        reponses = [_textes(r, "reponses") for r in reponses]
        if not all(reponses):
            raise Invalide("Chaque blanc doit avoir une réponse.")
    else:
        reponses = _textes(reponses, "reponses")
        if not reponses:
            raise Invalide("Ajouter au moins une réponse.")
    distracteurs = _textes(brut.get("distracteurs") or [], "distracteurs")
    if type_ in ("qcm", "choix"):
        distracteurs = [d for d in dict.fromkeys(distracteurs) if d not in reponses]
        if not 1 <= len(distracteurs) <= 3:
            raise Invalide("Un QCM ou un choix contrasté a de 1 à 3 distracteurs.")
    difficulte = brut.get("difficulte", 2)
    if type(difficulte) is not int or not 1 <= difficulte <= 3:
        raise Invalide("La difficulté va de 1 à 3.")
    champs["consigne"] = champs["consigne"] or CONSIGNES[type_].format(
        langue="espagnol" if langue == "es" else "anglais")
    return {**champs, "concepts": codes, "type": type_, "reponses": reponses,
            "distracteurs": distracteurs, "difficulte": difficulte, "empreinte": empreinte(enonce, langue)}


def langues(con) -> dict:
    return {r["code"]: r["langue"] for r in con.execute("SELECT code, langue FROM concept")}


def doublon(con, emp, sauf=None):
    r = con.execute("SELECT id FROM exercice WHERE empreinte=? AND id IS NOT ?", (emp, sauf)).fetchone()
    return r and r["id"]


def _sql(ex):
    return {k: json.dumps(v, ensure_ascii=False) if k in JSON_CHAMPS else v for k, v in ex.items()}


def inserer(con, ex: dict, source: str, statut: str) -> int:
    v = {**_sql(ex), "source": source, "statut": statut, "cree_le": maintenant()}
    return con.execute(f"INSERT INTO exercice ({','.join(v)}) VALUES ({','.join('?' * len(v))})",
                       list(v.values())).lastrowid


def modifier(con, id_, ex: dict):
    v = _sql(ex)
    con.execute(f"UPDATE exercice SET {','.join(k + '=?' for k in v)} WHERE id=?", [*v.values(), id_])


def valider_concept(c) -> dict:
    if not isinstance(c, dict):
        raise Invalide("Chaque concept doit être un objet JSON.")
    t = {k: c.get(k) or "" for k in ("code", "langue", "titre", "categorie", "fiche")}
    if not all(isinstance(v, str) for v in t.values()):
        raise Invalide("Champs de concept invalides.")
    t = {k: v.strip() for k, v in t.items()}
    if t["langue"] not in ("en", "es"):
        raise Invalide("Langue : en ou es.")
    if not t["titre"] or not t["categorie"]:
        raise Invalide("Titre et catégorie sont obligatoires.")
    if not t["code"]:
        plat = unicodedata.normalize("NFD", t["titre"]).encode("ascii", "ignore").decode().lower()
        t["code"] = f"{t['langue']}." + re.sub(r"[^a-z0-9]+", "-", plat).strip("-")
    if not re.fullmatch(t["langue"] + r"\.[a-z0-9][a-z0-9-]*", t["code"]):
        raise Invalide(f"Code de concept invalide : {t['code']}.")
    t["voisins"] = _textes(c.get("voisins") or [], "voisins")
    return t


def inserer_concept(con, c: dict):
    con.execute("INSERT INTO concept VALUES (:code,:langue,:titre,:categorie,:fiche,:voisins)",
                {**c, "voisins": json.dumps(c["voisins"])})


def importer(con, donnees, source="import", statut="a_valider") -> dict:
    """Liste d'exercices, ou {"concepts": […], "exercices": […]}. Doublons rejetés et signalés."""
    paquet = donnees if isinstance(donnees, dict) else {"exercices": donnees}
    exercices, concepts = paquet.get("exercices"), paquet.get("concepts") or []
    if not isinstance(exercices, list) or not isinstance(concepts, list):
        raise Invalide("Le fichier doit contenir une liste d'exercices.")
    bilan = {"ajoutes": 0, "doublons": [], "erreurs": []}
    connus = langues(con)
    for i, brut in enumerate(concepts):
        try:
            c = valider_concept(brut)
            if c["code"] not in connus:
                inserer_concept(con, c)
                connus[c["code"]] = c["langue"]
        except Invalide as e:
            bilan["erreurs"].append({"n": i + 1, "message": f"concept : {e}"})
    for i, brut in enumerate(exercices):
        try:
            ex = valider(brut, connus)
        except Invalide as e:
            bilan["erreurs"].append({"n": i + 1, "message": str(e)})
            continue
        if doublon(con, ex["empreinte"]):
            bilan["doublons"].append(ex["enonce"])
            continue
        inserer(con, ex, source, statut)
        bilan["ajoutes"] += 1
    return bilan


def prompt(concept, existants: list, nombre: int, types: list, difficulte: int) -> str:
    """Prompt à coller dans un assistant : le MVP n'appelle aucune IA lui-même."""
    langue = "espagnol" if concept["langue"] == "es" else "anglais"
    exemple = {"concepts": [concept["code"]], "type": "trous", "consigne": "Complète la phrase.",
               "enonce": "… {{1}} … (verbe)", "reponses": [["réponse 1", "réponse 2"]],
               "distracteurs": [], "indice": "", "explication": "", "difficulte": difficulte}
    lignes = [
        f"Écris {nombre} exercices de grammaire ({langue}) pour un étudiant francophone de prépa ECG (concours BCE).",
        f"Concept visé : {concept['titre']} (code {concept['code']}).",
        f"Règle : {concept['fiche']}" if concept["fiche"] else "",
        f"Types, à répartir : {', '.join(f'{t} ({TYPES[t]})' for t in types)}. Difficulté : {difficulte} sur 3.",
        "", "Contraintes :",
        "- un seul point de grammaire par phrase, le reste de la phrase reste simple ; 8 à 20 mots ;",
        "- vocabulaire B2-C1 proche des sujets BCE (économie, société, actualité) ;",
        "- toutes les réponses correctes plausibles dans « reponses » ;",
        "- qcm : 3 distracteurs, choix : 1 à 3 ; ce sont de vraies fautes d'étudiants francophones, "
        "et le blanc s'écrit ___ ;",
        "- trous : blancs {{1}}, {{2}}… et « reponses » = une liste par blanc ; "
        "pour les autres types, une simple liste de textes ;",
        "- explication d'une ou deux phrases, en français.", "",
        "Réponds uniquement par un tableau JSON d'objets de cette forme :",
        json.dumps(exemple, ensure_ascii=False, indent=2),
    ]
    if existants:
        lignes += ["", "Énoncés déjà présents, à ne pas reproduire ni paraphraser :",
                   *(f"- {e}" for e in existants)]
    return "\n".join(lignes)
