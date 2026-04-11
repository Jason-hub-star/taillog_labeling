"""Critic 프롬프트"""

from typing import Dict


def build_critic_prompt(
    category: str,
    label: str,
    antecedent: str,
    behavior: str,
    consequence: str,
    intensity: int,
    keypoints_quality: float,
) -> str:
    """
    critic용 검수 프롬프트 생성

    Args:
        category: 행동 카테고리
        label: 행동 라벨
        antecedent: 선행 사건
        behavior: 행동 설명
        consequence: 결과
        intensity: 강도 (1-5)
        keypoints_quality: 키포인트 품질 (0~1)

    Returns:
        프롬프트 문자열
    """
    return f"""당신은 강아지 행동 분석 최종 검수자입니다.

다음 라벨이 올바른지 검증하세요.

=== 라벨 정보 ===
카테고리: {category}
라벨: {label}

=== ABC 내용 ===
선행 사건 (Antecedent): {antecedent}
행동 (Behavior): {behavior}
결과 (Consequence): {consequence}
강도: {intensity}/5

=== 키포인트 품질 ===
신뢰도: {keypoints_quality:.2f}

=== 검증 기준 ===
1. ABC의 3개 항목이 모두 존재하고 논리적으로 연결되는가?
2. 강도(intensity)가 관찰된 행동과 일치하는가?
   - 1: 거의 보이지 않음
   - 2: 경미한 반응
   - 3: 명확히 관찰됨
   - 4: 강도 높음
   - 5: 제어 어려움
3. 라벨이 정의된 21개 행동 범위 내에 있는가?
4. 키포인트 품질이 충분한가 (0.3 미만이면 감점)?

=== 응답 형식 (JSON) ===
{{
  "pass_decision": true|false,
  "confidence_adjusted": 0.0~1.0,
  "exception_reason": "불합격 사유 또는 조정 이유"
}}

주의사항:
- pass_decision: true면 통과, false면 불합격
- confidence_adjusted: 0~1 범위 (조정된 신뢰도)
- exception_reason: 선택사항 (불합격이거나 특이사항 있을 때만)
- JSON만 응답"""


def build_rule_based_critic_prompt(
    category: str, label: str, antecedent: str, behavior: str, consequence: str, intensity: int
) -> tuple:
    """
    LLM 실패 시 Rule-Based Fallback Critic

    Args:
        category: 행동 카테고리
        label: 행동 라벨
        antecedent: 선행 사건
        behavior: 행동 설명
        consequence: 결과
        intensity: 강도 (1-5)

    Returns:
        (pass: bool, confidence_adjusted: float, exception_reason: str)
    """
    # 기본 검증
    valid_categories = [
        "walk",
        "play",
        "condition",
        "alert",
        "meal",
        "social",
        "unknown",
    ]
    valid_labels = [
        "walk_pulling",
        "walk_reactive",
        "walk_fearful",
        "walk_distracted",
        "play_overexcited",
        "play_resource",
        "play_rough",
        "cond_anxious",
        "cond_destructive",
        "cond_repetitive",
        "cond_toileting",
        "alert_aggression",
        "alert_barking",
        "alert_territorial",
        "meal_guarding",
        "meal_picky",
        "meal_stealing",
        "social_reactive",
        "social_fearful",
        "social_dominant",
        "social_separation",
        "unknown",
    ]

    # 1. 카테고리 검증
    if category not in valid_categories:
        return False, 0.3, f"유효하지 않은 카테고리: {category}"

    # 2. 라벨 검증
    if label not in valid_labels:
        return False, 0.3, f"유효하지 않은 라벨: {label}"

    # 3. ABC 완전성 검증
    if not all([antecedent, behavior, consequence]):
        return False, 0.4, "ABC 항목 누락"

    # 4. 강도 범위 검증
    if not (1 <= intensity <= 5):
        return False, 0.35, f"강도 범위 오류: {intensity}"

    # 5. ABC 길이 검증 (너무 짧거나 길면 감점)
    abc_lengths = [len(antecedent), len(behavior), len(consequence)]
    if any(l < 5 for l in abc_lengths) or any(l > 200 for l in abc_lengths):
        return True, 0.65, "ABC 길이 이상 (감점)"

    # 6. 기본 통과 (LLM 실패 시 보수적 신뢰도)
    return True, 0.7, None
