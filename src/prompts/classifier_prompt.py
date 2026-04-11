"""Behavior Classifier 프롬프트"""

from typing import List, Dict


def build_classifier_prompt(keypoints_text: str, video_context: str = "") -> str:
    """
    behavior_classifier용 프롬프트 생성

    Args:
        keypoints_text: 키포인트 텍스트 표현
        video_context: 영상 메타 정보

    Returns:
        프롬프트 문자열
    """
    return f"""당신은 강아지 행동 분석 전문가입니다.

주어진 프레임의 강아지 포즈(keypoints)를 분석하여 행동 카테고리를 분류하세요.

=== 강아지 포즈 정보 ===
{keypoints_text}

=== 영상 컨텍스트 ===
{video_context if video_context else "실내 또는 실외 환경에서 일상적인 강아지 활동"}

=== 가능한 행동 카테고리 (21가지) ===
1. walk_pulling: 줄 당기기
2. walk_reactive: 산책 중 반응성
3. walk_fearful: 산책 중 공포 반응
4. walk_distracted: 산책 중 집중력 저하
5. play_overexcited: 과도한 흥분
6. play_resource: 자원 지키기 (장난감)
7. play_rough: 거친 놀이
8. cond_anxious: 분리불안 / 불안행동
9. cond_destructive: 파괴 행동
10. cond_repetitive: 반복 행동 (강박)
11. cond_toileting: 배변 문제
12. alert_aggression: 공격성
13. alert_barking: 과도한 짖음
14. alert_territorial: 영역 방어
15. meal_guarding: 음식 자원 지키기
16. meal_picky: 편식 / 식욕부진
17. meal_stealing: 음식 훔치기
18. social_reactive: 사회적 반응성
19. social_fearful: 사회적 공포
20. social_dominant: 지배 행동
21. social_separation: 분리 불안
22. unknown: 위 21개 이외의 행동

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
        keypoints: [{"x": 0.45, "y": 0.32, "c": 0.91}, ...]

    Returns:
        텍스트 표현
    """
    # COCO 17 keypoints 이름
    keypoint_names = [
        "코",
        "왼쪽_눈",
        "오른쪽_눈",
        "왼쪽_귀",
        "오른쪽_귀",
        "왼쪽_어깨",
        "오른쪽_어깨",
        "왼쪽_팔꿈치",
        "오른쪽_팔꿈치",
        "왼쪽_손목",
        "오른쪽_손목",
        "왼쪽_엉덩이",
        "오른쪽_엉덩이",
        "왼쪽_무릎",
        "오른쪽_무릎",
        "왼쪽_발목",
        "오른쪽_발목",
    ]

    lines = []
    for i, kp in enumerate(keypoints):
        if i < len(keypoint_names):
            name = keypoint_names[i]
            x, y, c = kp.get("x", 0), kp.get("y", 0), kp.get("c", 0)
            lines.append(f"- {name}: 위치=({x:.2f}, {y:.2f}), 신뢰도={c:.2f}")

    return "\n".join(lines) if lines else "키포인트 정보 없음"
