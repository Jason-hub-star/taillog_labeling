"""데이터베이스 테스트"""

import pytest
from src.core.database import Database


def test_database_creation(temp_db):
    """DB 생성"""
    db = Database(temp_db)
    db.init_schema()

    # 테이블 확인
    tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = [t["name"] for t in tables]

    assert "labeling_runs" in table_names
    assert "pose_results" in table_names
    assert "behavior_labels" in table_names
    assert "sync_attempts" in table_names


def test_insert_and_query(temp_db):
    """INSERT/SELECT 테스트"""
    db = Database(temp_db)
    db.init_schema()

    # INSERT
    db.insert(
        """
        INSERT INTO labeling_runs
        (id, url, title, channel, duration_s, video_path, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "run1",
            "https://youtube.com/watch?v=abc",
            "Test",
            "Channel",
            120,
            "/path/to/video.mp4",
            "collected",
        ),
    )

    # SELECT
    result = db.execute_one("SELECT * FROM labeling_runs WHERE id = ?", ("run1",))

    assert result is not None
    assert result["url"] == "https://youtube.com/watch?v=abc"
    assert result["status"] == "collected"


def test_update(temp_db):
    """UPDATE 테스트"""
    db = Database(temp_db)
    db.init_schema()

    # INSERT
    db.insert(
        """
        INSERT INTO labeling_runs
        (id, url, title, channel, duration_s, video_path, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "run1",
            "https://youtube.com/watch?v=abc",
            "Test",
            "Channel",
            120,
            "/path/to/video.mp4",
            "collected",
        ),
    )

    # UPDATE
    count = db.update(
        "UPDATE labeling_runs SET status = ? WHERE id = ?",
        ("synced", "run1"),
    )

    assert count == 1

    # 확인
    result = db.execute_one("SELECT * FROM labeling_runs WHERE id = ?", ("run1",))
    assert result["status"] == "synced"
