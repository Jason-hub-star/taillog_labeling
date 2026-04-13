"""Behavior Classifier 프롬프트 — LABEL-SCHEMA.md v3.0 기준"""

from typing import List, Dict

from src.utils.label_constants import ALL_LABELS, LABEL_TO_KO, LABEL_TO_CATEGORY


def build_classifier_prompt(keypoints_text: str, video_context: str = "") -> str:
    """
    behavior_classifier용 프롬프트 생성 (keypoints 기반)

    Note: Phase 3 이후 Vision LLM 기반 분류는 vision_classifier_prompt.py 사용

    Args:
        keypoints_text: 키포인트 텍스트 표현
        video_context: 영상 메타 정보

    Returns:
        프롬프트 문자열
    """
    # label_constants에서 동적 생성 (하드코딩 금지)
    behavior_labels = [l for l in ALL_LABELS if l != "unknown"]  # unknown 명시 제외
    labels_str = "\n".join(
        f"{i + 1}. {label}: {LABEL_TO_KO[label]}"
        for i, label in enumerate(behavior_labels)
    )
    total = len(behavior_labels)

    return f"""당신은 강아지 행동 분석 전문가입니다.

주어진 프레임의 강아지 포즈(keypoints)를 분석하여 행동 카테고리를 분류하세요.

=== 강아지 포즈 정보 ===
{keypoints_text}

=== 영상 컨텍스트 ===
{video_context if video_context else "실내 또는 실외 환경에서 일상적인 강아지 활동"}

=== 가능한 행동 카테고리 ({total}가지) ===
{labels_str}
{total + 1}. unknown: 위 {total}개 이외의 행동

=== 응답 형식 (JSON) ===
{{
  "category": "(walk|play|condition|alert|meal|social|unknown)",
  "label": "(preset_id)",
  "confidence": 0.0~1.0
}}

주의사항:
- category와 label은 위 목록에서만 선택
- confidence는 0~1 범위의 소수점 (기본값 없으면 0.6)
- 확실하지 않으면 "unknown"으로 분류
- JSON만 응답하고 다른 설명은 없을 것"""


def keypoints_to_text(keypoints: List[Dict]) -> str:
    """
    키포인트를 텍스트로 변환

    Args:
        keypoints: [{"bodypart": "nose", "x": 0.45, "y": 0.32, "c": 0.91}, ...]
                   A-07: SuperAnimal 39pt bodypart 필드 직접 사용 (COCO 인덱스 매핑 금지)

    Returns:
        텍스트 표현
    """
    # confidence 0.3 미만 키포인트 제외 (저품질 필터)
    valid_kps = [kp for kp in keypoints if kp.get("c", 0) >= 0.3]

    if not valid_kps:
        return "키포인트 정보 없음 (신뢰도 0.3 미만 전부 제외)"

    lines = []
    for kp in valid_kps:
        name = kp.get("bodypart", "unknown")  # A-07: bodypart 필드 직접 사용
        x, y, c = kp.get("x", 0), kp.get("y", 0), kp.get("c", 0)
        lines.append(f"- {name}: ({x:.0f}, {y:.0f}), 신뢰도={c:.2f}")

    return "\n".join(lines)
