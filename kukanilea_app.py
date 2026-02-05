#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(app.config.get("PORT", 5051)), debug=True)
