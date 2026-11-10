"""Local storage: a SQLite database plus a folder of photos.

Everything lives in LOOKSMAX_HOME (default ~/.looksmax) on your own machine.
"""

import json
import os
import sqlite3
from pathlib import Path

HOME = Path(os.environ.get("LOOKSMAX_HOME", Path.home() / ".looksmax"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS checkins (
    day TEXT PRIMARY KEY,          -- YYYY-MM-DD
    photo TEXT NOT NULL,           -- file name in photos/
    assessment TEXT,               -- JSON, null if no face was found
    report TEXT,                   -- Markdown report
    warnings TEXT,                 -- JSON list of photo-quality warnings
    created TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS habit_log (
    day TEXT NOT NULL,
    habit TEXT NOT NULL,
    done INTEGER NOT NULL,
    PRIMARY KEY (day, habit)
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""


class Store:
    def __init__(self, home=HOME):
        self.home = Path(home)
        self.photos = self.home / "photos"
        self.photos.mkdir(parents=True, exist_ok=True)
        self.path = self.home / "looksmax.db"
        with self._db() as db:
            db.executescript(SCHEMA)

    def _db(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    # ---- settings
    def settings(self):
        with self._db() as db:
            return {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM settings")}

    def save_settings(self, **kv):
        with self._db() as db:
            db.executemany("INSERT OR REPLACE INTO settings VALUES (?, ?)",
                           [(k, v) for k, v in kv.items()])

    # ---- check-ins
    def save_checkin(self, day, photo, assessment, report, warnings):
        with self._db() as db:
            db.execute("INSERT OR REPLACE INTO checkins (day, photo, assessment, report, warnings) "
                       "VALUES (?, ?, ?, ?, ?)",
                       (day, photo, json.dumps(assessment, default=float) if assessment else None,
                        report, json.dumps(warnings)))

    def checkin(self, day):
        with self._db() as db:
            r = db.execute("SELECT * FROM checkins WHERE day = ?", (day,)).fetchone()
        return self._row(r)

    def latest_checkin(self, on_or_before):
        with self._db() as db:
            r = db.execute("SELECT * FROM checkins WHERE day <= ? AND assessment IS NOT NULL "
                           "ORDER BY day DESC LIMIT 1", (on_or_before,)).fetchone()
        return self._row(r)

    def checkins(self, since=None):
        with self._db() as db:
            rows = db.execute("SELECT * FROM checkins WHERE day >= ? ORDER BY day",
                              (since or "0000",)).fetchall()
        return [self._row(r) for r in rows]

    @staticmethod
    def _row(r):
        if r is None:
            return None
        d = dict(r)
        d["assessment"] = json.loads(d["assessment"]) if d["assessment"] else None
        d["warnings"] = json.loads(d["warnings"] or "[]")
        return d

    # ---- habits
    def set_habit(self, day, habit, done):
        with self._db() as db:
            db.execute("INSERT OR REPLACE INTO habit_log VALUES (?, ?, ?)", (day, habit, int(done)))

    def habits_done(self, day):
        with self._db() as db:
            return {r["habit"] for r in db.execute(
                "SELECT habit FROM habit_log WHERE day = ? AND done = 1", (day,))}

    def habit_log(self, since):
        with self._db() as db:
            return [dict(r) for r in db.execute(
                "SELECT day, habit FROM habit_log WHERE day >= ? AND done = 1", (since,))]
