"""Self-Auditing Cryptographic Ledger.

An append-only, hash-chained log of every self-modification the matrix makes:
rewrites, promotions, rollbacks, capability registrations, chaos experiments.
Each entry commits to the previous entry's hash, so any tampering with history
is detectable by re-verifying the chain.

This is a first-class safety primitive — it is the tamper-evident lineage that
makes an autonomous, self-modifying system auditable after the fact.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

GENESIS_HASH = "0" * 64


@dataclass(slots=True, frozen=True)
class LedgerEntry:
    """One tamper-evident record in the evolutionary lineage."""

    index: int
    timestamp_ns: int
    event: str
    payload: dict[str, Any]
    prev_hash: str
    entry_hash: str

    def recompute_hash(self) -> str:
        """Recompute this entry's hash from its committed fields."""
        return _hash_entry(
            self.index, self.timestamp_ns, self.event, self.payload, self.prev_hash
        )


class CryptographicLedger:
    """Append-only hash chain over self-modification events."""

    def __init__(self, *, clock=time.time_ns) -> None:
        self._entries: list[LedgerEntry] = []
        self._clock = clock

    @property
    def head(self) -> str:
        """Hash of the most recent entry (or the genesis hash when empty)."""
        return self._entries[-1].entry_hash if self._entries else GENESIS_HASH

    def append(self, event: str, **payload: Any) -> LedgerEntry:
        """Append a new event, chaining it to the current head."""
        index = len(self._entries)
        timestamp = self._clock()
        prev = self.head
        entry_hash = _hash_entry(index, timestamp, event, payload, prev)
        entry = LedgerEntry(
            index=index,
            timestamp_ns=timestamp,
            event=event,
            payload=payload,
            prev_hash=prev,
            entry_hash=entry_hash,
        )
        self._entries.append(entry)
        return entry

    def verify(self) -> bool:
        """Return True iff the entire chain is internally consistent."""
        prev = GENESIS_HASH
        for i, entry in enumerate(self._entries):
            if entry.index != i or entry.prev_hash != prev:
                return False
            if entry.recompute_hash() != entry.entry_hash:
                return False
            prev = entry.entry_hash
        return True

    @property
    def entries(self) -> list[LedgerEntry]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)


def _hash_entry(
    index: int, timestamp_ns: int, event: str, payload: dict[str, Any], prev_hash: str
) -> str:
    body = json.dumps(
        {
            "index": index,
            "timestamp_ns": timestamp_ns,
            "event": event,
            "payload": payload,
            "prev_hash": prev_hash,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
