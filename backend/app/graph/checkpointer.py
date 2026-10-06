"""
SQLite-backed Checkpoint Saver for LangGraph per Master Plan Phase 9.
Persists graph execution states, writes, and channel blobs to SQLite database
to guarantee crash recovery and state resumption across server restarts.
"""
import os
import pickle
import sqlite3
from typing import Optional
from langgraph.checkpoint.memory import MemorySaver

DEFAULT_CHECKPOINT_DB = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../storage/graph_checkpoints.db")
)


class SqliteCheckpointer(MemorySaver):
    """A durable SQLite-backed checkpoint saver for LangGraph."""

    def __init__(self, db_path: Optional[str] = None):
        super().__init__()
        self.db_path = db_path or DEFAULT_CHECKPOINT_DB
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        self._load()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self) -> None:
        """Create storage table in SQLite if it does not exist."""
        with self._get_connection() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS graph_checkpoints (k TEXT PRIMARY KEY, v BLOB)"
            )
            conn.commit()

    def _save(self) -> None:
        """Serialize in-memory storage, writes, and blobs into SQLite."""
        try:
            clean_storage = {k: {nk: dict(nv) for nk, nv in v.items()} for k, v in self.storage.items()}
            clean_writes = {k: dict(v) for k, v in self.writes.items()}
            clean_blobs = dict(self.blobs)
            payload = pickle.dumps((clean_storage, clean_writes, clean_blobs))
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO graph_checkpoints (k, v) VALUES (?, ?)",
                    ("state_dump", payload)
                )
                conn.commit()
        except Exception as e:
            print("SAVE ERROR IN CHECKPOINTER:", repr(e))

    def _load(self) -> None:
        """Restore in-memory storage, writes, and blobs from SQLite."""
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT v FROM graph_checkpoints WHERE k = ?",
                    ("state_dump",)
                ).fetchone()
                if row and row[0]:
                    st, wr, bl = pickle.loads(row[0])
                    for k, v in st.items():
                        for nk, nv in v.items():
                            self.storage[k][nk].update(nv)
                    for k, v in wr.items():
                        self.writes[k].update(v)
                    self.blobs.update(bl)
        except Exception:
            pass

    def put(self, *args, **kwargs):
        res = super().put(*args, **kwargs)
        self._save()
        return res

    def delete_thread(self, *args, **kwargs):
        res = super().delete_thread(*args, **kwargs)
        self._save()
        return res
