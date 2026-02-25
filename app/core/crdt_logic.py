from __future__ import annotations
import time
from typing import Any, Generic, TypeVar

T = TypeVar("T")

class LWWRegister(Generic[T]):
    """
    Last-Writer-Wins Register (CRDT).
    Ensures that the update with the highest timestamp and Peer ID wins ties.
    """
    def __init__(self, value: T, timestamp: float | None = None, peer_id: str = "default"):
        self.value = value
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.peer_id = peer_id

    def update(self, value: T, peer_id: str):
        self.value = value
        self.timestamp = time.time()
        self.peer_id = peer_id

    def merge(self, other: LWWRegister[T]) -> LWWRegister[T]:
        """
        Merge this register with another.
        Highest timestamp wins. If timestamps are equal, highest peer_id (string comparison) wins.
        """
        if other.timestamp > self.timestamp:
            return other
        elif other.timestamp == self.timestamp:
            if other.peer_id > self.peer_id:
                return other
        return self

    def to_dict(self) -> dict:
        return {
            "v": self.value,
            "ts": self.timestamp,
            "pid": self.peer_id
        }

    @classmethod
    def from_dict(cls, data: dict) -> LWWRegister:
        return cls(value=data["v"], timestamp=data["ts"], peer_id=data["pid"])


def merge_records(local_data: dict, remote_data: dict) -> dict:
    """
    Generic record merge using LWW semantics for each field.
    Assumes values are stored as LWW dicts or plain values (which get converted).
    """
    merged = {}
    all_keys = set(local_data.keys()) | set(remote_data.keys())
    
    for key in all_keys:
        l_val = local_data.get(key)
        r_val = remote_data.get(key)
        
        # Convert plain values to LWW if necessary (migration path)
        l_reg = LWWRegister.from_dict(l_val) if isinstance(l_val, dict) and "ts" in l_val else LWWRegister(l_val, timestamp=0)
        r_reg = LWWRegister.from_dict(r_val) if isinstance(r_val, dict) and "ts" in r_val else LWWRegister(r_val, timestamp=0)
        
        merged[key] = l_reg.merge(r_reg).to_dict()
        
    return merged
