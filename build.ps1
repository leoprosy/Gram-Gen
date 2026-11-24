# Construit l'installateur Windows et app.zip : code, serveur PyInstaller, puis coque Tauri.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
function Invoke-Step($nom, [scriptblock]$etape) { & $etape; if ($LASTEXITCODE) { throw "Echec : $nom" } }
$py = ".venv/Scripts/python.exe"
Invoke-Step "tests" { & $py -m unittest discover -s tests -t . }
Invoke-Step "contrat de runtime" { & $py scripts/runtime_contract.py --check }
Invoke-Step "code" { & $py scripts/build_payload.py build/app_bundle --zip build/app.zip }
Invoke-Step "PyInstaller" { & $py -m PyInstaller --noconfirm gramgen-server.spec }
# L'exe neuf doit faire tourner le code qu'il embarque : un module oublie echoue ici, pas chez l'utilisateur.
Invoke-Step "auto-verification" { & dist/gramgen-server.exe --self-check }
$triple = ((& rustc -vV) -match "^host: ") -replace "^host: ", ""
New-Item -ItemType Directory -Force src-tauri/binaries | Out-Null
Copy-Item dist/gramgen-server.exe "src-tauri/binaries/gramgen-server-$triple.exe" -Force
Invoke-Step "Tauri" { npx tauri build }
