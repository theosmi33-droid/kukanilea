import json
import os
import sqlite3
import sys
import time
from pathlib import Path

# Add app directory to path to import local modules
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.core.crdt_contacts import CRDTContactManager
from app.core.crdt_logic import LWWRegister


def setup_db(db_path):
    if os.path.exists(db_path):
        os.remove(db_path)
    con = sqlite3.connect(db_path)
    con.execute("""
        CREATE TABLE docs_index (
            kdnr TEXT PRIMARY KEY,
            customer_name TEXT,
            phone TEXT,
            crdt_meta TEXT DEFAULT '{}'
        )
    """)
    con.commit()
    con.close()


def run_sync_test():
    hub_db = "hub.sqlite3"
    peer_db = "peer.sqlite3"

    setup_db(hub_db)
    setup_db(peer_db)

    hub_mgr = CRDTContactManager(hub_db, "HUB-ZIMA-01")
    peer_mgr = CRDTContactManager(peer_db, "TABLET-GESELLE-01")

    kdnr = "K123"
    # Init: Create Kunde X on both
    for db in [hub_db, peer_db]:
        with sqlite3.connect(db) as con:
            con.execute(
                "INSERT INTO docs_index (kdnr, customer_name, phone) VALUES (?, ?, ?)",
                (kdnr, "Hans Mueller", "0170-111"),
            )

    print(f"--- Phase 1: Shared state initialized for {kdnr} ---")

    # Phase 2 (Offline Split): Hub changes Name (T1), Peer changes Phone (T2)
    t1 = time.time()
    hub_mgr.update_customer_name(kdnr, "Hans Mueller (Stammkunde)")

    time.sleep(0.1)  # Ensure distinct timestamps
    t2 = time.time()

    with sqlite3.connect(peer_db) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT crdt_meta FROM docs_index WHERE kdnr=?", (kdnr,)
        ).fetchone()
        meta = json.loads(row["crdt_meta"] or "{}")
        phone_reg = LWWRegister("0170-999", timestamp=t2, peer_id="TABLET-GESELLE-01")
        meta["phone"] = phone_reg.to_dict()
        con.execute(
            "UPDATE docs_index SET phone=?, crdt_meta=? WHERE kdnr=?",
            ("0170-999", json.dumps(meta), kdnr),
        )
        con.commit()

    print("--- Phase 2: Hub updated Name (T1), Peer updated Phone (T2) ---")

    # Phase 3 (Merge): Merge Peer data into Hub
    with sqlite3.connect(peer_db) as con:
        con.row_factory = sqlite3.Row
        peer_row = con.execute(
            "SELECT crdt_meta, customer_name, phone FROM docs_index WHERE kdnr=?",
            (kdnr,),
        ).fetchone()

    hub_mgr.merge_from_remote(
        kdnr, peer_row["crdt_meta"], peer_row["customer_name"], peer_row["phone"]
    )

    with sqlite3.connect(hub_db) as con:
        con.row_factory = sqlite3.Row
        final_row = con.execute(
            "SELECT * FROM docs_index WHERE kdnr=?", (kdnr,)
        ).fetchone()

    print(
        f"Final State on Hub: Name='{final_row['customer_name']}', Phone='{final_row['phone']}'"
    )

    success = (
        final_row["customer_name"] == "Hans Mueller (Stammkunde)"
        and final_row["phone"] == "0170-999"
    )

    if success:
        print("\n[PASSED] Conflict resolved successfully via LWW-Register.")
    else:
        print("\n[FAILED] Data loss or incorrect merge detected!")
        sys.exit(1)

    os.remove(hub_db)
    os.remove(peer_db)


if __name__ == "__main__":
    run_sync_test()
