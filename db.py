"""Base SQLite : emplacement, migrations, copies de sécurité, contenu de départ."""

import json
import os
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent


def data_dir() -> Path:
    """%APPDATA%/GramGen une fois packagée (fixé par launcher.py) : la base survit aux mises à jour."""
    return Path(os.environ.get("GRAMGEN_DATA") or CODE_DIR / "data")


def connecter() -> sqlite3.Connection:
    con = sqlite3.connect(data_dir() / "gramgen.db")
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def migrer(con):
    """Applique les fichiers migrations/NNN_*.sql plus récents que user_version."""
    version = con.execute("PRAGMA user_version").fetchone()[0]
    for f in sorted((CODE_DIR / "migrations").glob("*.sql")):
        n = int(f.name[:3])
        if n > version:
            con.executescript(
                f"BEGIN;\n{f.read_text(encoding='utf-8')}\nPRAGMA user_version = {n};\nCOMMIT;"
            )


def sauvegarder(con, dossier: Path, garder=7):
    """Une copie par jour au démarrage, les 7 dernières conservées."""
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / f"gramgen-{date.today().isoformat()}.db"
    if not cible.exists():
        with closing(sqlite3.connect(cible)) as copie:
            con.backup(copie)
    for vieux in sorted(dossier.glob("gramgen-*.db"))[:-garder]:
        vieux.unlink()


def importer_contenu(con):
    """Chaque fichier de seed/ entre une seule fois : un exercice supprimé ne revient pas."""
    import contenu
    faits = {r["cle"] for r in con.execute("SELECT cle FROM reglage WHERE cle LIKE 'seed:%'")}
    if not faits and con.execute("SELECT 1 FROM concept LIMIT 1").fetchone():
        faits = {"seed:en", "seed:es"}          # base d'avant ce registre
    for f in sorted((CODE_DIR / "seed").glob("*.json"), key=lambda f: (len(f.stem), f.stem)):
        cle = f"seed:{f.stem}"
        if cle not in faits:
            contenu.importer(con, json.loads(f.read_text(encoding="utf-8")), source="ia", statut="actif")
        con.execute("INSERT OR IGNORE INTO reglage VALUES (?, 'true')", (cle,))
    con.commit()


def initialiser():
    dossier = data_dir()
    dossier.mkdir(parents=True, exist_ok=True)
    with closing(connecter()) as con:
        if con.execute("PRAGMA user_version").fetchone()[0]:   # avant toute migration
            sauvegarder(con, dossier / "sauvegardes")
        migrer(con)
        importer_contenu(con)
