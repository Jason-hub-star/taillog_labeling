"""Behavior Classifier 에이전트 — Vision LLM 기반 행동 분류 (Phase 3)

Phase 3: gemma4:26b Vision LLM + 프레임 이미지 (단일 프레임 zero-shot)
  - 입력: 프레임 JPEG 이미지
  - 출력: preset_id, category, confidence, reasoning

Phase 2+ 예정:
  - 5프레임 콜라주 + few-shot 프롬프트
  - 처리 시간: 12초/프레임 → ~2초/프레임
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from src.core.database import get_db
from src.core.image_utils import load_frame_image, image_to_base64
from src.core.llm import get_ollama_client
from src.core.models import ClassifierOutput, BehaviorLabel
from src.prompts.vision_classifier_prompt import build_vision_classifier_prompt
from src.utils.config import Config
from src.utils.label_constants import IS_PROBLEMATIC, LABEL_TO_CATEGORY


class BehaviorClassifier:
    """Vision LLM 기반 행동 분류 에이전트"""

    MODEL = Config.BEHAVIOR_CLASSIFIER_MODEL  # gemma4:26b-a4b-it-q4_K_M
    RETRY_COUNT = 3

    def __init__(self):
        self.db = get_db()
        self.llm = get_ollama_client()

    def run(
        self,
        run_id: str,
        frame_id: int,
        keypoints_json: str,
        frame_path: Optional[str] = None,
        video_context: str = "",
        dry_run: bool = False,
    ) -> Optional[BehaviorLabel]:
        """
        단일 프레임을 Vision LLM으로 행동 분류.

        Args:
            run_id: labeling_runs.id
            frame_id: 프레임 번호
            keypoints_json: pose_results.keypoints_json (keypoint_quality 계산용)
            frame_path: 프레임 JPEG 절대 경로 (없으면 unknown 반환)
            video_context: 영상 메타 정보 (선택)
            dry_run: True면 DB 저장 안 함

        Returns:
            BehaviorLabel (pending 상태) 또는 None (실패)
        """
        # keypoints 파싱 (keypoint_quality 계산용)
        try:
            keypoints = json.loads(keypoints_json)
        except json.JSONDecodeError:
            keypoints = []

        # Vision LLM 분류
        classifier_output = self._call_vision_llm(frame_path, video_context)

        # 신뢰도 계산
        keypoint_quality = self._calculate_keypoint_quality(keypoints)
        consistency_score = 0.5  # 단일 프레임 기본값
        confidence = (
            classifier_output.confidence * 0.5
            + consistency_score * 0.3
            + keypoint_quality * 0.2
        )

        # preset_id → is_problematic / category 검증 (label_constants SSOT)
        preset_id = classifier_output.label
        is_problematic = IS_PROBLEMATIC.get(preset_id)
        category = LABEL_TO_CATEGORY.get(preset_id, preset_id)

        # reasoning → reviewer_note ([AI] prefix)
        reviewer_note = (
            f"[AI] {classifier_output.reasoning}"
            if classifier_output.reasoning
            else None
        )

        label = BehaviorLabel(
            id=str(uuid.uuid4()),
            run_id=run_id,
            frame_id=frame_id,
            preset_id=preset_id,
            category=category,
            label=preset_id,
            llm_confidence=classifier_output.confidence,
            consistency_score=consistency_score,
            keypoint_quality=keypoint_quality,
            confidence=confidence,
            review_status="pending",
            labeler_model=self.MODEL,
        )

        if not dry_run:
            try:
                self.db.insert(
                    """
                    INSERT INTO behavior_labels
                    (id, run_id, frame_id, preset_id, category, label,
                     llm_confidence, consistency_score, keypoint_quality, confidence,
                     is_problematic, review_status, reviewer_note, labeler_model, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        is_problematic,
                        label.review_status,
                        reviewer_note,
                        label.labeler_model,
                        label.created_at.isoformat(),
                    ),
                )
            except Exception as e:
                print(f"DB 저장 실패: {str(e)}")
                return None

        return label

    # ── 내부 메서드 ────────────────────────────────────────────────────────────

    def _call_vision_llm(
        self, frame_path: Optional[str], video_context: str
    ) -> ClassifierOutput:
        """
        Vision LLM 호출 → ClassifierOutput 반환.
        프레임 없거나 LLM 실패 시 unknown(0.3) 반환.
        """
        _FALLBACK = ClassifierOutput(category="unknown", label="unknown", confidence=0.3)

        # 프레임 이미지 로드
        if not frame_path:
            print("[WARN] frame_path 없음 → unknown 반환")
            return _FALLBACK

        image_bytes = load_frame_image(frame_path)
        if image_bytes is None:
            print(f"[WARN] 프레임 이미지 없음: {frame_path} → unknown 반환")
            return _FALLBACK

        image_base64 = image_to_base64(image_bytes)
        prompt = build_vision_classifier_prompt(video_context)

        try:
            response = self.llm.generate_with_image(
                model=self.MODEL,
                prompt=prompt,
                image_base64=image_base64,
                temperature=0.3,
                retry_count=self.RETRY_COUNT,
            )
            result = self.llm.parse_json_response(response["content"])

            return ClassifierOutput(
                category=result.get("category", "unknown"),
                label=result.get("preset_id", "unknown"),
                confidence=float(result.get("confidence", 0.3)),
                reasoning=result.get("reasoning"),
            )
        except Exception as e:
            print(f"[WARN] Vision LLM 분류 실패 → unknown 반환: {str(e)}")
            return _FALLBACK

    def _calculate_keypoint_quality(self, keypoints: list) -> float:
        """키포인트 품질 계산 (평균 신뢰도)."""
        if not keypoints:
            return 0.3

        confidences = [kp.get("c", 0) for kp in keypoints]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.3

        detected_count = sum(1 for c in confidences if c > 0.3)
        if detected_count < len(keypoints) / 2:
            avg_confidence *= 0.5

        return min(1.0, max(0.1, avg_confidence))
