"""
Mise à jour automatique, reprise d'Anki-Gen.

L'exécutable (interpréteur + dépendances) ne change qu'avec l'installateur. Le code, lui, vit dans
<données>/app et se remplace par app.zip, publié dans la release GitHub. Le téléchargement va dans
app_staged ; l'échange a lieu au démarrage suivant, avant que le serveur n'écoute (launcher.py).

N'importe que la bibliothèque standard à ce niveau : launcher.py charge ce module avant tout le reste.
"""

import hashlib
import io
import json
import os
import shutil
import threading
import zipfile
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

DEPOT = "leoprosy/Gram-Gen"
RELEASE_URL = f"https://api.github.com/repos/{DEPOT}/releases/latest"
# Constante, jamais reçue du client : c'est le serveur qui l'ouvre.
PAGE_INSTALLATEUR = f"https://github.com/{DEPOT}/releases/latest"
ICI = Path(__file__).resolve().parent
_verrou = threading.Lock()


# ── Manifeste version.json : {version, commit, requires_runtime} ──

def lire_manifeste(dossier) -> dict:
    """{} si le dossier ne contient pas un code complet et lisible."""
    dossier = Path(dossier)
    try:
        m = json.loads((dossier / "version.json").read_text(encoding="utf-8"))
        complet = isinstance(m, dict) and _semver(m.get("version")) and (dossier / "app.py").is_file()
        return m if complet else {}
    except (OSError, ValueError):
        return {}


def _semver(version):
    try:
        parts = tuple(int(p) for p in version.split("."))
    except (AttributeError, ValueError):
        return None
    return parts if len(parts) == 3 and min(parts) >= 0 else None


def plus_recent(a, b) -> bool:
    """a > b ; faux dès qu'une des deux versions est illisible."""
    a, b = _semver(a), _semver(b)
    return bool(a and b and a > b)


def runtime_exige(manifeste) -> int:
    try:
        return int(manifeste.get("requires_runtime") or 0)
    except (TypeError, ValueError):
        return 0


# ── Au démarrage (launcher.py), avant tout import du code ─────────

def _voisin(live, suffixe) -> Path:
    return Path(str(live) + suffixe)


def _echanger(neuf: Path, live: Path):
    """`neuf` devient `live`. L'ancien n'est supprimé qu'une fois le nouveau en place."""
    ancien = _voisin(live, "_ancien")
    shutil.rmtree(ancien, ignore_errors=True)
    if live.exists():
        os.rename(live, ancien)
    try:
        os.rename(neuf, live)
    except OSError:
        if ancien.exists() and not live.exists():
            os.rename(ancien, live)
        raise
    shutil.rmtree(ancien, ignore_errors=True)


def deployer(embarque, live) -> bool:
    """Déploie le code de l'exécutable s'il est plus récent, ou reconstruit à version égale."""
    embarque, live = Path(embarque), Path(live)
    ici, la = lire_manifeste(embarque), lire_manifeste(live)
    if la and not plus_recent(ici["version"], la["version"]) and (
            ici["version"] != la["version"] or ici.get("commit") == la.get("commit")):
        return False
    neuf = _voisin(live, "_neuf")
    shutil.rmtree(neuf, ignore_errors=True)
    shutil.copytree(embarque, neuf)
    _echanger(neuf, live)
    return True


def appliquer(live, runtime: int) -> bool:
    """Met en place la mise à jour téléchargée, si elle est complète, plus récente et compatible."""
    live = Path(live)
    attente = _voisin(live, "_staged")
    if not attente.is_dir():
        return False
    m = lire_manifeste(attente)
    if not m or runtime_exige(m) > runtime or not plus_recent(m["version"], lire_manifeste(live).get("version", "0.0.0")):
        shutil.rmtree(attente, ignore_errors=True)
        return False
    _echanger(attente, live)
    return True


# ── Pendant l'exécution (routes /api/maj/*) ───────────────────────

def _live() -> Path:
    import db
    return db.data_dir() / "app"


def _runtime():
    """Numéro annoncé par launcher.py ; None hors de l'exécutable (développement)."""
    n = os.environ.get("GRAMGEN_RUNTIME", "")
    return int(n) if n.isdigit() else None


def version_locale() -> str:
    return lire_manifeste(ICI).get("version", "développement")


def _get(url, delai):
    with urlopen(Request(url, headers={"User-Agent": "GramGen-Updater"}), timeout=delai) as r:
        return r.read()


def _asset(release, nom):
    return next((a for a in release.get("assets", []) if a.get("name") == nom), None)


def _etat():
    """(état à afficher, asset app.zip ou None)."""
    local = version_locale()
    if _runtime() is None:
        return {"etat": "developpement", "version": local}, None
    prete = lire_manifeste(_voisin(_live(), "_staged"))
    if prete:
        return {"etat": "prete", "version": prete["version"]}, None
    release = json.loads(_get(RELEASE_URL, 5))
    fiche = _asset(release, "version.json")
    distant = json.loads(_get(fiche["browser_download_url"], 10)) if fiche else {}
    if not plus_recent(distant.get("version"), local):
        return {"etat": "a_jour", "version": local}, None
    if runtime_exige(distant) > _runtime():
        return {"etat": "installateur", "version": distant["version"]}, None
    archive = _asset(release, "app.zip")
    if not archive:
        return {"etat": "erreur", "version": local, "message": "La release ne contient pas app.zip."}, None
    return {"etat": "disponible", "version": distant["version"]}, archive


def _tenter(f):
    try:
        return f()
    except URLError:
        message = "GitHub est injoignable."
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as e:
        message = f"Mise à jour impossible : {e}"
    return {"etat": "erreur", "version": version_locale(), "message": message}


def verifier() -> dict:
    return _tenter(lambda: _etat()[0])


def telecharger() -> dict:
    with _verrou:
        return _tenter(_telecharger)


def _telecharger():
    etat, archive = _etat()
    if not archive:
        return etat
    contenu = _get(archive["browser_download_url"], 120)
    attendu = archive.get("digest") or ""
    if attendu.startswith("sha256:") and hashlib.sha256(contenu).hexdigest() != attendu[7:]:
        raise ValueError("l'archive reçue est abîmée.")
    live = _live()
    neuf = _voisin(live, "_telecharge")
    shutil.rmtree(neuf, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        z.extractall(neuf)
    if lire_manifeste(neuf / "app").get("version") != etat["version"]:
        shutil.rmtree(neuf, ignore_errors=True)
        raise ValueError("l'archive ne contient pas la version annoncée.")
    # Renommage final : une coupure pendant l'extraction ne laisse jamais de mise à jour à moitié prête.
    shutil.rmtree(_voisin(live, "_staged"), ignore_errors=True)
    os.rename(neuf / "app", _voisin(live, "_staged"))
    shutil.rmtree(neuf, ignore_errors=True)
    return {"etat": "prete", "version": etat["version"]}
