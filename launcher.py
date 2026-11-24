"""
Point d'entrée : `python launcher.py` (navigateur) ou sidecar Tauri (GRAMGEN_SIDECAR=1).

Dans l'exécutable, ce fichier est figé : il met le code à jour puis le charge depuis <données>/app.
Son contrat avec ce code : `updater.deployer`, `updater.appliquer`, `db.initialiser` et `app.app`.
Les modules de l'app passent par import_module pour ne pas être figés eux aussi.
"""

import json
import os
import socket
import sys
import tempfile
import threading
import traceback
import webbrowser
from importlib import import_module
from pathlib import Path

from waitress import serve

GELE = getattr(sys, "frozen", False)
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)).resolve()
EMBARQUE = BASE / "app_bundle" if GELE else BASE


def runtime() -> int:
    try:
        return int(json.loads((BASE / "runtime.json").read_text(encoding="utf-8"))["runtime"])
    except (OSError, ValueError, KeyError, TypeError):
        return 0


def choisir(dossier: Path):
    """Les prochains imports de modules de l'app viendront de `dossier`, et de lui seul."""
    codes = {str(EMBARQUE), str(Path(os.environ.get("GRAMGEN_DATA", "")) / "app"), str(dossier)}
    for nom, module in list(sys.modules.items()):
        fichier = getattr(module, "__file__", None)
        if nom != "__main__" and fichier and str(Path(fichier).parent) in codes:
            del sys.modules[nom]
    sys.path[:] = [str(dossier), *(p for p in sys.path if p not in codes)]


def charger(dossier: Path):
    choisir(dossier)
    import_module("db").initialiser()
    return import_module("app").app


def auto_verification(dossier: Path) -> int:
    """Ce runtime fait-il tourner le code de `dossier` ? 0 oui, 1 non, 3 runtime trop ancien (voulu)."""
    try:
        exige = int(json.loads((dossier / "version.json").read_text(encoding="utf-8")).get("requires_runtime") or 0)
    except (OSError, ValueError):
        exige = 0
    if exige > runtime():
        print(f"runtime {exige} exigé, {runtime()} disponible")
        return 3
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        os.environ["GRAMGEN_DATA"] = tmp
        try:
            client = charger(dossier).test_client()
            for url in ("/", "/api/accueil", "/api/stats", "/static/app.js"):
                if client.get(url).status_code != 200:
                    raise RuntimeError(f"{url} ne répond pas")
            n = len(client.get("/api/concepts").get_json())
            if not n:
                raise RuntimeError("aucun concept")
        except Exception:
            traceback.print_exc()
            return 1
    print(f"ok : {n} concepts, runtime {runtime()}")
    return 0


def preparer():
    """Dans l'exécutable : met le code à jour et le charge, avec repli sur le code embarqué."""
    donnees = Path(os.environ.get("GRAMGEN_DATA") or Path(os.environ.get("APPDATA") or Path.home()) / "GramGen")
    donnees.mkdir(parents=True, exist_ok=True)
    os.environ["GRAMGEN_DATA"] = str(donnees)
    os.environ["GRAMGEN_RUNTIME"] = str(runtime())
    live = donnees / "app"
    choisir(EMBARQUE)
    updater = import_module("updater")
    for etape in (lambda: updater.deployer(EMBARQUE, live), lambda: updater.appliquer(live, runtime())):
        try:
            etape()
        except OSError:
            traceback.print_exc()       # dossier verrouillé : on retentera au prochain démarrage
    try:
        return charger(live)
    except Exception:
        traceback.print_exc()
        print("Code installé inutilisable : repli sur le code de l'exécutable.", flush=True)
        return charger(EMBARQUE)


def port_libre(debut=5200, fin=5300):
    for port in range(debut, fin):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return debut


def main():
    if "--self-check" in sys.argv:
        i = sys.argv.index("--app-dir") + 1 if "--app-dir" in sys.argv else 0
        sys.exit(auto_verification(Path(sys.argv[i]).resolve() if i else EMBARQUE))
    app = preparer() if GELE else charger(EMBARQUE)
    port = int(os.environ.get("GRAMGEN_PORT") or port_libre())
    # La coque Tauri lit cette ligne pour connaître le port.
    print(f"Gram-Gen running on http://127.0.0.1:{port}", flush=True)
    if os.environ.get("GRAMGEN_SIDECAR") != "1":
        threading.Timer(1, webbrowser.open, (f"http://127.0.0.1:{port}",)).start()
    serve(app, host="127.0.0.1", port=port, threads=4)


if __name__ == "__main__":
    main()
