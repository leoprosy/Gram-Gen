"""Point d'entrée : `python launcher.py` (navigateur) ou sidecar Tauri (GRAMGEN_SIDECAR=1)."""

import os
import socket
import threading
import webbrowser

from waitress import serve

import db
from app import app


def port_libre(debut=5200, fin=5300):
    for port in range(debut, fin):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return debut


if __name__ == "__main__":
    db.initialiser()
    port = int(os.environ.get("GRAMGEN_PORT") or port_libre())
    # La coque Tauri lit cette ligne pour connaître le port.
    print(f"Gram-Gen running on http://127.0.0.1:{port}", flush=True)
    if os.environ.get("GRAMGEN_SIDECAR") != "1":
        threading.Timer(1, webbrowser.open, (f"http://127.0.0.1:{port}",)).start()
    serve(app, host="127.0.0.1", port=port, threads=4)
