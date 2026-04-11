"""Supabase 클라이언트 — PostgreSQL 직접 연결"""

import os
from typing import Dict, Any, Optional

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None


class SupabaseManager:
    """Supabase PostgreSQL 직접 연결 래퍼"""

    def __init__(self, db_url: str = None):
        """
        Args:
            db_url: PostgreSQL 연결 URL (env: SUPABASE_DB_URL)
        """
        if psycopg2 is None:
            raise RuntimeError("psycopg2 패키지 필요: pip install psycopg2-binary")

        self.db_url = db_url or os.getenv("SUPABASE_DB_URL")
        if not self.db_url:
            raise ValueError("SUPABASE_DB_URL 환경변수 필수")

    def _connect(self):
        return psycopg2.connect(self.db_url)

    def insert_behavior_log(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        behavior_logs 테이블에 INSERT

        Args:
            data: {
                'dog_id': '<uuid>',
                'behavior_type': 'walk_pulling',
                'antecedent': '...',
                'behavior': '...',
                'consequence': '...',
                'intensity': 3,
                'occurred_at': '2026-04-11T...',
                'is_quick_log': False
            }

        Returns:
            {'id': '<uuid>', ...}
        """
        cols = list(data.keys())
        vals = list(data.values())
        placeholders = ", ".join(["%s"] * len(cols))
        col_names = ", ".join(cols)

        sql = f"INSERT INTO behavior_logs ({col_names}) VALUES ({placeholders}) RETURNING id"

        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(sql, vals)
                    row = cur.fetchone()
                    conn.commit()
                    return dict(row)
        except Exception as e:
            raise RuntimeError(f"Supabase insert 실패: {str(e)}") from e

    def check_connection(self) -> bool:
        """연결 확인"""
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return True
        except Exception as e:
            print(f"Supabase 연결 실패: {str(e)}")
            return False


# 글로벌 인스턴스
_supabase_instance: Optional[SupabaseManager] = None


def get_supabase_client() -> SupabaseManager:
    """글로벌 Supabase 클라이언트 반환"""
    global _supabase_instance
    if _supabase_instance is None:
        _supabase_instance = SupabaseManager()
    return _supabase_instance
