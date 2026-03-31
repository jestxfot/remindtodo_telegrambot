"""
Encrypted SQLite storage with one-shot migration from legacy JSON files.
"""
import asyncio
import json
import shutil
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import fcntl
except ImportError:  # pragma: no cover - Unix-only file locking
    fcntl = None

from config import DATA_DIR
from crypto.encryption import CryptoManager
from utils.timezone import now_str, parse_dt

from .models import UserData
from .user_storage import UserStorage


class EncryptedSQLiteStorage:
    """
    Encrypted per-user storage backed by SQLite.

    User payloads stay encrypted with the same AES-256-GCM envelope that was used
    in the legacy JSON files. The only source of truth is the SQLite database.
    """

    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "storage.sqlite3"
        self.legacy_backup_root = self.data_dir / "legacy_json_backup"
        self._locks: Dict[int, asyncio.Lock] = {}

        self._initialize_database()
        self._migrate_legacy_json_files()

    def _get_lock(self, user_id: int) -> asyncio.Lock:
        """Get or create a per-user lock."""
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection configured for this storage."""
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    def _initialize_database(self) -> None:
        """Ensure the SQLite schema exists."""
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS encrypted_user_data (
                    user_id INTEGER PRIMARY KEY,
                    version TEXT NOT NULL,
                    algorithm TEXT NOT NULL,
                    key_fingerprint TEXT,
                    last_modified TEXT NOT NULL,
                    data TEXT NOT NULL,
                    migrated_from TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS storage_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    @contextmanager
    def _migration_lock(self):
        """Serialize legacy JSON migration across concurrently starting processes."""
        lock_path = self.data_dir / ".sqlite_migration.lock"
        with open(lock_path, "w", encoding="utf-8") as lock_handle:
            if fcntl is not None:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def _get_user_row(
        self, connection: sqlite3.Connection, user_id: int
    ) -> Optional[sqlite3.Row]:
        """Fetch a raw user row."""
        return connection.execute(
            """
            SELECT user_id, version, algorithm, key_fingerprint, last_modified, data,
                   migrated_from, created_at, updated_at
            FROM encrypted_user_data
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    def _set_meta(self, connection: sqlite3.Connection, key: str, value: str) -> None:
        """Upsert a storage metadata value."""
        connection.execute(
            """
            INSERT INTO storage_meta (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )

    def _row_to_envelope(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a DB row to the exported encrypted envelope format."""
        return {
            "version": row["version"],
            "algorithm": row["algorithm"],
            "key_fingerprint": row["key_fingerprint"],
            "user_id": row["user_id"],
            "last_modified": row["last_modified"],
            "data": row["data"],
        }

    def _normalize_envelope(self, user_id: int, payload: Any) -> Dict[str, Any]:
        """Normalize imported payloads into a single encrypted-envelope format."""
        if isinstance(payload, str):
            envelope = json.loads(payload)
        elif isinstance(payload, dict):
            envelope = dict(payload)
        else:
            raise ValueError("Encrypted payload must be a JSON string or dict")

        if not isinstance(envelope.get("data"), str) or not envelope["data"]:
            raise ValueError("Encrypted payload is missing the encrypted 'data' field")

        payload_user_id = envelope.get("user_id", user_id)
        if int(payload_user_id) != int(user_id):
            raise ValueError(
                f"Encrypted payload user_id mismatch: expected {user_id}, got {payload_user_id}"
            )

        return {
            "version": str(envelope.get("version", "2.0")),
            "algorithm": str(envelope.get("algorithm", "AES-256-GCM")),
            "key_fingerprint": envelope.get("key_fingerprint"),
            "user_id": int(user_id),
            "last_modified": envelope.get("last_modified") or now_str(),
            "data": envelope["data"],
        }

    def _save_envelope(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        envelope: Dict[str, Any],
        migrated_from: Optional[str] = None,
    ) -> None:
        """Insert or replace a user's encrypted envelope."""
        existing = self._get_user_row(connection, user_id)
        timestamp = now_str()
        created_at = existing["created_at"] if existing else timestamp

        if existing:
            connection.execute(
                """
                UPDATE encrypted_user_data
                SET version = ?, algorithm = ?, key_fingerprint = ?, last_modified = ?,
                    data = ?, migrated_from = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (
                    envelope["version"],
                    envelope["algorithm"],
                    envelope.get("key_fingerprint"),
                    envelope["last_modified"],
                    envelope["data"],
                    migrated_from,
                    timestamp,
                    user_id,
                ),
            )
        else:
            connection.execute(
                """
                INSERT INTO encrypted_user_data (
                    user_id, version, algorithm, key_fingerprint, last_modified,
                    data, migrated_from, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    envelope["version"],
                    envelope["algorithm"],
                    envelope.get("key_fingerprint"),
                    envelope["last_modified"],
                    envelope["data"],
                    migrated_from,
                    created_at,
                    timestamp,
                ),
            )

    def _legacy_user_id_from_path(self, filepath: Path) -> int:
        """Extract the user id from a legacy encrypted JSON filename."""
        parts = filepath.name.split("_", 1)
        if len(parts) != 2:
            raise ValueError(f"Unexpected legacy filename: {filepath.name}")
        return int(parts[1].split(".", 1)[0])

    def _read_legacy_envelope(self, filepath: Path) -> Dict[str, Any]:
        """Read and validate a legacy JSON storage file."""
        user_id = self._legacy_user_id_from_path(filepath)
        raw_payload = json.loads(filepath.read_text(encoding="utf-8"))
        envelope = self._normalize_envelope(user_id, raw_payload)
        if int(envelope["user_id"]) != user_id:
            raise ValueError(
                f"Legacy file {filepath.name} contains user_id={envelope['user_id']}, "
                f"expected {user_id}"
            )
        return envelope

    def _is_newer_envelope(
        self, candidate: Dict[str, Any], current: Dict[str, Any]
    ) -> bool:
        """Choose the newer envelope by last_modified, falling back to lexical compare."""
        candidate_ts = candidate.get("last_modified")
        current_ts = current.get("last_modified")

        try:
            return parse_dt(candidate_ts) >= parse_dt(current_ts)
        except Exception:
            return str(candidate_ts or "") >= str(current_ts or "")

    def _archive_legacy_files(self, files: List[Path]) -> Optional[Path]:
        """Move migrated legacy files into a backup directory."""
        if not files:
            return None

        backup_dir = self.legacy_backup_root / f"migrated_{now_str().replace(':', '-').replace(' ', '_')}"
        backup_dir.mkdir(parents=True, exist_ok=True)

        move_errors: List[str] = []
        for filepath in files:
            if not filepath.exists():
                continue
            destination = backup_dir / filepath.name
            try:
                shutil.move(str(filepath), str(destination))
            except Exception as exc:
                move_errors.append(f"{filepath.name}: {exc}")

        if move_errors:
            raise RuntimeError(
                "Legacy JSON migration completed, but failed to archive some old files: "
                + "; ".join(move_errors)
            )

        return backup_dir

    def _migrate_legacy_json_files(self) -> None:
        """Import legacy encrypted JSON files into SQLite and archive the originals."""
        with self._migration_lock():
            legacy_files = sorted(self.data_dir.glob("user_*.encrypted.json"))
            if not legacy_files:
                return

            envelopes = [(filepath, self._read_legacy_envelope(filepath)) for filepath in legacy_files]

            with self._connect() as connection:
                for filepath, envelope in envelopes:
                    existing = self._get_user_row(connection, envelope["user_id"])
                    if existing is not None:
                        existing_envelope = self._row_to_envelope(existing)
                        if not self._is_newer_envelope(envelope, existing_envelope):
                            continue

                    self._save_envelope(
                        connection,
                        envelope["user_id"],
                        envelope,
                        migrated_from=str(filepath),
                    )

                self._set_meta(connection, "legacy_json_migrated_at", now_str())
                connection.commit()

            backup_dir = self._archive_legacy_files(legacy_files)
            if backup_dir is not None:
                with self._connect() as connection:
                    self._set_meta(connection, "legacy_json_backup_dir", str(backup_dir))
                    connection.commit()

    async def get_user_storage(self, user_id: int, crypto: CryptoManager) -> UserStorage:
        """Get user storage for the provided crypto manager."""
        user_storage = UserStorage(self, user_id, crypto)
        await user_storage.load()
        return user_storage

    async def save_user_data(
        self, user_id: int, data: UserData, crypto: CryptoManager
    ) -> None:
        """Encrypt and store user data in SQLite."""
        async with self._get_lock(user_id):
            envelope = {
                "version": "2.0",
                "algorithm": "AES-256-GCM",
                "key_fingerprint": crypto.key_fingerprint,
                "user_id": user_id,
                "last_modified": now_str(),
                "data": crypto.encrypt(data.to_dict()),
            }

            with self._connect() as connection:
                self._save_envelope(connection, user_id, envelope)
                connection.commit()

    async def load_user_data(
        self, user_id: int, crypto: CryptoManager
    ) -> Optional[UserData]:
        """Load and decrypt user data from SQLite."""
        async with self._get_lock(user_id):
            with self._connect() as connection:
                row = self._get_user_row(connection, user_id)

            if row is None:
                print(f"[INFO] No stored data for user {user_id}")
                return None

            envelope = self._row_to_envelope(row)
            stored_fingerprint = envelope.get("key_fingerprint", "unknown")
            current_fingerprint = crypto.key_fingerprint
            if stored_fingerprint != current_fingerprint:
                print(f"[WARN] Key fingerprint mismatch for user {user_id}!")
                print(f"[WARN] Stored: {stored_fingerprint}, Current: {current_fingerprint}")
                print("[WARN] The decryption key is different - data may not decrypt!")

            decrypted = crypto.decrypt_to_json(envelope["data"])
            user_data = UserData.from_dict(decrypted)
            print(
                f"[INFO] Loaded data for user {user_id}: "
                f"{len(user_data.reminders)} reminders, "
                f"{len(user_data.todos)} todos, "
                f"{len(user_data.notes)} notes"
            )
            return user_data

    async def user_exists(self, user_id: int) -> bool:
        """Check whether encrypted data exists for a user."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM encrypted_user_data WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return row is not None

    async def get_all_user_ids(self) -> List[int]:
        """Get all user ids with stored data."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT user_id FROM encrypted_user_data ORDER BY user_id"
            ).fetchall()
        return [int(row["user_id"]) for row in rows]

    def export_data(self, user_id: int) -> Optional[str]:
        """Export a user's encrypted envelope as JSON."""
        with self._connect() as connection:
            row = self._get_user_row(connection, user_id)
        if row is None:
            return None
        return json.dumps(self._row_to_envelope(row), ensure_ascii=False, indent=2)

    async def import_data(self, user_id: int, encrypted_data: Any) -> bool:
        """Import an already-encrypted user payload into SQLite."""
        async with self._get_lock(user_id):
            envelope = self._normalize_envelope(user_id, encrypted_data)
            with self._connect() as connection:
                self._save_envelope(connection, user_id, envelope)
                connection.commit()
        return True


storage = EncryptedSQLiteStorage()
