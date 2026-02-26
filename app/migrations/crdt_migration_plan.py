"""
CRDT Migration Plan v1.6.0
Target: Contacts & Jobs Tables
Objective: Enable LWW (Last-Writer-Wins) synchronization support.
"""

import sqlite3
from pathlib import Path


def migrate_to_crdt(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Identify tables needing CRDT (starting with contacts)
    tables = ["contacts"]

    for table in tables:
        print(f"Migrating table: {table}")
        # Add a JSON blob column to store field-level LWW metadata if we don't want to add 2 columns per field
        # Alternatively, add _ts and _pid columns for key fields.
        # Strategy: Add a 'crdt_meta' TEXT (JSON) column to track vector clocks/timestamps.
        try:
            cursor.execute(
                f"ALTER TABLE {table} ADD COLUMN crdt_meta TEXT DEFAULT '{{}}'"
            )
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column crdt_meta already exists in {table}")
            else:
                raise e

    conn.commit()
    conn.close()


if __name__ == "__main__":
    # Example for local core DB
    db = Path.home() / "Library/Application Support/KUKANILEA/core.sqlite3"
    if db.exists():
        migrate_to_crdt(str(db))
    else:
        print("Database not found at default location.")
