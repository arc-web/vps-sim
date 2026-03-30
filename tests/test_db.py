import pytest
from db import BaselineDB

def test_create_baselines_table(temp_db_path):
    """Initialize baselines table with correct schema."""
    db = BaselineDB(temp_db_path)
    db.create_tables()

    # Verify schema via pragma
    cursor = db.conn.cursor()
    cursor.execute("PRAGMA table_info(baselines)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    assert "id" in columns
    assert "timestamp" in columns
    assert "tag" in columns
    assert "data" in columns  # JSON blob

def test_insert_and_retrieve_baseline(temp_db_path, mock_baseline_data):
    """Store and retrieve baseline collection."""
    db = BaselineDB(temp_db_path)
    db.create_tables()

    db.insert_baseline(mock_baseline_data, tag="test-run")

    row = db.get_latest_baseline()
    assert row["tag"] == "test-run"
    assert row["data"]["ram"]["used_gb"] == 4.2

def test_get_baselines_since(temp_db_path, mock_baseline_data):
    """Retrieve baselines after a given timestamp."""
    db = BaselineDB(temp_db_path)
    db.create_tables()
    db.insert_baseline(mock_baseline_data)

    rows = db.get_baselines_since("2026-03-29T00:00:00Z")
    assert len(rows) == 1
