#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from kukanilea_app import create_app

# Erzeuge die App-Instanz einmal und exportiere sie:
app = create_app()

# Wenn dieser File direkt ausgeführt wird,
# starte den Waitress-Server.
if __name__ == "__main__":
    from waitress import serve
    serve(app, host="127.0.0.1", port=5051)
