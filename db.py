import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class BaselineDB:
    """SQLite manager for baseline collection history."""

    def __init__(self, db_path: str = "baselines.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def create_tables(self):
        """Create baselines table if not exists."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS baselines (
                id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                tag TEXT,
                data TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def insert_baseline(self, data: Dict, tag: Optional[str] = None) -> int:
        """Insert a baseline record. Return row ID."""
        self.conn.execute(
            "INSERT INTO baselines (timestamp, tag, data) VALUES (?, ?, ?)",
            (data["timestamp"], tag, json.dumps(data))
        )
        self.conn.commit()
        return self.conn.total_changes

    def get_latest_baseline(self) -> Optional[Dict]:
        """Get most recent baseline record."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT timestamp, tag, data FROM baselines ORDER BY timestamp DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            return {
                "timestamp": row[0],
                "tag": row[1],
                "data": json.loads(row[2])
            }
        return None

    def get_baselines_since(self, timestamp: str) -> List[Dict]:
        """Retrieve baselines after a given timestamp."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT timestamp, tag, data FROM baselines WHERE timestamp >= ? ORDER BY timestamp ASC",
            (timestamp,)
        )
        rows = cursor.fetchall()
        return [
            {
                "timestamp": row[0],
                "tag": row[1],
                "data": json.loads(row[2])
            }
            for row in rows
        ]

    def close(self):
        """Close database connection."""
        self.conn.close()
