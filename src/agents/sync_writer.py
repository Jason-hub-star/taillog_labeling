"""Sync Writer 에이전트 — Supabase 동기화"""

import json
import random
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

from src.core.database import get_db
from src.core.supabase_client import get_supabase_client


class SyncWriter:
    """Supabase 동기화 에이전트"""

    # SUPABASE-SYNC-CONTRACT 기준
    SYNC_CONDITIONS = {
        "confidence_min": 0.85,
        "review_status": "auto_approved",
        "synced": False,
    }

    # OD-02 미결: 임시 preset_id → type_id 매핑
    PRESET_TO_TYPE_ID = {
        "walk_pulling": 1,
        "walk_reactive": 2,
        "walk_fearful": 3,
        "walk_distracted": 4,
        "play_overexcited": 5,
        "play_resource": 6,
        "play_rough": 7,
        "cond_anxious": 8,
        "cond_destructive": 9,
        "cond_repetitive": 10,
        "cond_toileting": 11,
        "alert_aggression": 12,
        "alert_barking": 13,
        "alert_territorial": 14,
        "meal_guarding": 15,
        "meal_picky": 16,
        "meal_stealing": 17,
        "social_reactive": 18,
        "social_fearful": 19,
        "social_dominant": 20,
        "social_separation": 21,
        "unknown": None,
    }

    # OD-01 미결: 임시 anonymous dog
    ANONYMOUS_DOG_ID = "labeling_pipeline_v1"

    def __init__(self, retry_count: int = 3):
        self.db = get_db()
        self.supabase = get_supabase_client()
        self.retry_count = retry_count

    def run(self, label_id: str, dry_run: bool = False) -> bool:
        """
        라벨을 Supabase behavior_logs에 sync

        Args:
            label_id: behavior_labels.id
            dry_run: True면 Supabase 저장 안 함

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

        # 2. sync 조건 검사
        if not self._check_sync_conditions(result):
            return False

        # 3. run 조회 (occurred_at 계산용)
        run_result = self.db.execute_one(
            "SELECT * FROM labeling_runs WHERE id = ?", (result["run_id"],)
        )
        if not run_result:
            return False

        # 4. Supabase 데이터 구성
        preset_id = result["preset_id"]
        type_id = self.PRESET_TO_TYPE_ID.get(preset_id)

        if type_id is None:
            # unknown 라벨은 sync 제외
            print(f"Unknown 라벨은 sync 제외: {label_id}")
            return False

        # occurred_at 계산: run.created_at + frame_id초 (1 FPS 기준)
        frame_id = result["frame_id"]
        run_created_at = datetime.fromisoformat(run_result["created_at"])
        occurred_at = (run_created_at + timedelta(seconds=frame_id)).isoformat()

        payload = {
            "dog_id": self.ANONYMOUS_DOG_ID,
            "type_id": type_id,
            "antecedent": result["antecedent"],
            "behavior": result["behavior"],
            "consequence": result["consequence"],
            "intensity": result["intensity"],
            "occurred_at": occurred_at,
            "is_quick_log": False,
        }

        # 5. Supabase INSERT (retry 포함)
        taillog_log_id = None
        for attempt in range(self.retry_count):
            try:
                if not dry_run:
                    response = self.supabase.insert_behavior_log(payload)
                    if response and isinstance(response, dict):
                        taillog_log_id = response.get("id")
                    else:
                        taillog_log_id = str(uuid.uuid4())  # fallback
                else:
                    taillog_log_id = str(uuid.uuid4())

                # 6. sync_attempts 기록
                self.db.insert(
                    """
                    INSERT INTO sync_attempts
                    (id, label_id, attempt_at, success, error_msg)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        label_id,
                        datetime.utcnow().isoformat(),
                        True,
                        None,
                    ),
                )

                # 7. behavior_labels 업데이트 (synced=TRUE, review_status=synced)
                self.db.update(
                    """
                    UPDATE behavior_labels
                    SET synced = 1, taillog_log_id = ?,
                        review_status = 'synced', updated_at = ?
                    WHERE id = ?
                    """,
                    (taillog_log_id, datetime.utcnow().isoformat(), label_id),
                )

                return True

            except Exception as e:
                error_msg = str(e)
                print(f"Sync 실패 (시도 {attempt + 1}/{self.retry_count}): {error_msg}")

                # sync_attempts 기록
                self.db.insert(
                    """
                    INSERT INTO sync_attempts
                    (id, label_id, attempt_at, success, error_msg)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        label_id,
                        datetime.utcnow().isoformat(),
                        False,
                        error_msg,
                    ),
                )

                # HALT 조건 확인
                if self._is_halt_condition(error_msg):
                    raise RuntimeError(f"HALT 조건: {error_msg}")

                # exponential backoff
                if attempt < self.retry_count - 1:
                    backoff = 2 ** attempt + random.uniform(0, 1)
                    time.sleep(backoff)

        # 모든 시도 실패
        return False

    def _check_sync_conditions(self, label: dict) -> bool:
        """sync 조건 확인"""
        return (
            label["confidence"] >= self.SYNC_CONDITIONS["confidence_min"]
            and label["review_status"] == self.SYNC_CONDITIONS["review_status"]
            and not label["synced"]
        )

    def _is_halt_condition(self, error_msg: str) -> bool:
        """HALT 조건 확인"""
        halt_keywords = [
            "schema mismatch",
            "RLS violation",
            "permission denied",
        ]
        return any(keyword in error_msg.lower() for keyword in halt_keywords)

    def batch_sync(self, run_id: Optional[str] = None, dry_run: bool = False) -> tuple:
        """
        일괄 sync: review_status='auto_approved'인 라벨들 sync

        Args:
            run_id: 특정 run만 처리 (None이면 전체)
            dry_run: True면 Supabase 저장 안 함

        Returns:
            (성공 개수, 실패 개수)
        """
        if run_id:
            labels = self.db.execute(
                """
                SELECT id FROM behavior_labels
                WHERE review_status = 'auto_approved'
                  AND synced = 0
                  AND run_id = ?
                ORDER BY created_at
                """,
                (run_id,),
            )
        else:
            labels = self.db.execute(
                """
                SELECT id FROM behavior_labels
                WHERE review_status = 'auto_approved' AND synced = 0
                ORDER BY created_at
                """
            )

        success_count = 0
        fail_count = 0

        for label in labels:
            if self.run(label["id"], dry_run):
                success_count += 1
            else:
                fail_count += 1

        return success_count, fail_count
