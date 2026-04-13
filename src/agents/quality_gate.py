"""Quality Gate 에이전트 — 신뢰도 기반 review_status 설정"""

import os
from datetime import datetime
from typing import Optional

from src.core.database import get_db


class QualityGate:
    """신뢰도 임계값 기반 review_status 설정 에이전트"""

    # CONFIDENCE-THRESHOLD-POLICY 기준
    AUTO_APPROVED_THRESHOLD = 0.85
    HUMAN_REVIEW_THRESHOLD = 0.65
    COLD_START_LIMIT = 100  # 초기 100건은 모두 human_review
    # 오버라이드: COLD_START_LIMIT=0 환경변수로 cold_start 비활성화 가능

    def __init__(self):
        self.db = get_db()
        # 환경변수로 cold_start_limit 오버라이드 (테스트/첫 sync 시 0으로 설정)
        env_limit = os.environ.get("COLD_START_LIMIT")
        if env_limit is not None:
            self.cold_start_limit = int(env_limit)
        else:
            self.cold_start_limit = self.COLD_START_LIMIT

    def run(self, label_id: str, dry_run: bool = False) -> bool:
        """
        라벨의 review_status 설정

        Args:
            label_id: behavior_labels.id
            dry_run: True면 DB 저장 안 함

        Returns:
            성공 여부
        """
        # 1. 라벨 조회
        result = self.db.execute_one(
            "SELECT * FROM behavior_labels WHERE id = ?", (label_id,)
        )
        if not result:
            print(f"라벨 없음: {label_id}")
            return False

        confidence = result["confidence"]
        preset_id = result["preset_id"]

        # 2. Cold Start 검사 (초기 2주)
        total_synced = self.db.execute_one(
            "SELECT COUNT(*) as cnt FROM behavior_labels WHERE synced = 1"
        )
        synced_count = total_synced.get("cnt", 0) if total_synced else 0

        if synced_count < self.cold_start_limit:
            # Cold Start 모드: 모든 라벨을 human_review
            review_status = "human_review"
        elif preset_id == "unknown":
            # unknown 라벨은 항상 discard
            review_status = "rejected"
        elif confidence >= self.AUTO_APPROVED_THRESHOLD:
            review_status = "auto_approved"
        elif confidence >= self.HUMAN_REVIEW_THRESHOLD:
            review_status = "human_review"
        else:
            review_status = "rejected"

        # 3. DB 업데이트
        if not dry_run:
            self.db.update(
                """
                UPDATE behavior_labels
                SET review_status = ?, updated_at = ?
                WHERE id = ?
                """,
                (review_status, datetime.utcnow().isoformat(), label_id),
            )

        return True

    def batch_process(self, run_id: Optional[str] = None, dry_run: bool = False) -> int:
        """
        일괄 처리: review_status 미설정인 라벨들 처리

        Args:
            run_id: 특정 run만 처리 (None이면 전체)
            dry_run: True면 DB 저장 안 함

        Returns:
            처리된 라벨 수
        """
        # review_status가 'pending'인 라벨 조회
        if run_id:
            labels = self.db.execute(
                """
                SELECT id FROM behavior_labels
                WHERE review_status = 'pending' AND run_id = ?
                ORDER BY created_at
                """,
                (run_id,),
            )
        else:
            labels = self.db.execute(
                """
                SELECT id FROM behavior_labels
                WHERE review_status = 'pending'
                ORDER BY created_at
                """
            )

        count = 0
        for label in labels:
            if self.run(label["id"], dry_run):
                count += 1

        return count
