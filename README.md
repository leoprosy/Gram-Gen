# Gram-Gen

Réviser la grammaire anglaise et espagnole par **concepts** : c'est la règle qui revient, jamais la même phrase.
Application de bureau hors ligne, sans clé d'API.

## Installer (Windows)

Télécharger `Gram-Gen_x.y.z_x64-setup.exe` depuis la [page des releases](https://github.com/leoprosy/Gram-Gen/releases/latest).
L'installateur n'est pas signé : Windows peut afficher un avertissement SmartScreen.

## Lancer en développement

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python launcher.py
.venv\Scripts\python -m unittest discover -s tests -t .
```

Données en développement : `data/`. Application installée : `%APPDATA%\GramGen`. `GRAMGEN_DATA` force un autre dossier.

## Construire l'installateur Windows

`npm install`, puis `.\build.ps1` (Rust requis).

## Organisation

| Fichier | Rôle |
| --- | --- |
| `app.py` | API locale Flask, seule à écrire dans la base |
| `moteur.py` | SM-2 par concept, tirage, composition des séances |
| `correction.py` | Normalisation et verdicts (étages 1 et 2) |
| `contenu.py` | Format d'échange, import, prompt de génération |
| `db.py`, `migrations/` | SQLite, migrations numérotées, copies de sécurité |
| `seed/` | Contenu de départ, au format d'import |
| `static/`, `templates/` | Interface, sans framework |
| `src-tauri/` | Coque de bureau |

## Format d'import

Une liste d'exercices, ou `{"concepts": […], "exercices": […]}` (voir `seed/es.json`).
Types : `trous`, `conjugaison`, `theme`, `transformation`, `choix`, `qcm`, `erreur`.
Phrase à trous : blancs `{{1}}`, `{{2}}`… et une liste de réponses par blanc. QCM et choix : blanc `___`.
