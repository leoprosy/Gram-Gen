"""API locale de Gram-Gen. Seule à écrire dans la base. Lancer : python launcher.py"""

import json
import random
import sqlite3
import webbrowser
from datetime import date, timedelta

from flask import Flask, abort, g, jsonify, render_template, request

import contenu
import correction
import db
import ia
import moteur
import updater
from contenu import Invalide

app = Flask(__name__, template_folder=str(db.CODE_DIR / "templates"), static_folder=str(db.CODE_DIR / "static"))
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
app.json.ensure_ascii = False
app.json.sort_keys = False
app.jinja_env.policies["json.dumps_kwargs"] = {"sort_keys": False}

REGLAGES = {"accents": "faux", "duree": 15, "nouveaux": 2, "theme": "auto", "cle_api": ""}
VALEURS = {"accents": ("faux", "demi"), "duree": (10, 15, 25), "nouveaux": tuple(range(6)),
           "theme": ("auto", "clair", "sombre")}


# ── Plomberie ────────────────────────────────────────────────

@app.before_request
def hote_local():
    # Parade au DNS rebinding : seule la machine parle à l'API. Le CSRF est couvert par
    # l'exigence application/json (préflight refusé, aucun en-tête CORS).
    if request.host.rsplit(":", 1)[0] not in ("127.0.0.1", "localhost"):
        abort(403)


def con() -> sqlite3.Connection:
    if "con" not in g:
        g.con = db.connecter()
    return g.con


@app.teardown_appcontext
def fermer(_):
    if "con" in g:
        g.con.close()


@app.errorhandler(Invalide)
def invalide(e):
    if "con" in g:
        g.con.rollback()
    return jsonify(erreur=str(e)), 400


@app.errorhandler(404)
@app.errorhandler(405)
@app.errorhandler(413)
@app.errorhandler(415)
@app.errorhandler(400)
def erreur_http(e):
    return jsonify(erreur=e.description), e.code


def corps() -> dict:
    d = request.get_json()
    if not isinstance(d, dict):
        raise Invalide("Objet JSON attendu.")
    return d


def rows(sql, *params):
    return con().execute(sql, params).fetchall()


def aujourd_hui() -> date:
    return date.today()


def reglages() -> dict:
    return {**REGLAGES, **{r["cle"]: json.loads(r["valeur"]) for r in rows("SELECT * FROM reglage WHERE cle NOT LIKE 'seed:%'")}}


def exercice_ou_404(id_) -> dict:
    r = con().execute("SELECT * FROM exercice WHERE id=?", (id_,)).fetchone()
    return contenu.ligne(r) if r else abort(404, "Exercice introuvable.")


def concepts_complets() -> dict:
    """code → concept + état + réservoir."""
    out = {}
    for r in rows("SELECT c.*, e.echeance, e.debut FROM concept c "
                  "LEFT JOIN etat_concept e ON e.concept = c.code ORDER BY c.langue, c.rowid"):
        c = dict(r)
        c.update(voisins=json.loads(c["voisins"]), maitrise=0, actifs=0, non_vus=0, vu=None, scores=[])
        out[c["code"]] = c
    for r in rows("SELECT j.value code, COUNT(*) actifs, SUM(t.vu IS NULL) non_vus FROM exercice x, "
                  "json_each(x.concepts) j LEFT JOIN (SELECT exercice, MAX(date) vu FROM tentative GROUP BY exercice) t "
                  "ON t.exercice = x.id WHERE x.statut='actif' GROUP BY j.value"):
        if r["code"] in out:
            out[r["code"]].update(actifs=r["actifs"], non_vus=r["non_vus"])
    severite = reglages()["accents"]
    for t in rows("SELECT j.value code, t.date, t.resultat, x.type FROM tentative t JOIN exercice x ON x.id=t.exercice, "
                  "json_each(x.concepts) j ORDER BY t.date, t.id"):
        if t["code"] in out:
            c = out[t["code"]]
            c["vu"] = t["date"]
            c["scores"].append(moteur.score(
                t["resultat"], moteur.est_faute(t["resultat"], c["langue"], t["type"], severite)))
    for c in out.values():
        c["maitrise"] = moteur.maitrise(c.pop("scores"))
        c["acquis"] = c["maitrise"] >= moteur.SEUIL_ACQUIS
    return out


def graphe_voisins(concepts) -> dict:
    v = {c: set() for c in concepts}
    for code, c in concepts.items():
        for autre in c["voisins"]:
            if autre in v:
                v[code].add(autre)
                v[autre].add(code)
    return v


