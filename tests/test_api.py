"""Boucle complète sur une base temporaire : importer → valider → réviser → mesurer."""

import os
import tempfile
import time
import unittest
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import app as web
import contenu
import correction
import db


class Api(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, GRAMGEN_DATA=self.tmp.name)
        self.env.start()
        db.initialiser()
        self.c = web.app.test_client()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def post(self, url, **d):
        return self.c.post(url, json=d)

    def test_contenu_de_depart_se_corrige_juste(self):
        exs = self.c.get("/api/exercices").json
        self.assertEqual(len(exs), 720)
        for c in self.c.get("/api/concepts").json:
            self.assertGreaterEqual(c["actifs"], 30, c["code"])
        for ex in exs:
            rep = [r[0] for r in ex["reponses"]] if ex["type"] == "trous" else ex["reponses"][:1]
            for forme in (rep, [r.upper()[:1] + r[1:].rstrip(".") for r in rep], [r.replace("'", "’") for r in rep]):
                self.assertEqual(correction.corriger(ex, forme, ex["concepts"][0][:2])["resultat"], "juste", ex)

    def test_seance_complete(self):
        s = self.post("/api/seance", mode="jour", duree=15).json["exercices"]
        self.assertEqual(len({e["concepts"][0] for e in s}), 2)             # 2 nouveaux par jour
        self.assertEqual({e["langue"] for e in s}, {"en", "es"})
        self.assertNotIn("reponses", s[0])
        par_id = {e["id"]: e for e in self.c.get("/api/exercices").json}
        rate = s[0]["concepts"][0]
        for e in s:
            r = par_id[e["id"]]["reponses"]
            bonne = [x[0] for x in r] if e["type"] == "trous" else r[:1]
            v = self.post("/api/repondre", exercice=e["id"], mode="jour", duree=12,
                          reponse=["zzz"] if e["concepts"][0] == rate else bonne, decision="faux").json
            self.assertEqual(v["resultat"], "faux" if e["concepts"][0] == rate else "juste")
        neuf = self.post("/api/seance/rejouer", concepts=[rate], exclus=[e["id"] for e in s]).json["exercices"]
        self.assertEqual(len(neuf), 1)
        self.assertNotIn(neuf[0]["id"], {e["id"] for e in s})
        self.assertEqual(self.post("/api/seance/fin").json["demain"], 1)
        etats = {c["code"]: c for c in self.c.get("/api/concepts").json if c["echeance"]}
        demain = date.today() + timedelta(days=1)
        self.assertEqual(etats.pop(rate)["echeance"], demain.isoformat())
        (reussi,) = etats.values()
        self.assertEqual(reussi["echeance"], (date.today() + timedelta(days=3)).isoformat())
        self.assertEqual(reussi["maitrise"], 100)
        # Plus rien aujourd'hui ; demain, aucun exercice déjà vu.
        self.assertEqual(self.post("/api/seance", mode="jour", duree=15).json["exercices"], [])
        with mock.patch.object(web, "aujourd_hui", return_value=demain):
            vus = {e["id"] for e in s}
            suite = self.post("/api/seance", mode="jour", duree=15).json["exercices"]
            self.assertTrue(suite and not vus & {e["id"] for e in suite})

    def test_cible_navance_pas_les_intervalles(self):
        e = self.post("/api/seance", mode="cible", concept="es.por-para").json["exercices"][0]
        self.post("/api/repondre", exercice=e["id"], mode="cible", reponse=["zzz"], decision="faux")
        self.post("/api/seance/fin")
        self.assertFalse(any(c["echeance"] for c in self.c.get("/api/concepts").json))
        self.assertTrue(self.post("/api/seance", mode="rafale", concept="es.por-para").json["exercices"])

    def test_a_verifier_puis_accepte(self):
        ex = next(e for e in self.c.get("/api/exercices").json if e["type"] == "theme")
        d = dict(exercice=ex["id"], mode="jour", reponse=["Une autre version"])
        self.assertEqual(self.post("/api/repondre", **d).json["resultat"], "averifier")
        self.assertEqual(self.c.get("/api/stats").json["faits"], 0)
        self.assertEqual(self.post("/api/repondre", **d, decision="juste").json["resultat"], "juste")
        self.assertEqual(self.post("/api/repondre", **d).json["resultat"], "juste")     # variante apprise

    def test_j_avais_raison(self):
        ex = next(e for e in self.c.get("/api/exercices").json if e["type"] == "trous")
        d = dict(exercice=ex["id"], mode="jour", reponse=["variante"])
        v = self.post("/api/repondre", **d).json
        self.assertEqual(v["resultat"], "faux")
        self.post(f"/api/tentatives/{v['tentative']}/juste")
        self.assertEqual(self.post("/api/repondre", **d).json["resultat"], "juste")
        self.assertEqual(self.c.get("/api/stats").json["fautes"], [])

    def test_import_doublons_et_erreurs(self):
        lot = [{"concepts": ["es.depuis"], "type": "theme", "enonce": f"Phrase numéro {i}.", "reponses": ["x"]}
               for i in range(50)]
        t = time.time()
        b = self.post("/api/import", donnees=lot + [dict(lot[0], enonce="phrase NUMÉRO 0 !"),
                                                    {"concepts": ["es.rien"], "type": "theme"}, 3]).json
        self.assertLess(time.time() - t, 10)
        self.assertEqual((b["ajoutes"], len(b["doublons"]), len(b["erreurs"])), (50, 1, 2))
        self.assertEqual(self.c.get("/api/accueil").json["a_valider"], 50)
        self.assertNotIn("à valider", [e["statut"] for e in self.post(
            "/api/seance", mode="cible", concept="es.depuis").json["exercices"] if "statut" in e])
        self.assertEqual(self.post("/api/import", donnees="non").status_code, 400)

    def test_validation_des_entrees(self):
        k = {"es.depuis": "es", "en.passif": "en"}
        ok = {"concepts": ["es.depuis"], "type": "trous", "enonce": "Vivo {{1}} aquí {{2}}.", "reponses": ["a", "b"]}
        self.assertEqual(contenu.valider(ok, k)["reponses"], [["a"], ["b"]])
        for faux in ({"reponses": ["a"]}, {"enonce": "Sans blanc"}, {"enonce": "{{2}} {{1}}"}, {"concepts": []},
                     {"concepts": ["es.depuis", "en.passif"]}, {"type": []}, {"difficulte": 9}, {"enonce": " ! "},
                     {"type": "qcm", "distracteurs": []}, {"reponses": [["a"], [3]]}, {"indice": 3}):
            with self.assertRaises(contenu.Invalide, msg=faux):
                contenu.valider({**ok, **faux}, k)

    def test_contenu_importe_une_seule_fois(self):
        ids = [e["id"] for e in self.c.get("/api/exercices").json]
        self.c.delete(f"/api/exercices/{ids[0]}")
        db.initialiser()
        self.assertEqual(len(self.c.get("/api/exercices").json), 719)
        # Base d'avant le registre : elle reçoit les nouveaux fichiers, pas les anciens.
        with closing(db.connecter()) as con:
            con.execute("DELETE FROM reglage")
            con.execute("DELETE FROM exercice WHERE id IN (SELECT id FROM exercice ORDER BY id DESC LIMIT 479)")
            con.execute("DELETE FROM exercice WHERE id = 1")
            con.commit()
        db.initialiser()
        self.assertEqual(len(self.c.get("/api/exercices").json), 719)

    def test_doublon_a_la_main_et_suppression(self):
        ex = {"concepts": ["es.depuis"], "type": "theme", "enonce": "Il pleut.", "reponses": ["Llueve."]}
        id_ = self.post("/api/exercices", **ex).json["id"]
        self.assertEqual(self.post("/api/exercices", **ex).status_code, 409)
        self.assertEqual(self.c.put(f"/api/exercices/{id_}", json={**ex, "statut": "a_valider"}).status_code, 200)
        self.post("/api/repondre", exercice=id_, mode="cible", reponse=["llueve"])
        self.c.delete(f"/api/exercices/{id_}")                                          # archivé, pas effacé
        self.assertIn(id_, [e["id"] for e in self.c.get("/api/exercices?statut=archive").json])

    def test_export_sauvegarde_hote(self):
        self.assertEqual(len(self.c.get("/api/export").json["exercices"]), 720)
        db.initialiser()
        self.assertEqual(len(list((Path(self.tmp.name) / "sauvegardes").glob("*.db"))), 1)
        self.assertEqual(self.c.get("/", headers={"Host": "pirate.test"}).status_code, 403)
        self.assertEqual(self.c.patch("/api/reglages", json={"accents": "x"}).status_code, 400)
        p = self.post("/api/concepts/es.depuis/prompt", nombre=10, types=["theme"], difficulte=2).json["prompt"]
        self.assertIn("es.depuis", p)


if __name__ == "__main__":
    unittest.main()
