#!/usr/bin/env python3
from __future__ import annotations

import os

from waitress import serve

from app import create_app


def main() -> None:
    app = create_app()
    port = int(os.environ.get("PORT", str(app.config.get("PORT", 5051))))
    serve(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
