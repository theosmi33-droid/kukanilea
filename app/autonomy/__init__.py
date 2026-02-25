from __future__ import annotations

from flask import Flask

from .healer import init_healer


def init_autonomy(app: Flask) -> None:
    init_healer(app)