def candidats(code, types=None):
    """Exercices actifs d'un concept, mélangés, avec leur dernière apparition."""
    r = [dict(x) for x in rows(
        "SELECT x.id, x.type, (SELECT MAX(date) FROM tentative t WHERE t.exercice=x.id) vu FROM exercice x "
        "WHERE x.statut='actif' AND EXISTS (SELECT 1 FROM json_each(x.concepts) WHERE value=?)", code)]
    random.shuffle(r)
    return [x for x in r if not types or x["type"] in types]


def vue_seance(id_, concepts) -> dict:
    """Ce que la séance affiche avant la réponse (donc sans la solution)."""
    ex = exercice_ou_404(id_)
    c = concepts[ex["concepts"][0]]
    v = {k: ex[k] for k in ("id", "concepts", "type", "consigne", "enonce", "indice")}
    v.update(langue=c["langue"], concept=c["titre"],
             blancs=len(ex["reponses"]) if ex["type"] == "trous" else 1)
    if ex["type"] in ("qcm", "choix"):
        v["options"] = random.sample([ex["reponses"][0], *ex["distracteurs"]], 1 + len(ex["distracteurs"]))
    return v


# ── Planification ────────────────────────────────────────────

def cloturer():
    """Répercute sur les concepts les tentatives de séances du jour pas encore comptées."""
    severite = reglages()["accents"]
    par_concept, ids = {}, []
    for t in rows("SELECT t.id, t.resultat, substr(t.date,1,10) jour, x.type, x.concepts FROM tentative t "
                  "JOIN exercice x ON x.id=t.exercice WHERE t.mode='jour' AND t.comptee=0 ORDER BY t.date"):
        ids.append((t["id"],))
        for code in json.loads(t["concepts"]):
            par_concept.setdefault(code, []).append(t)
    for code, ts in par_concept.items():
        langue = code[:2]
        e = con().execute("SELECT * FROM etat_concept WHERE concept=?", (code,)).fetchone()
        n = moteur.sm2(dict(e) if e else {"intervalle": 1, "facilite": 2.5},
                       [moteur.est_faute(t["resultat"], langue, t["type"], severite) for t in ts],
                       all(t["resultat"] == "juste" for t in ts), date.fromisoformat(ts[-1]["jour"]))
        con().execute(
            "INSERT INTO etat_concept (concept, facilite, intervalle, echeance, debut) VALUES (?,?,?,?,?) "
            "ON CONFLICT(concept) DO UPDATE SET facilite=excluded.facilite, intervalle=excluded.intervalle, "
            "echeance=excluded.echeance", (code, n["facilite"], n["intervalle"], n["echeance"], ts[0]["jour"]))
    con().executemany("UPDATE tentative SET comptee=1 WHERE id=?", ids)
    con().commit()


def maj_retrait(id_):
    ts = [(t["date"], t["resultat"]) for t in
          rows("SELECT date, resultat FROM tentative WHERE exercice=? ORDER BY date, id", id_)]
    if moteur.a_retirer(ts):
        con().execute("UPDATE exercice SET statut='retire' WHERE id=? AND statut='actif'", (id_,))


def concepts_du_jour(concepts):
    """Échus (les plus en retard d'abord), puis nouveaux dans la limite quotidienne."""
    jour = aujourd_hui().isoformat()
    dus = sorted((c for c in concepts.values() if c["echeance"] and c["echeance"] <= jour and c["actifs"]),
                 key=lambda c: c["echeance"])
    places = reglages()["nouveaux"] - sum(c["debut"] == jour for c in concepts.values())
    # On alterne les langues pour que les nouveautés ne soient pas toutes anglaises.
    neufs = [[c for c in concepts.values() if not c["echeance"] and c["actifs"] and c["langue"] == l]
             for l in ("es", "en")]
    return dus + moteur.entrelacer(neufs)[:max(0, places)]


def composer(concepts, minutes) -> list:
    du_jour = [c["code"] for c in concepts_du_jour(concepts)]
    retenus, par = moteur.repartir(len(du_jour), round(minutes * 60 / moteur.SECONDES_PAR_EXERCICE))
    codes = moteur.voisins_cote_a_cote(du_jour[:retenus], graphe_voisins(concepts))
    pris, series = set(), []
    for code in codes:
        serie = [x["id"] for x in moteur.tirer(
            candidats(code), par, concepts[code]["acquis"], aujourd_hui(), pris)]
        pris.update(serie)
        series.append(serie)
    return moteur.entrelacer(series)


