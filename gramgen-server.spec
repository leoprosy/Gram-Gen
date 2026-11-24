# -*- mode: python ; coding: utf-8 -*-
# Le code de l'app est embarqué comme données (app_bundle, voir scripts/build_payload.py) et non figé :
# launcher.py le déploie dans le dossier de données, où app.zip peut le remplacer. D'où la bibliothèque
# standard et les dépendances entières dans l'exécutable (scripts/runtime_contract.py).
import os
import sys

sys.path.insert(0, os.path.join(SPECPATH, "scripts"))
from runtime_contract import runtime_import_names, stdlib_modules  # noqa: E402
from PyInstaller.utils.hooks import collect_submodules  # noqa: E402

caches = list(stdlib_modules())
for paquet in runtime_import_names():
    caches += collect_submodules(paquet, on_error="ignore",
                                 filter=lambda n: not {"test", "tests", "testing"} & set(n.split(".")[1:]) or n == "flask.testing")

a = Analysis(
    ["launcher.py"],
    datas=[("build/app_bundle", "app_bundle"), ("runtime.json", ".")],
    hiddenimports=caches,
    excludes=["app", "contenu", "correction", "db", "moteur", "updater"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="gramgen-server", console=True, upx=False)
