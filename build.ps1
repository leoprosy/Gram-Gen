# Construit l'installateur Windows : serveur PyInstaller, puis coque Tauri.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
& .venv\Scripts\python.exe -m unittest discover -s tests -t .
if ($LASTEXITCODE) { throw "Tests en échec" }
& .venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --console --name gramgen-server `
  --add-data "templates;templates" --add-data "static;static" --add-data "seed;seed" --add-data "migrations;migrations" launcher.py
if ($LASTEXITCODE) { throw "PyInstaller en échec" }
$triple = ((& rustc -vV) -match "^host: ") -replace "^host: ", ""
New-Item -ItemType Directory -Force src-tauri\binaries | Out-Null
Copy-Item dist\gramgen-server.exe "src-tauri\binaries\gramgen-server-$triple.exe" -Force
npx tauri build
if ($LASTEXITCODE) { throw "Tauri en échec" }