@app.post("/api/seance")
def seance():
    d = corps()
    mode, code = d.get("mode"), d.get("concept")
    cloturer()
    concepts = concepts_complets()
    if mode == "jour":
        ids = composer(concepts, d["duree"] if d.get("duree") in VALEURS["duree"] else reglages()["duree"])
    elif code not in concepts:
        raise Invalide("Choisir un concept.")
    elif mode == "cible":
        ids = [x["id"] for x in moteur.tirer(candidats(code), 20, concepts[code]["acquis"], aujourd_hui())]
    elif mode == "rafale":
        paire = [code, *sorted(graphe_voisins(concepts)[code])]
        ids = moteur.entrelacer([
            [x["id"] for x in moteur.tirer(candidats(c, ("qcm", "choix")), 40, False, aujourd_hui())] for c in paire])
        ids = list(dict.fromkeys(ids))
    else:
        raise Invalide("Mode inconnu.")
    return jsonify(exercices=[vue_seance(i, concepts) for i in ids])


@app.post("/api/seance/rejouer")
def rejouer():
    """Un exercice neuf par concept raté, pour la fin de séance."""
    d = corps()
    concepts, pris, ids = concepts_complets(), set(d.get("exclus") or []), []
    for code in dict.fromkeys(d.get("concepts") or []):
        if code in concepts:
            # tirer() replie sur du déjà vu quand le réservoir est vide, mais jamais sur la séance en cours
            choix = moteur.tirer(candidats(code), 1, concepts[code]["acquis"], aujourd_hui(), pris)
            ids += [x["id"] for x in choix]
            pris.update(ids)
    return jsonify(exercices=[vue_seance(i, concepts) for i in ids])


@app.post("/api/seance/fin")
def fin():
    cloturer()
    demain = (aujourd_hui() + timedelta(days=1)).isoformat()
    n = con().execute("SELECT COUNT(*) FROM etat_concept WHERE echeance<=?", (demain,)).fetchone()[0]
    return jsonify(demain=n)


@app.post("/api/repondre")
def repondre():
    """Corrige et enregistre. Verdict « à vérifier » : rien n'est enregistré avant la `decision`."""
    d = corps()
    ex = exercice_ou_404(d.get("exercice"))
    donnees, decision, mode = d.get("reponse"), d.get("decision"), d.get("mode")
    if not isinstance(donnees, list) or not all(isinstance(x, str) for x in donnees):
        raise Invalide("Réponse invalide.")
    if mode not in ("jour", "cible", "rafale"):
        raise Invalide("Mode inconnu.")
    concept = con().execute("SELECT * FROM concept WHERE code=?", (ex["concepts"][0],)).fetchone()
    langue = concept["langue"]
    v = correction.corriger(ex, donnees, langue)
    v.update(explication=ex["explication"], regle={"titre": concept["titre"], "fiche": concept["fiche"]})
    if v["resultat"] == "averifier" and decision is None:
        juger(v, ex, dict(concept), donnees)
    if v["resultat"] == "averifier":
        if decision not in ("juste", "faux"):
            return jsonify(v)
        v["resultat"] = decision
        if decision == "juste":
            accepter_variante(ex, donnees, langue)
    if v["resultat"] == "juste" and d.get("aide"):
        v["resultat"] = "aide"
    duree = d.get("duree")
    duree = min(300, max(0, int(duree))) if isinstance(duree, (int, float)) else 0
    v["tentative"] = con().execute(
        "INSERT INTO tentative (exercice, date, mode, reponse, resultat, code_erreur, duree) VALUES (?,?,?,?,?,?,?)",
        (ex["id"], contenu.maintenant(), mode, json.dumps(donnees, ensure_ascii=False), v["resultat"],
         v.get("code_erreur") or code_erreur(v["resultat"], ex["type"]), duree)).lastrowid
    apres_tentative(ex)
    return jsonify(v)


def juger(v, ex, concept, donnees):
    """Étage 3. Sans clé ou hors ligne, le verdict reste « à vérifier » et l'élève tranche."""
    try:
        j = ia.juger(reglages()["cle_api"], ex, concept, " · ".join(donnees))
    except ia.Indisponible as e:
        v["ia_erreur"] = str(e) if ia.disponible(reglages()["cle_api"]) else None
        return
    v["ia"] = {"verdict": j["verdict"], "commentaire": j["commentaire"]}
    # Point visé réussi mais faute ailleurs : compté comme « avec aide », pas comme une faute sur le concept.
    v["resultat"] = {"juste": "juste", "maladroit": "juste", "faute_point": "faux", "faute_ailleurs": "aide"}[j["verdict"]]
    if j["code_erreur"] != "aucun":
        v["code_erreur"] = j["code_erreur"]
    if j["verdict"] == "juste":
        # La variante rejoint les références : la même réponse ne coûtera plus d'appel.
        accepter_variante(ex, donnees, concept["langue"])


