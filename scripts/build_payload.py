"""
Construit le code livré : embarqué dans l'exécutable (app_bundle) et publié en app.zip pour l'updater.

    python scripts/build_payload.py build/app_bundle [--zip build/app.zip]
"""

import argparse
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOSSIERS = ("templates", "static", "seed", "migrations")


def commit() -> str:
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True)
    return r.stdout.strip()


def construire(dest: Path) -> dict:
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    for f in ROOT.glob("*.py"):             # tout le code de l'app vit à la racine
        if f.name != "launcher.py":         # figé dans l'exécutable
            shutil.copy2(f, dest)
    for d in DOSSIERS:
        shutil.copytree(ROOT / d, dest / d)
    manifeste = {
        "version": json.loads((ROOT / "src-tauri/tauri.conf.json").read_text(encoding="utf-8"))["version"],
        "commit": commit(),
        "requires_runtime": json.loads((ROOT / "runtime.json").read_text(encoding="utf-8"))["runtime"],
    }
    (dest / "version.json").write_text(json.dumps(manifeste, indent=2), encoding="utf-8")
    return manifeste


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("dest", type=Path)
    p.add_argument("--zip", type=Path)
    args = p.parse_args()
    print(construire(args.dest))
    if args.zip:
        with zipfile.ZipFile(args.zip, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(args.dest.rglob("*")):
                if f.is_file():
                    z.write(f, Path("app") / f.relative_to(args.dest))
