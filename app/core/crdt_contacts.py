import json
import sqlite3

from .crdt_logic import LWWRegister, merge_records


class CRDTContactManager:
    """
    Manages Contact/Customer data with CRDT support.
    Uses the docs_index table for demo purposes, adding LWW metadata.
    """

    def __init__(self, db_path: str, peer_id: str):
        self.db_path = db_path
        self.peer_id = peer_id

    def _db(self):
        return sqlite3.connect(self.db_path)

    def update_customer_name(self, kdnr: str, name: str):
        """
        Updates a customer name using LWW semantics.
        """
        with self._db() as con:
            con.row_factory = sqlite3.Row
            row = con.execute(
                "SELECT crdt_meta, customer_name, phone FROM docs_index WHERE kdnr=?",
                (kdnr,),
            ).fetchone()

            meta = {}
            if row and row["crdt_meta"]:
                meta = json.loads(row["crdt_meta"])

            # Seed meta from current columns if empty (migration path)
            if not meta:
                meta = {
                    "customer_name": LWWRegister(
                        row["customer_name"], timestamp=0.0
                    ).to_dict(),
                    "phone": LWWRegister(row["phone"], timestamp=0.0).to_dict(),
                }

            # Update the specific field in metadata
            name_reg = LWWRegister(name, peer_id=self.peer_id)
            meta["customer_name"] = name_reg.to_dict()

            con.execute(
                "UPDATE docs_index SET customer_name=?, crdt_meta=? WHERE kdnr=?",
                (name, json.dumps(meta), kdnr),
            )
            con.commit()

    def merge_from_remote(
        self,
        kdnr: str,
        remote_meta_json: str,
        remote_customer_name: str,
        remote_phone: str = None,
    ):
        """
        Merges remote data into local state.
        """
        with self._db() as con:
            con.row_factory = sqlite3.Row
            row = con.execute(
                "SELECT crdt_meta, customer_name, phone FROM docs_index WHERE kdnr=?",
                (kdnr,),
            ).fetchone()

            if not row:
                return

            local_meta = json.loads(row["crdt_meta"] or "{}")
            if not local_meta:
                local_meta = {
                    "customer_name": LWWRegister(
                        row["customer_name"], timestamp=0.0
                    ).to_dict(),
                    "phone": LWWRegister(row["phone"], timestamp=0.0).to_dict(),
                }

            remote_meta = json.loads(remote_meta_json or "{}")

            # If remote_meta is empty but we have data, create basic remote registers with TS=0
            if "customer_name" not in remote_meta and remote_customer_name:
                remote_meta["customer_name"] = LWWRegister(
                    remote_customer_name, timestamp=0.0
                ).to_dict()
            if "phone" not in remote_meta and remote_phone:
                remote_meta["phone"] = LWWRegister(
                    remote_phone, timestamp=0.0
                ).to_dict()

            merged_meta = merge_records(local_meta, remote_meta)

            # Update local fields from merged result
            updates = []
            params = []
            for field in ["customer_name", "phone"]:
                if field in merged_meta:
                    updates.append(f"{field}=?")
                    params.append(merged_meta[field]["v"])

            if updates:
                sql = f"UPDATE docs_index SET {', '.join(updates)}, crdt_meta=? WHERE kdnr=?"
                params.extend([json.dumps(merged_meta), kdnr])
                con.execute(sql, params)
                con.commit()