def code_erreur(resultat, type_):
    if resultat == "accent":
        return "accent"
    if resultat == "faux":
        return "conjugaison" if type_ == "conjugaison" else "grammaire"
    return None


def apres_tentative(ex):
    maj_retrait(ex["id"])
    con().commit()


def accepter_variante(ex, donnees, langue):
    """Ajoute la réponse donnée aux réponses acceptées, blanc par blanc."""
    listes = ex["reponses"] if ex["type"] == "trous" else [ex["reponses"]]
    for liste, donne in zip(listes, donnees):
        if donne.strip() and correction.comparer(donne, liste, langue, ex["type"], "")["resultat"] != "juste":
            liste.append(donne.strip())
    con().execute("UPDATE exercice SET reponses=? WHERE id=?",
                  (json.dumps(ex["reponses"], ensure_ascii=False), ex["id"]))


@app.post("/api/tentatives/<int:id_>/juste")
def j_avais_raison(id_):
    t = con().execute("SELECT * FROM tentative WHERE id=?", (id_,)).fetchone() or abort(404)
    ex = exercice_ou_404(t["exercice"])
    if ex["type"] not in ("qcm", "choix"):
        accepter_variante(ex, json.loads(t["reponse"]), ex["concepts"][0][:2])
    con().execute("UPDATE tentative SET resultat='juste', code_erreur=NULL WHERE id=?", (id_,))
    apres_tentative(ex)
    return jsonify(ok=True)


# ── Accueil ──────────────────────────────────────────────────

@app.get("/api/accueil")
def accueil():
    cloturer()
    concepts = concepts_complets()
    dus = {"en": 0, "es": 0}
    for c in concepts_du_jour(concepts):
        dus[c["langue"]] += min(4, c["actifs"])
    commences = [c for c in concepts.values() if c["vu"]]
    bas = [c for c in commences if c["non_vus"] < moteur.SEUIL_RESERVOIR]
    jours = {r["j"] for r in rows("SELECT DISTINCT substr(date,1,10) j FROM tentative")}
    champs = ("code", "langue", "titre", "maitrise", "non_vus")
    return jsonify(
        dus=dus, serie=moteur.serie(jours, aujourd_hui()), duree=reglages()["duree"],
        faibles=[{k: c[k] for k in champs} for c in sorted(commences, key=lambda c: c["maitrise"])
                 if not c["acquis"]][:3],
        reservoirs=[{k: c[k] for k in champs} for c in sorted(bas, key=lambda c: c["non_vus"])[:3]],
        a_valider=con().execute("SELECT COUNT(*) FROM exercice WHERE statut='a_valider'").fetchone()[0])


# ── Bibliothèque ─────────────────────────────────────────────

@app.get("/api/concepts")
def liste_concepts():
    concepts = concepts_complets()
    v = graphe_voisins(concepts)
    return jsonify([{**c, "voisins": sorted(v[code])} for code, c in concepts.items()])


@app.post("/api/concepts")
def creer_concept():
    c = contenu.valider_concept(corps())
    if c["code"] in contenu.langues(con()):
        raise Invalide("Ce concept existe déjà.")
    contenu.inserer_concept(con(), c)
    con().commit()
    return jsonify(code=c["code"]), 201


@app.patch("/api/concepts/<code>")
def modifier_concept(code):
    fiche = corps().get("fiche")
    if not isinstance(fiche, str):
        raise Invalide("Fiche invalide.")
    if not con().execute("UPDATE concept SET fiche=? WHERE code=?", (fiche.strip(), code)).rowcount:
        abort(404, "Concept introuvable.")
    con().commit()
    return jsonify(ok=True)


def texte_prompt(code):
    d = corps()
    c = con().execute("SELECT * FROM concept WHERE code=?", (code,)).fetchone() or abort(404)
    types = [t for t in contenu.TYPES if t in (d.get("types") or [])]
    if not types or d.get("nombre") not in (5, 10, 20) or d.get("difficulte") not in (1, 2, 3):
        raise Invalide("Choisir un nombre, au moins un type et une difficulté.")
    existants = [r["enonce"] for r in rows("SELECT enonce FROM exercice x WHERE EXISTS "
                                           "(SELECT 1 FROM json_each(x.concepts) WHERE value=?)", code)]
    return contenu.prompt(dict(c), existants, d["nombre"], types, d["difficulte"])


