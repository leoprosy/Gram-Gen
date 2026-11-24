"""Planificateur : SM-2, tirage, retrait."""

import unittest
from datetime import date

import moteur as m

J = date(2026, 11, 24)
NEUF = {"intervalle": 1, "facilite": 2.5}


class Moteur(unittest.TestCase):
    def test_sm2(self):
        self.assertEqual(m.sm2(NEUF, [False], True, J),
                         {"intervalle": 2.5, "facilite": 2.5, "echeance": "2026-11-27"})
        self.assertEqual(m.sm2({"intervalle": 10, "facilite": 2.5}, [False], False, J)["echeance"], "2026-12-06")
        rate = m.sm2({"intervalle": 30, "facilite": 1.4}, [False, True], False, J)
        self.assertEqual((rate["intervalle"], rate["facilite"], rate["echeance"]), (1.0, 1.3, "2026-11-25"))

    def test_accent_selon_langue_type_et_reglage(self):
        self.assertTrue(m.est_faute("accent", "es", "trous"))
        self.assertFalse(m.est_faute("accent", "es", "trous", "demi"))
        self.assertTrue(m.est_faute("accent", "es", "conjugaison", "demi"))
        self.assertFalse(m.est_faute("accent", "en", "trous"))

    def test_maitrise_ponderee_vers_le_recent(self):
        self.assertEqual(m.maitrise([]), 0)
        self.assertEqual(m.maitrise([1] * 5), 100)
        self.assertGreater(m.maitrise([0, 1]), m.maitrise([1, 0]))
        self.assertEqual(m.maitrise([0] * 10 + [1] * 20), 100)

    def test_retrait(self):
        self.assertTrue(m.a_retirer([("2026-11-01T10:00:00", "juste"), ("2026-11-08T10:00:00", "juste")]))
        self.assertFalse(m.a_retirer([("2026-11-01T10:00:00", "juste"), ("2026-11-08T09:59:00", "juste")]))
        self.assertFalse(m.a_retirer([("2026-11-01T10:00:00", "juste"), ("2026-11-10T10:00:00", "aide")]))

    def test_tirage_jamais_vus_dabord_et_repos_de_14_jours(self):
        c = [{"id": 1, "type": "qcm", "vu": "2026-11-20T08:00:00"}, {"id": 2, "type": "qcm", "vu": None},
             {"id": 3, "type": "trous", "vu": "2026-11-01T08:00:00"}]
        self.assertEqual([x["id"] for x in m.tirer(c, 3, False, J)], [2, 3])
        self.assertEqual([x["id"] for x in m.tirer(c[:1], 2, False, J)], [1])       # réservoir épuisé
        self.assertEqual([x["id"] for x in m.tirer(c, 3, False, J, exclus={2})], [3])

    def test_tirage_varie_les_types_et_passe_a_lecrit(self):
        c = [{"id": i, "type": t, "vu": None} for i, t in enumerate(["qcm", "qcm", "trous", "trous"])]
        self.assertEqual([x["type"] for x in m.tirer(c, 2, False, J)], ["qcm", "trous"])
        self.assertEqual([x["type"] for x in m.tirer(c, 2, True, J)], ["trous", "qcm"])

    def test_budget(self):
        for nb in range(1, 30):
            for budget in (15, 22, 37):
                k, par = m.repartir(nb, budget)
                self.assertTrue(2 <= par <= 4 and k * par <= budget, (nb, budget))

    def test_entrelacement_et_voisins(self):
        self.assertEqual(m.entrelacer([[1, 2, 3], ["a"]]), [1, "a", 2, 3])
        self.assertEqual(m.voisins_cote_a_cote(["a", "b", "c"], {"a": ["c"]}), ["a", "c", "b"])

    def test_serie(self):
        self.assertEqual(m.serie({"2026-11-23", "2026-11-22", "2026-11-20"}, J), 2)
        self.assertEqual(m.serie({"2026-11-24", "2026-11-23"}, J), 2)
        self.assertEqual(m.serie(set(), J), 0)


if __name__ == "__main__":
    unittest.main()
