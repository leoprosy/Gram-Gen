"""Normalisation et verdicts. Lancer : python -m unittest discover -s tests -t ."""

import unittest

from correction import corriger


def verdict(reponses, donne, langue="es", type_="theme", enonce="x"):
    donne = donne if isinstance(donne, list) else [donne]
    return corriger({"type": type_, "reponses": reponses, "enonce": enonce}, donne, langue)


class Correction(unittest.TestCase):
    def res(self, attendu, *a, **k):
        self.assertEqual(verdict(*a, **k)["resultat"], attendu, (a, k))

    def test_normalisation(self):
        for r in ("hace tres años que vive en Madrid", "Hace  tres años que vive en Madrid.",
                  " « Hace tres años que vive en Madrid. » ", "Hace tres años que vive en Madrid…"):
            self.res("juste", ["Hace tres años que vive en Madrid."], r)

    def test_apostrophe_et_contractions(self):
        for r in ("I don’t know.", "I don't know", "i do not know"):
            self.res("juste", ["I do not know."], r, "en")
        self.res("juste", ["She has been working."], "She's been working", "en")
        self.res("juste", ["He is tired."], "he's tired", "en")
        self.res("juste", ["I'd have come."], "I would have come", "en")
        self.res("juste", ["You can not leave."], "You can't leave", "en")
        self.res("juste", ["John's car is red."], "John's car's red", "en")
        self.res("averifier", ["It is raining."], "It has raining", "en")
        self.res("averifier", ["It's raining."], "It has raining", "en")
        self.res("averifier", ["I had better go."], "I would better go", "en")

    def test_accent(self):
        v = verdict(["Está viviendo en Madrid."], "Esta viviendo en Madrid")
        self.assertEqual(v["resultat"], "accent")
        self.assertEqual(v["accents"], [["esta", "está"]])
        self.res("accent", ["volvió"], "volvio", type_="conjugaison")
        self.res("accent", ["España"], "Espana")
        self.res("accent", ["tomo"], "tomó", type_="conjugaison")

    def test_faux_ou_a_verifier(self):
        self.res("faux", [["llegue"]], "llega", type_="trous")
        self.res("faux", ["going"], "to go", "en", "qcm")
        self.res("faux", [["llegue"]], "", type_="trous")
        self.res("averifier", ["Lleva tres años aquí."], "Él lleva tres años aquí.")

    def test_coquille_seulement_hors_du_mot_vise(self):
        e = "She said: I am tired."
        v = verdict(["She said she was tired."], "She said she was tird.", "en", "transformation", e)
        self.assertEqual((v["resultat"], v["coquille"]["attendu"]), ("juste", "tired"))
        self.res("averifier", ["She said she was tired."], "She said she wes tired.", "en", "transformation", e)
        self.res("faux", [["pienso"]], "penso", type_="trous", enonce="Yo {{1}}. (pensar)")

    def test_plusieurs_blancs(self):
        r = [["had known"], ["would have come"]]
        self.res("juste", r, ["had known", "'d have come"], "en", "trous")
        self.res("faux", r, ["had known"], "en", "trous")

    def test_diff_et_reference_la_plus_proche(self):
        v = verdict(["Lleva tres años viviendo en Madrid.", "Hace tres años que vive en Madrid."],
                    "Hacía tres años que vivía en Madrid.")
        self.assertEqual(v["reference"], "Hace tres años que vive en Madrid.")
        self.assertEqual([m for m, d in v["diff_donne"] if d], ["Hacía", "vivía"])
        self.assertEqual([m for m, d in v["diff_attendu"] if d], ["Hace", "vive"])


if __name__ == "__main__":
    unittest.main()