@app.post("/api/concepts/<code>/prompt")
def prompt(code):
    return jsonify(prompt=texte_prompt(code))


@app.post("/api/concepts/<code>/generer")
def generer(code):
    """Génération directe par Claude ; les exercices arrivent dans « À valider »."""
    texte = texte_prompt(code)
    try:
        exercices = ia.generer(reglages()["cle_api"], texte)
    except ia.Indisponible as e:
        return jsonify(erreur=str(e)), 503
    bilan = contenu.importer(con(), exercices, "ia")
    con().commit()
    return jsonify(bilan)


@app.get("/api/exercices")
def liste_exercices():
    sql = "SELECT x.*, (SELECT MAX(date) FROM tentative t WHERE t.exercice=x.id) vu FROM exercice x WHERE 1"
    params = []
    if request.args.get("concept"):
        sql += " AND EXISTS (SELECT 1 FROM json_each(x.concepts) WHERE value=?)"
        params.append(request.args["concept"])
    if request.args.get("statut"):
        sql += " AND x.statut=?"
        params.append(request.args["statut"])
    return jsonify([contenu.ligne(r) for r in rows(sql + " ORDER BY x.id DESC", *params)])


def exercice_du_corps(sauf=None):
    ex = contenu.valider(corps(), contenu.langues(con()))
    id_ = contenu.doublon(con(), ex["empreinte"], sauf)
    return ex, id_


@app.post("/api/exercices")
def creer_exercice():
    ex, double = exercice_du_corps()
    if double:
        return jsonify(erreur="Un exercice presque identique existe déjà.", doublon=double), 409
    id_ = contenu.inserer(con(), ex, "manuel", "actif")
    con().commit()
    return jsonify(id=id_), 201


@app.put("/api/exercices/<int:id_>")
def modifier_exercice(id_):
    exercice_ou_404(id_)
    ex, double = exercice_du_corps(sauf=id_)
    if double:
        return jsonify(erreur="Un exercice presque identique existe déjà.", doublon=double), 409
    contenu.modifier(con(), id_, ex)
    if "statut" in corps():
        changer_statut([id_], corps()["statut"])
    con().commit()
    return jsonify(id=id_)


def changer_statut(ids, statut):
    if statut not in contenu.STATUTS:
        raise Invalide("Statut inconnu.")
    con().executemany("UPDATE exercice SET statut=? WHERE id=?", [(statut, i) for i in ids])


@app.post("/api/exercices/statut")
def statut_lot():
    d = corps()
    ids = d.get("ids")
    if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
        raise Invalide("Liste d'exercices attendue.")
    changer_statut(ids, d.get("statut"))
    con().commit()
    return jsonify(ok=True)


@app.delete("/api/exercices/<int:id_>")
def supprimer_exercice(id_):
    """Efface, ou archive si des tentatives s'y rattachent (les statistiques restent justes)."""
    exercice_ou_404(id_)
    if rows("SELECT 1 FROM tentative WHERE exercice=? LIMIT 1", id_):
        changer_statut([id_], "archive")
    else:
        con().execute("DELETE FROM exercice WHERE id=?", (id_,))
    con().commit()
    return jsonify(ok=True)


@app.post("/api/import")
def importer():
    d = corps()
    source = d.get("source", "import")
    if source not in ("import", "ia", "mcp"):
        raise Invalide("Source inconnue.")
    bilan = contenu.importer(con(), d.get("donnees"), source)
    con().commit()
    return jsonify(bilan)


@app.get("/api/export")
def exporter():
    tables = {"concepts": "concept", "exercices": "exercice", "tentatives": "tentative",
              "etats": "etat_concept", "reglages": "reglage"}
    out = {cle: [dict(r) for r in rows(f"SELECT * FROM {t}")] for cle, t in tables.items()}
    out["exercices"] = [contenu.ligne(e) for e in out["exercices"]]
    out["reglages"] = [r for r in out["reglages"] if r["cle"] != "cle_api"]   # la clé ne quitte pas la machine
    for c in out["concepts"]:
        c["voisins"] = json.loads(c["voisins"])
    rep = jsonify(out)
    rep.headers["Content-Disposition"] = f"attachment; filename=gramgen-{aujourd_hui().isoformat()}.json"
    return rep


