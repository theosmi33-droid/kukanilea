from __future__ import annotations

from app import create_app


def main() -> None:
    app = create_app()
    with app.app_context():
        routes = [rule.rule for rule in app.url_map.iter_rules()]
        if "/login" not in routes:
            raise SystemExit("/login route missing")
    print("smoke ok")


if __name__ == "__main__":
    main()
