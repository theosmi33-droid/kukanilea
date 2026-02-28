from tophandwerk_core import db_connect


def reset_users():
    con = db_connect()
    cur = con.cursor()

    # ACHTUNG: löscht ALLE Benutzer & Rollen
    cur.execute("DELETE FROM users")
    cur.execute("DELETE FROM user_roles")

    con.commit()
    con.close()
    print("[OK] Alle User & Rollen wurden gelöscht.")


if __name__ == "__main__":
    reset_users()
