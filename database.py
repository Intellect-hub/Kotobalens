"""Persistent sentence and vocabulary history for KotobaLens.

On first use, copy an existing database to the per-user AppData directory.
The original database is never modified or deleted.
"""

import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

APP_NAME = "KotobaLens"


def _user_data_directory():
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / APP_NAME
    return Path.home() / "AppData" / "Local" / APP_NAME


DATABASE_PATH = _user_data_directory() / "japanese_helper.db"


def _old_database_candidates():
    module_dir = Path(__file__).resolve().parent
    candidates = [module_dir / "japanese_helper.db"]
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend([
            exe_dir / "_internal" / "japanese_helper.db",
            exe_dir / "japanese_helper.db",
        ])
    else:
        candidates.append(Path.cwd() / "japanese_helper.db")
    return list(dict.fromkeys(candidates))


def _prepare_database():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DATABASE_PATH.exists():
        return

    for previous_path in _old_database_candidates():
        if not previous_path.is_file() or previous_path == DATABASE_PATH:
            continue

        temporary_path = DATABASE_PATH.with_name("japanese_helper.migrating.db")
        try:
            if temporary_path.exists():
                temporary_path.unlink()

            # sqlite3's context manager alone does NOT close the connection.
            # closing() releases Windows file handles before the rename.
            with closing(sqlite3.connect(str(previous_path))) as source:
                with closing(sqlite3.connect(str(temporary_path))) as destination:
                    source.backup(destination)

            temporary_path.replace(DATABASE_PATH)
        except Exception as error:
            try:
                if temporary_path.exists():
                    temporary_path.unlink()
            except OSError:
                pass
            raise RuntimeError(
                f"Could not migrate history from {previous_path} to {DATABASE_PATH}. "
                "The original database was not changed. "
                f"Details: {error}"
            ) from error
        return


def get_connection():
    """Open the per-user SQLite database."""
    _prepare_database()
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():
    """Create the tables if they don't already exist."""
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS sentences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                japanese TEXT NOT NULL,
                english TEXT NOT NULL,
                captured_at TEXT DEFAULT CURRENT_TIMESTAMP,
                saved_to_anki INTEGER DEFAULT 0
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS vocabulary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL,
                reading TEXT,
                dictionary_form TEXT,
                meaning TEXT,
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                times_seen INTEGER DEFAULT 1,
                saved_to_anki INTEGER DEFAULT 0,
                UNIQUE(word, reading)
            )
        """)
        connection.commit()


def save_sentence(japanese, english):
    """Save a Japanese sentence and its English translation."""
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO sentences (japanese, english) VALUES (?, ?)",
            (japanese, english)
        )
        return cursor.lastrowid


def get_sentences():
    """Retrieve sentence history, newest first."""
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM sentences ORDER BY id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def save_vocabulary(word, reading, dictionary_form, meaning):
    """Save a word or increase its encounter count if it already exists."""
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT id FROM vocabulary WHERE word = ? AND reading = ?",
            (word, reading)
        ).fetchone()
        if existing:
            connection.execute(
                "UPDATE vocabulary SET times_seen = times_seen + 1 WHERE id = ?",
                (existing["id"],)
            )
            return existing["id"]
        cursor = connection.execute(
            """INSERT INTO vocabulary (word, reading, dictionary_form, meaning)
               VALUES (?, ?, ?, ?)""",
            (word, reading, dictionary_form, meaning)
        )
        return cursor.lastrowid


def get_vocabulary():
    """Retrieve saved vocabulary, newest first."""
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM vocabulary ORDER BY id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def delete_vocabulary_by_ids(ids):
    """Permanently delete only vocabulary entries with the given IDs."""
    ids = list(dict.fromkeys(int(item) for item in ids))
    if not ids:
        return 0
    placeholders = ", ".join("?" for _ in ids)
    with get_connection() as connection:
        cursor = connection.execute(
            f"DELETE FROM vocabulary WHERE id IN ({placeholders})", ids
        )
        return cursor.rowcount


def clear_all_history():
    """Atomically delete both sentence and vocabulary history."""
    with get_connection() as connection:
        connection.execute("DELETE FROM sentences")
        connection.execute("DELETE FROM vocabulary")


if __name__ == "__main__":
    initialize_database()
    print("Database ready:", DATABASE_PATH)
