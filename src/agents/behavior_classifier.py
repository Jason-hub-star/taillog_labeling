"""Behavior Classifier 에이전트 — 행동 분류"""

import json
import uuid
from datetime import datetime
from typing import Optional, Dict

from src.core.database import get_db
from src.core.llm import get_ollama_client
from src.core.models import ClassifierOutput, BehaviorLabel
from src.prompts.classifier_prompt import build_classifier_prompt, keypoints_to_text


class BehaviorClassifier:
    """행동 분류 에이전트 (gemma4-unsloth-e4b)"""

    MODEL = "gemma4-unsloth-e4b:latest"
    RETRY_COUNT = 3

    def __init__(self):
        self.db = get_db()
        self.llm = get_ollama_client()

    def run(
        self,
        run_id: str,
        frame_id: int,
        keypoints_json: str,
        video_context: str = "",
        dry_run: bool = False,
    ) -> Optional[BehaviorLabel]:
        """
        단일 프레임을 행동 분류

        Args:
            run_id: labeling_runs.id
            frame_id: 프레임 번호
            keypoints_json: pose_results.keypoints_json
            video_context: 영상 메타 정보
            dry_run: True면 DB 저장 안 함

        Returns:
            BehaviorLabel 객체 (pending 상태) 또는 None (실패)
        """
        # 1. keypoints 파싱
        try:
            keypoints = json.loads(keypoints_json)
        except json.JSONDecodeError:
            print(f"Invalid keypoints JSON: {keypoints_json[:100]}")
            return None

        # 2. 프롬프트 구성
        keypoints_text = keypoints_to_text(keypoints)
        prompt = build_classifier_prompt(keypoints_text, video_context)

        # 3. LLM 호출
        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.chat(
                model=self.MODEL,
                messages=messages,
                temperature=0.3,
                retry_count=self.RETRY_COUNT,
            )
            result = self.llm.parse_json_response(response["content"])
            classifier_output = ClassifierOutput(**result)
        except Exception as e:
            print(f"LLM 분류 실패: {str(e)}")
            # critic에 전달하기 위해 기본값으로 생성 후 반환
            classifier_output = ClassifierOutput(
                category="unknown",
                label="unknown",
                confidence=0.3,
            )

        # 4. 신뢰도 계산 (1차 — consistency_score, keypoint_quality는 이후 계산)
        keypoint_quality = self._calculate_keypoint_quality(keypoints)
        consistency_score = 0.5  # 단일 프레임이므로 기본값

        confidence = (
            classifier_output.confidence * 0.5
            + consistency_score * 0.3
            + keypoint_quality * 0.2
        )

        # 5. BehaviorLabel 생성
        label = BehaviorLabel(
            id=str(uuid.uuid4()),
            run_id=run_id,
            frame_id=frame_id,
            preset_id=classifier_output.label,
            category=classifier_output.category,
            label=classifier_output.label,
            llm_confidence=classifier_output.confidence,
            consistency_score=consistency_score,
            keypoint_quality=keypoint_quality,
            confidence=confidence,
            review_status="pending",
            labeler_model=self.MODEL,
        )

        # 6. DB 저장
        if not dry_run:
            try:
                self.db.insert(
                    """
                    INSERT INTO behavior_labels
                    (id, run_id, frame_id, preset_id, category, label,
                     llm_confidence, consistency_score, keypoint_quality, confidence,
                     review_status, labeler_model, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        label.id,
                        label.run_id,
                        label.frame_id,
                        label.preset_id,
                        label.category,
                        label.label,
                        label.llm_confidence,
                        label.consistency_score,
                        label.keypoint_quality,
                        label.confidence,
                        label.review_status,
                        label.labeler_model,
                        label.created_at.isoformat(),
                    ),
                )
            except Exception as e:
                print(f"DB 저장 실패: {str(e)}")
                return None

        return label

    def _calculate_keypoint_quality(self, keypoints: list) -> float:
        """
        키포인트 품질 계산 (평균 신뢰도)

        Args:
            keypoints: [{"x": 0.45, "y": 0.32, "c": 0.91}, ...]

        Returns:
            0~1 범위 신뢰도
        """
        if not keypoints:
            return 0.3

        confidences = [kp.get("c", 0) for kp in keypoints]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.3

        # 탐지된 keypoints가 절반 미만이면 패널티
        detected_count = sum(1 for c in confidences if c > 0.1)
        if detected_count < len(keypoints) / 2:
            avg_confidence *= 0.5

        return min(1.0, max(0.1, avg_confidence))
