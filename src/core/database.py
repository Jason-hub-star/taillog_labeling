"""SQLite 데이터베이스 관리 — WAL mode, schema 초기화"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, List, Dict, Any


class Database:
    """SQLite 연결 및 쿼리 래퍼"""

    def __init__(self, db_path: str = "data/databases/labeling.db"):
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_wal_mode()

    def _ensure_wal_mode(self):
        """WAL mode 활성화 (동시 접근 대비)"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.close()

    @contextmanager
    def get_connection(self):
        """컨텍스트 매니저 — 자동 commit/rollback"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, query: str, params: tuple = ()) -> List[Dict]:
        """SELECT 쿼리 실행"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def execute_one(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """단일 행 반환"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def insert(self, query: str, params: tuple = ()) -> str:
        """INSERT 실행, 마지막 행 ID 반환"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid

    def update(self, query: str, params: tuple = ()) -> int:
        """UPDATE 실행, 영향받은 행 수 반환"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount

    def init_schema(self):
        """스키마 초기화 (기존 테이블 유지)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # labeling_runs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS labeling_runs (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    duration_s REAL NOT NULL,
                    video_path TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    error_msg TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)

            # pose_results
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pose_results (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    frame_id INTEGER NOT NULL,
                    keypoints_json TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(run_id) REFERENCES labeling_runs(id),
                    UNIQUE(run_id, frame_id)
                )
            """)

            # behavior_labels
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS behavior_labels (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    frame_id INTEGER NOT NULL,
                    preset_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    label TEXT NOT NULL,
                    antecedent TEXT,
                    behavior TEXT,
                    consequence TEXT,
                    intensity INTEGER,
                    llm_confidence REAL NOT NULL,
                    consistency_score REAL NOT NULL,
                    keypoint_quality REAL NOT NULL,
                    confidence REAL NOT NULL,
                    review_status TEXT DEFAULT 'pending',
                    critic_pass BOOLEAN,
                    critic_note TEXT,
                    labeler_model TEXT NOT NULL,
                    synced BOOLEAN DEFAULT 0,
                    taillog_log_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    FOREIGN KEY(run_id) REFERENCES labeling_runs(id),
                    FOREIGN KEY(run_id, frame_id) REFERENCES pose_results(run_id, frame_id)
                )
            """)

            # sync_attempts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_attempts (
                    id TEXT PRIMARY KEY,
                    label_id TEXT NOT NULL,
                    attempt_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN DEFAULT 0,
                    error_msg TEXT,
                    FOREIGN KEY(label_id) REFERENCES behavior_labels(id)
                )
            """)

            # 인덱스
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_labeling_runs_status ON labeling_runs(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_behavior_labels_status ON behavior_labels(review_status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_behavior_labels_synced ON behavior_labels(synced)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pose_results_run_id ON pose_results(run_id)")

            conn.commit()


# 글로벌 인스턴스
_db_instance: Optional[Database] = None


def get_db() -> Database:
    """글로벌 DB 인스턴스 반환"""
    global _db_instance
    if _db_instance is None:
        db_path = os.getenv("LABELING_DB_PATH", "data/databases/labeling.db")
        _db_instance = Database(db_path)
    return _db_instance


def init_db():
    """DB 초기화"""
    db = get_db()
    db.init_schema()
