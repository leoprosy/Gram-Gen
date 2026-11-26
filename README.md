# Gram-Gen

Réviser la grammaire anglaise et espagnole par **concepts** : c'est la règle qui revient, jamais la même phrase.
Application de bureau hors ligne. Une clé d'API Anthropic, facultative, ajoute la correction et la génération par Claude.

## Installer (Windows)

Télécharger `Gram-Gen_x.y.z_x64-setup.exe` depuis la [page des releases](https://github.com/leoprosy/Gram-Gen/releases/latest).
L'installateur n'est pas signé : Windows peut afficher un avertissement SmartScreen.

Ensuite, Gram-Gen se met à jour lui-même : au démarrage il lit le numéro de la dernière release sur GitHub (rien n'est
envoyé, tout marche hors ligne) et propose « Mettre à jour » dans l'accueil. Le nouveau code s'applique au redémarrage.

## Claude (facultatif)

Avec une clé d'API Anthropic (Réglages → Claude, ou la variable `ANTHROPIC_API_KEY`) :

- une réponse libre (thème, transformation, repérage d'erreur) absente des références est jugée par Claude. Si elle est
  juste, elle rejoint les réponses acceptées. Sans clé ou hors ligne, elle reste « à vérifier » et tu tranches toi-même ;
- « Générer des exercices » écrit le lot directement, qui arrive dans « À valider ».

La clé reste dans la base locale et n'est jamais exportée.

## Utiliser depuis Claude (MCP)

Gram-Gen peut tourner comme serveur [MCP](https://modelcontextprotocol.io) local : Claude voit quels réservoirs sont bas et
les remplit lui-même. Les exercices ajoutés passent par la file « À valider ». À enregistrer une fois (Claude Code ; pour
Claude Desktop, mettre la même commande dans `claude_desktop_config.json`) :

```powershell
claude mcp add --scope user gramgen -- "$env:LOCALAPPDATA\Gram-Gen\gramgen-server.exe" --mcp
```

Depuis les sources : `claude mcp add --scope local gramgen-dev -- .venv/Scripts/python.exe launcher.py --mcp`.

Outils : `lister_concepts`, `creer_concept`, `enonces`, `ajouter_exercices`, `etat_reservoirs`, `statistiques`.

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

## Publier une version

Aligner la version dans `src-tauri/tauri.conf.json`, `src-tauri/Cargo.toml` et `package.json`, puis pousser le tag `vX.Y.Z`.
La CI construit l'installateur et `app.zip`, vérifie que le nouveau code tourne sur l'exécutable déjà publié, et crée la release.

Après un changement de dépendance dans `requirements.txt` : `python scripts/runtime_contract.py --bump`. Les utilisateurs
seront alors invités à réinstaller, car leur exécutable ne contient pas la nouvelle dépendance.

## Organisation

| Fichier | Rôle |
| --- | --- |
| `app.py` | API locale Flask, seule à écrire dans la base |
| `moteur.py` | SM-2 par concept, tirage, composition des séances |
| `correction.py` | Normalisation et verdicts (étages 1 et 2) |
| `ia.py` | Appels à Claude : jugement (étage 3) et génération |
| `mcp_server.py` | Serveur MCP (stdio), passe par l'API locale |
| `contenu.py` | Format d'échange, import, prompt de génération |
| `db.py`, `migrations/` | SQLite, migrations numérotées, copies de sécurité |
| `updater.py`, `launcher.py` | Mise à jour : téléchargement, échange au démarrage, repli sur le code embarqué |
| `seed/` | Contenu de départ, au format d'import |
| `static/`, `templates/` | Interface, sans framework |
| `src-tauri/` | Coque de bureau |

## Format d'import

Une liste d'exercices, ou `{"concepts": […], "exercices": […]}` (voir `seed/es.json`).
Types : `trous`, `conjugaison`, `theme`, `transformation`, `choix`, `qcm`, `erreur`.
Phrase à trous : blancs `{{1}}`, `{{2}}`… et une liste de réponses par blanc. QCM et choix : blanc `___`.
