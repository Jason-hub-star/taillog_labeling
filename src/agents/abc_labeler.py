"""ABC Labeler 에이전트 — ABC 라벨 생성"""

import json
import uuid
from datetime import datetime
from typing import Optional, List

from src.core.database import get_db
from src.core.llm import get_ollama_client
from src.core.models import ABCLabelerOutput, BehaviorLabel
from src.prompts.abc_labeler_prompt import build_abc_labeler_prompt


class ABCLabeler:
    """ABC 라벨 생성 에이전트 (gemma4-unsloth-e4b)"""

    MODEL = "gemma4-unsloth-e4b:latest"
    RETRY_COUNT = 3

    def __init__(self):
        self.db = get_db()
        self.llm = get_ollama_client()

    def run(self, label_id: str, dry_run: bool = False) -> Optional[BehaviorLabel]:
        """
        이미 분류된 라벨에 ABC (Antecedent-Behavior-Consequence) 추가

        Args:
            label_id: behavior_labels.id
            dry_run: True면 DB 저장 안 함

        Returns:
            업데이트된 BehaviorLabel 객체 또는 None
        """
        # 1. 기존 라벨 조회
        result = self.db.execute_one(
            "SELECT * FROM behavior_labels WHERE id = ?", (label_id,)
        )
        if not result:
            print(f"라벨 없음: {label_id}")
            return None

        run_id = result["run_id"]
        frame_id = result["frame_id"]
        category = result["category"]
        label = result["label"]

        # 2. 키포인트 시퀀스 조회 (±2 프레임)
        keypoints_sequence = self._get_keypoints_sequence(run_id, frame_id)

        # 3. 프롬프트 구성
        prompt = build_abc_labeler_prompt(category, label, keypoints_sequence)

        # 4. LLM 호출
        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.chat(
                model=self.MODEL,
                messages=messages,
                temperature=0.3,
                retry_count=self.RETRY_COUNT,
            )
            result_dict = self.llm.parse_json_response(response["content"])
            abc_output = ABCLabelerOutput(**result_dict)
        except Exception as e:
            print(f"ABC LLM 실패: {str(e)}")
            # critic에 raw response 전달하기 위해 critic mandatory 처리
            if not dry_run:
                self.db.update(
                    """
                    UPDATE behavior_labels
                    SET review_status = 'pending', critic_note = ?
                    WHERE id = ?
                    """,
                    (f"ABC 생성 실패: {str(e)}", label_id),
                )
            return None

        # 5. 신뢰도 조정
        existing_confidence = result["confidence"]
        adjusted_confidence = (existing_confidence + abc_output.confidence) / 2

        # 6. DB 업데이트
        if not dry_run:
            try:
                self.db.update(
                    """
                    UPDATE behavior_labels
                    SET antecedent = ?, behavior = ?, consequence = ?,
                        intensity = ?, confidence = ?,
                        llm_confidence = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        abc_output.antecedent,
                        abc_output.behavior,
                        abc_output.consequence,
                        abc_output.intensity,
                        adjusted_confidence,
                        abc_output.confidence,
                        datetime.utcnow().isoformat(),
                        label_id,
                    ),
                )
            except Exception as e:
                print(f"DB 업데이트 실패: {str(e)}")
                return None

        # 7. 업데이트된 라벨 반환
        updated = self.db.execute_one(
            "SELECT * FROM behavior_labels WHERE id = ?", (label_id,)
        )
        if updated:
            return self._row_to_behavior_label(updated)

        return None

    def _get_keypoints_sequence(self, run_id: str, frame_id: int) -> List[dict]:
        """
        프레임 주변 keypoints 시퀀스 조회 (±2 프레임)

        Args:
            run_id: labeling_runs.id
            frame_id: 중심 프레임

        Returns:
            [{"frame_id": 100, "keypoints": [...]}, ...]
        """
        # 현재 프레임과 ±2 프레임
        frame_ids = [frame_id - 2, frame_id - 1, frame_id, frame_id + 1, frame_id + 2]

        placeholders = ",".join("?" * len(frame_ids))
        rows = self.db.execute(
            f"""
            SELECT frame_id, keypoints_json FROM pose_results
            WHERE run_id = ? AND frame_id IN ({placeholders})
            ORDER BY frame_id
            """,
            (run_id, *frame_ids),
        )

        sequence = []
        for row in rows:
            try:
                keypoints = json.loads(row["keypoints_json"])
                sequence.append({"frame_id": row["frame_id"], "keypoints": keypoints})
            except json.JSONDecodeError:
                pass

        return sequence

    def _row_to_behavior_label(self, row: dict) -> BehaviorLabel:
        """DB 행을 BehaviorLabel로 변환"""
        return BehaviorLabel(
            id=row["id"],
            run_id=row["run_id"],
            frame_id=row["frame_id"],
            preset_id=row["preset_id"],
            category=row["category"],
            label=row["label"],
            antecedent=row["antecedent"],
            behavior=row["behavior"],
            consequence=row["consequence"],
            intensity=row["intensity"],
            llm_confidence=row["llm_confidence"],
            consistency_score=row["consistency_score"],
            keypoint_quality=row["keypoint_quality"],
            confidence=row["confidence"],
            review_status=row["review_status"],
            critic_pass=row["critic_pass"],
            critic_note=row["critic_note"],
            labeler_model=row["labeler_model"],
            synced=bool(row["synced"]),
            taillog_log_id=row["taillog_log_id"],
        )
