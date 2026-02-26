import os
import sqlite3
import sys
import time
from multiprocessing import Process

DB_PATH = "instance/bagger_test.sqlite3"


def simulate_crash():
    print("[BAGGER-TEST] Starte massiven Schreibvorgang (Transaktion)...")
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(
        "CREATE TABLE IF NOT EXISTS test_data (id INTEGER PRIMARY KEY, data TEXT)"
    )

    # Transaktion starten
    con.execute("BEGIN EXCLUSIVE")
    for i in range(10000):
        con.execute(
            "INSERT INTO test_data (data) VALUES (?)", (f"Wichtige Kunden-Daten {i}",)
        )

        # Simuliere harten Stromausfall (Stecker ziehen) nach 50%
        if i == 5000:
            print("[BAGGER-TEST] STROMAUSFALL SIMULIERT (Hard Crash - SIGKILL)!")
            sys.stdout.flush()
            os._exit(9)


def verify_recovery():
    print("[BAGGER-TEST] Strom wieder da. System startet neu...")
    time.sleep(1)
    print("[BAGGER-TEST] Pruefe Datenbank-Integritaet...")
    try:
        con = sqlite3.connect(DB_PATH)

        # SQLite Integrity Check
        cur = con.execute("PRAGMA integrity_check")
        result = cur.fetchone()[0]

        if result == "ok":
            print(
                "[BAGGER-TEST] Integritaetspruefung bestanden: DB ist 'ok' und nicht korrupt."
            )
        else:
            print(f"[BAGGER-TEST] Datenbank korrupt: {result}")
            sys.exit(1)

        # Pruefen, ob die halbfertigen Daten sauber verworfen wurden (Rollback)
        count = con.execute("SELECT COUNT(*) FROM test_data").fetchone()[0]
        print(
            f"[BAGGER-TEST] Gefundene Datensaetze: {count} (Erwartet: 0, da Transaktion abgebrochen wurde)"
        )

        if count == 0:
            print(
                "[PASSED] Bagger-Test erfolgreich! Die SQLite WAL-Architektur hat den Datenmuell blockiert."
            )
        else:
            print("[FAILED] Halbgare Daten in der DB gefunden!")
            sys.exit(1)

    except Exception as e:
        print(f"[BAGGER-TEST] Fehler beim Zugriff auf die DB nach Crash: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    if os.path.exists(DB_PATH + "-wal"):
        os.remove(DB_PATH + "-wal")
    if os.path.exists(DB_PATH + "-shm"):
        os.remove(DB_PATH + "-shm")

    p = Process(target=simulate_crash)
    p.start()
    p.join()

    print(f"[BAGGER-TEST] Crash-Prozess beendet mit Exit-Code: {p.exitcode}")

    verify_recovery()

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
