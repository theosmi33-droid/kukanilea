#!/usr/bin/env python3
from __future__ import annotations

import os

from app import create_app

app = create_app()

__all__ = ["app", "create_app"]


if __name__ == "__main__":
    from waitress import serve

    serve(app, host="127.0.0.1", port=int(os.environ.get("PORT", "5051")))
