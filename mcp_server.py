"""Gram-Gen exposé à Claude comme serveur MCP (stdio, sans dépendance), repris d'Anki-Gen.

Lancé par `gramgen-server.exe --mcp` ou, en développement, `python launcher.py --mcp`.
Chaque outil passe par une route de l'API (`app.test_client()`) : même validation, et la base
garde un seul écrivain. Seul le sous-ensemble « tools » du protocole est implémenté.
"""

import json
from urllib.parse import quote

PROTOCOLE = "2025-06-18"
INSTRUCTIONS = (
    "Gram-Gen fait réviser la grammaire anglaise (en) et espagnole (es) par concepts. "
    "Pour remplir un réservoir : etat_reservoirs → enonces (pour ne pas répéter l'existant) → ajouter_exercices. "
    "Les exercices ajoutés arrivent dans la file « À valider » de l'app. Format d'un exercice : "
    '{"concepts": ["es.ser-estar"], "type": "trous|conjugaison|theme|transformation|choix|qcm|erreur", '
    '"consigne": "", "enonce": "", "reponses": [], "distracteurs": [], "indice": "", "explication": "", "difficulte": 1-3}. '
    "Trous : blancs {{1}}, {{2}}… et « reponses » = une liste par blanc. QCM et choix : blanc ___, 1 à 3 distracteurs "
    "(vraies fautes d'étudiants francophones). Theme : énoncé en français, reponses = traductions acceptées. "
    "Un seul point de grammaire par phrase, 8 à 20 mots, vocabulaire B2-C1 proche des sujets BCE, "
    "toutes les réponses correctes plausibles, explication d'une ou deux phrases en français.")


def _texte(r):
    corps = r.get_json(silent=True)
    if corps is None:
        return f"HTTP {r.status_code}", True
    return json.dumps(corps, ensure_ascii=False), r.status_code >= 400


def outils(client):
    def lister_concepts(langue=None):
        r = client.get("/api/concepts")
        champs = ("code", "langue", "titre", "categorie", "fiche", "voisins", "actifs", "non_vus", "maitrise")
        return json.dumps([{k: c[k] for k in champs} for c in r.get_json()
                           if langue in (None, c["langue"])], ensure_ascii=False), False

    def creer_concept(langue, titre, categorie, fiche="", code=None, voisins=None):
        return _texte(client.post("/api/concepts", json={
            "langue": langue, "titre": titre, "categorie": categorie, "fiche": fiche, "code": code or "",
            "voisins": voisins or []}))

    def enonces(concept):
        r = client.get(f"/api/exercices?concept={quote(concept)}")
        return json.dumps([{"type": x["type"], "enonce": x["enonce"], "statut": x["statut"]}
                           for x in r.get_json()], ensure_ascii=False), False

    def ajouter_exercices(exercices, concepts=None):
        return _texte(client.post("/api/import", json={
            "donnees": {"exercices": exercices, "concepts": concepts or []}, "source": "mcp"}))

    def etat_reservoirs(seuil=10):
        bas = [{"code": c["code"], "titre": c["titre"], "non_vus": c["non_vus"], "actifs": c["actifs"]}
               for c in client.get("/api/concepts").get_json() if c["non_vus"] < seuil]
        return json.dumps(sorted(bas, key=lambda c: c["non_vus"]), ensure_ascii=False), False

    def statistiques(langue="tout", periode="30"):
        return _texte(client.get(f"/api/stats?langue={quote(langue)}&periode={quote(periode)}"))

    def schema(requis=(), **props):
        return {"type": "object", "properties": props, "required": list(requis)}

    S, I = {"type": "string"}, {"type": "integer"}
    L = {"type": "string", "enum": ["en", "es"]}
    return {
        "lister_concepts": (lister_concepts, "Concepts (code, titre, catégorie, fiche-règle, voisins, réservoir, maîtrise 0-100).",
                            schema(langue=L)),
        "creer_concept": (creer_concept, "Crée un concept. Le code (ex. « es.ser-estar ») se déduit du titre s'il manque ; "
                                         "voisins = codes des concepts qui se confondent avec lui.",
                          schema(["langue", "titre", "categorie"], langue=L, titre=S, categorie=S, fiche=S, code=S,
                                 voisins={"type": "array", "items": S})),
        "enonces": (enonces, "Énoncés déjà présents pour un concept : à ne pas reproduire ni paraphraser.",
                    schema(["concept"], concept=S)),
        "ajouter_exercices": (ajouter_exercices, "Ajoute un lot d'exercices (file « À valider »). Renvoie le nombre ajouté, "
                                                 "les doublons rejetés et les erreurs de format, exercice par exercice. "
                                                 "concepts : nouveaux concepts à créer dans le même envoi.",
                              schema(["exercices"], exercices={"type": "array", "items": {"type": "object"}},
                                     concepts={"type": "array", "items": {"type": "object"}})),
        "etat_reservoirs": (etat_reservoirs, "Concepts dont le réservoir d'exercices actifs jamais vus est sous le seuil (10 par défaut).",
                            schema(seuil=I)),
        "statistiques": (statistiques, "Statistiques : réussite, temps, réussite par type, fautes fréquentes, maîtrise par concept.",
                         schema(langue={"type": "string", "enum": ["tout", "en", "es"]},
                                periode={"type": "string", "enum": ["7", "30", "tout"]})),
    }


def traiter(message, table, version="dev"):
    """Un message JSON-RPC → la réponse, ou None pour une notification."""
    methode, params, mid = message.get("method"), message.get("params") or {}, message.get("id")
    if mid is None:
        return None
    if methode == "initialize":
        res = {"protocolVersion": params.get("protocolVersion", PROTOCOLE), "capabilities": {"tools": {}},
               "serverInfo": {"name": "gramgen", "version": version}, "instructions": INSTRUCTIONS}
    elif methode == "ping":
        res = {}
    elif methode == "tools/list":
        res = {"tools": [{"name": n, "description": d, "inputSchema": s} for n, (_, d, s) in table.items()]}
    elif methode == "tools/call":
        outil = table.get(params.get("name"))
        if outil is None:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"Outil inconnu : {params.get('name')}"}}
        try:
            texte, erreur = outil[0](**(params.get("arguments") or {}))
        except Exception as e:   # noqa: BLE001 — l'erreur va à Claude, le serveur reste debout
            texte, erreur = f"{type(e).__name__}: {e}", True
        res = {"content": [{"type": "text", "text": texte}], "isError": erreur}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Méthode inconnue : {methode}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": res}


def servir(app, stdin, stdout):
    """Boucle stdio. `stdout` est le vrai canal : launcher envoie print() sur stderr."""
    import updater
    table = outils(app.test_client())
    for ligne in stdin:
        if not ligne.strip():
            continue
        try:
            rep = traiter(json.loads(ligne), table, updater.version_locale())
        except ValueError:
            rep = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        if rep is not None:
            stdout.write(json.dumps(rep, ensure_ascii=False).encode("utf-8") + b"\n")
            stdout.flush()
    return 0
