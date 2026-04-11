"""Supabase 클라이언트 초기화 및 래퍼"""

import os
from typing import Dict, Any, Optional, List

try:
    from supabase import create_client, Client
except ImportError:
    create_client = None
    Client = None


class SupabaseManager:
    """Supabase 클라이언트 래퍼"""

    def __init__(self, url: str = None, key: str = None):
        """
        Args:
            url: Supabase URL (env: SUPABASE_URL)
            key: service_role key (env: SUPABASE_SERVICE_ROLE_KEY)
        """
        if create_client is None:
            raise RuntimeError("supabase 패키지 필요: pip install supabase")

        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY 환경변수 필수")

        self.client: Client = create_client(self.url, self.key)

    def insert_behavior_log(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Supabase behavior_logs 테이블에 INSERT

        Args:
            data: {
                'dog_id': '...',
                'type_id': 1,
                'antecedent': '...',
                'behavior': '...',
                'consequence': '...',
                'intensity': 3,
                'occurred_at': '2026-04-11T...',
                'is_quick_log': False
            }

        Returns:
            Supabase 응답 (id 포함)

        Raises:
            Exception: API 오류
        """
        try:
            response = self.client.table("behavior_logs").insert(data).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return response.data
        except Exception as e:
            raise RuntimeError(f"Supabase insert 실패: {str(e)}")

    def check_connection(self) -> bool:
        """Supabase 연결 확인"""
        try:
            # 간단한 쿼리로 연결 테스트
            self.client.table("dogs").select("id").limit(1).execute()
            return True
        except Exception:
            return False


# 글로벌 인스턴스
_supabase_instance: Optional[SupabaseManager] = None


def get_supabase_client() -> SupabaseManager:
    """글로벌 Supabase 클라이언트 반환"""
    global _supabase_instance
    if _supabase_instance is None:
        _supabase_instance = SupabaseManager()
    return _supabase_instance