# ── Statistiques ─────────────────────────────────────────────

@app.get("/api/stats")
def stats():
    periode, langue = request.args.get("periode", "7"), request.args.get("langue", "tout")
    jour, severite = aujourd_hui(), reglages()["accents"]
    lundi = jour - timedelta(days=jour.weekday())
    toutes = []
    for t in rows("SELECT t.date, t.resultat, t.duree, x.type, x.concepts, c.titre FROM tentative t "
                  "JOIN exercice x ON x.id=t.exercice JOIN concept c ON c.code = json_extract(x.concepts, '$[0]')"):
        l = json.loads(t["concepts"])[0][:2]
        if langue in ("tout", l):
            toutes.append({**dict(t), "langue": l, "jour": date.fromisoformat(t["date"][:10]),
                           "score": moteur.score(t["resultat"], moteur.est_faute(t["resultat"], l, t["type"], severite))})
    debut = {"7": jour - timedelta(days=6), "30": jour - timedelta(days=29)}.get(periode, date.min)
    dans = [t for t in toutes if t["jour"] >= debut]

    def pourcent(ts):
        return round(100 * sum(t["score"] for t in ts) / len(ts)) if ts else None

    def semaine(t):   # 0 = cette semaine
        return (lundi - (t["jour"] - timedelta(days=t["jour"].weekday()))).days // 7

    types = [{"nom": nom, "p": pourcent(ts)} for cle, nom in contenu.TYPES.items()
             if (ts := [t for t in dans if t["type"] == cle])]
    fautes = {}
    for t in toutes:
        if t["resultat"] in ("faux", "accent") and semaine(t) < 8:
            # Sans jugement IA, le point fautif est le concept de l'exercice ; seul l'accent a son code propre.
            nom = "Accent" if t["resultat"] == "accent" else t["titre"]
            f = fautes.setdefault(nom, {"nom": nom, "langues": set(), "semaines": [0] * 8})
            f["langues"].add(t["langue"].upper())
            f["semaines"][7 - semaine(t)] += 1
    fautes = sorted(({**f, "langues": " · ".join(sorted(f["langues"])), "n": sum(f["semaines"])}
                     for f in fautes.values()), key=lambda f: -f["n"])[:6]
    temps = [0] * 12
    for t in toutes:
        if semaine(t) < 12:
            temps[11 - semaine(t)] += t["duree"]
    return jsonify(
        secondes=sum(t["duree"] for t in dans), faits=len(dans), reussite=pourcent(dans),
        serie=moteur.serie({t["date"][:10] for t in toutes}, jour), types=sorted(types, key=lambda t: -t["p"]),
        fautes=fautes, temps=temps,
        concepts=[{k: c[k] for k in ("code", "langue", "titre", "categorie", "maitrise", "vu")}
                  for c in concepts_complets().values() if langue in ("tout", c["langue"])])


# ── Réglages et page ─────────────────────────────────────────

@app.get("/api/reglages")
def lire_reglages():
    r = reglages()
    cle = r.pop("cle_api")
    return jsonify(**r, ia=ia.disponible(cle), cle_api=bool(cle), version=updater.version_locale(), dossier=str(db.data_dir()),
                   sauvegardes=len(list((db.data_dir() / "sauvegardes").glob("gramgen-*.db"))))


@app.patch("/api/reglages")
def ecrire_reglages():
    for cle, valeur in corps().items():
        if cle == "cle_api" and isinstance(valeur, str) and len(valeur) < 300:
            valeur = valeur.strip()
        elif cle not in VALEURS or valeur not in VALEURS[cle]:
            raise Invalide(f"Réglage invalide : {cle}.")
        con().execute("INSERT OR REPLACE INTO reglage VALUES (?,?)", (cle, json.dumps(valeur)))
    con().commit()
    return lire_reglages()


# ── Mise à jour ──────────────────────────────────────────────

@app.get("/api/maj")
def maj_verifier():
    return jsonify(updater.verifier())


@app.post("/api/maj")
def maj_telecharger():
    corps()     # exige application/json, comme toute écriture
    return jsonify(updater.telecharger())


@app.post("/api/maj/installateur")
def maj_installateur():
    corps()
    webbrowser.open(updater.PAGE_INSTALLATEUR)
    return jsonify(ok=True)


@app.get("/")
def index():
    return render_template("index.html", theme=reglages()["theme"], types=contenu.TYPES,
                           consignes=contenu.CONSIGNES)
