"""Mise à jour : une erreur ici casse l'installation, d'où les chemins d'échec."""

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import updater

RACINE = Path(__file__).resolve().parent.parent


def code(dossier, version, commit="c", runtime=1):
    dossier = Path(dossier)
    dossier.mkdir(parents=True)
    (dossier / "app.py").write_text(version, encoding="utf-8")
    (dossier / "version.json").write_text(json.dumps(
        {"version": version, "commit": commit, "requires_runtime": runtime}), encoding="utf-8")
    return dossier


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = Path(tmp.name)
        self.live = self.d / "app"

    def version(self):
        return (self.live / "app.py").read_text(encoding="utf-8")


class Demarrage(Base):
    def test_versions(self):
        self.assertTrue(updater.plus_recent("1.10.0", "1.9.0"))
        for a, b in (("1.0.0", "1.0.0"), ("0.9.0", "1.0.0"), ("", "1.0.0"), ("1.0.0-beta", "0.1.0"),
                     ("2.0.0", "développement"), (None, "1.0.0")):
            self.assertFalse(updater.plus_recent(a, b), (a, b))

    def test_deploiement(self):
        b = code(self.d / "b", "0.2.0")
        self.assertTrue(updater.deployer(b, self.live))                     # première fois
        self.assertFalse(updater.deployer(b, self.live))                    # rien de neuf
        (b / "version.json").write_text('{"version": "0.2.0", "commit": "autre"}')
        self.assertTrue(updater.deployer(b, self.live))                     # exe reconstruit
        (self.live / "version.json").write_text('{"version": "0.3.0"}')
        self.assertFalse(updater.deployer(b, self.live))                    # code mis à jour : on le garde
        (self.live / "app.py").unlink()
        self.assertTrue(updater.deployer(b, self.live))                     # dossier abîmé : réparé

    def test_application(self):
        code(self.live, "0.2.0")
        self.assertFalse(updater.appliquer(self.live, 1))
        code(self.d / "app_staged", "0.3.0")
        self.assertTrue(updater.appliquer(self.live, 1))
        self.assertEqual(self.version(), "0.3.0")
        self.assertEqual([p.name for p in self.d.iterdir()], ["app"])       # ni reste ni copie

    def test_attente_refusee(self):
        code(self.live, "0.2.0")
        for version, runtime in (("0.3.0", 2), ("0.1.0", 1), ("0.2.0", 1), ("illisible", 1)):
            code(self.d / "app_staged", version, runtime=runtime)
            self.assertFalse(updater.appliquer(self.live, 1))
            self.assertFalse((self.d / "app_staged").exists())
            self.assertEqual(self.version(), "0.2.0")

    def test_echange_interrompu_restaure_l_ancien(self):
        code(self.live, "0.2.0")
        code(self.d / "app_staged", "0.3.0")
        vrai = os.rename

        def rename(a, b):
            if Path(a).name == "app_staged":
                raise OSError("verrouillé")
            vrai(a, b)
        with mock.patch.object(updater.os, "rename", rename), self.assertRaises(OSError):
            updater.appliquer(self.live, 1)
        self.assertEqual(self.version(), "0.2.0")
        self.assertTrue(updater.appliquer(self.live, 1))                    # retenté au démarrage suivant


class Telechargement(Base):
    def setUp(self):
        super().setUp()
        ici = code(self.d / "ici", "0.2.0")
        for p in (mock.patch.object(updater, "ICI", ici), mock.patch.object(updater, "_live", lambda: self.live),
                  mock.patch.dict(os.environ, GRAMGEN_RUNTIME="1"), mock.patch.object(updater, "_get", self.get)):
            p.start()
            self.addCleanup(p.stop)
        self.publier("0.3.0")

    def publier(self, version, runtime=1, dans_zip=None, digest=None):
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w") as z:
            z.writestr("app/app.py", version)
            z.writestr("app/version.json", json.dumps({"version": dans_zip or version}))
        self.zip = tampon.getvalue()
        self.urls = {
            updater.RELEASE_URL: json.dumps({"assets": [
                {"name": "version.json", "browser_download_url": "v"},
                {"name": "app.zip", "browser_download_url": "z",
                 "digest": "sha256:" + (digest or hashlib.sha256(self.zip).hexdigest())}]}).encode(),
            "v": json.dumps({"version": version, "requires_runtime": runtime}).encode(), "z": self.zip}

    def get(self, url, delai):
        if url not in self.urls:
            raise updater.URLError("hors ligne")
        return self.urls[url]

    def test_nominal(self):
        self.assertEqual(updater.verifier(), {"etat": "disponible", "version": "0.3.0"})
        self.assertEqual(updater.telecharger(), {"etat": "prete", "version": "0.3.0"})
        self.urls = {}                                                      # prête même hors ligne
        self.assertEqual(updater.verifier()["etat"], "prete")
        self.assertTrue(updater.appliquer(self.live, 1))
        self.assertEqual(self.version(), "0.3.0")

    def test_rien_a_faire(self):
        self.publier("0.2.0")
        self.assertEqual(updater.telecharger()["etat"], "a_jour")
        self.publier("0.3.0", runtime=2)
        self.assertEqual(updater.telecharger()["etat"], "installateur")
        self.urls = {}
        self.assertEqual(updater.verifier()["etat"], "erreur")
        with mock.patch.dict(os.environ, GRAMGEN_RUNTIME=""):
            self.assertEqual(updater.verifier()["etat"], "developpement")

    def test_archive_douteuse_jamais_preparee(self):
        for k in ({"digest": "0" * 64}, {"dans_zip": "0.2.9"}):
            self.publier("0.3.0", **k)
            self.assertEqual(updater.telecharger()["etat"], "erreur", k)
            self.assertFalse((self.d / "app_staged").exists())
        self.publier("0.3.0")
        self.urls["z"] = b"pas un zip"
        self.assertEqual(updater.telecharger()["etat"], "erreur")


class Contrat(unittest.TestCase):
    def test_runtime_couvre_les_dependances(self):
        r = subprocess.run([sys.executable, "scripts/runtime_contract.py", "--check"], cwd=RACINE,
                           capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_le_code_livre_se_verifie(self):
        with tempfile.TemporaryDirectory() as tmp:
            lancer = lambda *a: subprocess.run([sys.executable, *a], cwd=RACINE, capture_output=True, text=True)
            self.assertEqual(lancer("scripts/build_payload.py", f"{tmp}/app").returncode, 0)
            r = lancer("launcher.py", "--self-check", "--app-dir", f"{tmp}/app")
            self.assertEqual(r.returncode, 0, r.stderr)
            m = Path(tmp, "app/version.json")
            m.write_text('{"version": "9.0.0", "requires_runtime": 99}')
            self.assertEqual(lancer("launcher.py", "--self-check", "--app-dir", f"{tmp}/app").returncode, 3)
            m.unlink()
            Path(tmp, "app/moteur.py").unlink()
            self.assertEqual(lancer("launcher.py", "--self-check", "--app-dir", f"{tmp}/app").returncode, 1)


if __name__ == "__main__":
    unittest.main()
