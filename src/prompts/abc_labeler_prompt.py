"""ABC Labeler 프롬프트"""

from typing import List, Dict


def build_abc_labeler_prompt(
    category: str, label: str, keypoints_sequence: List[Dict]
) -> str:
    """
    abc_labeler용 프롬프트 생성

    Args:
        category: 행동 카테고리
        label: 행동 라벨 (preset_id)
        keypoints_sequence: 연속 프레임 keypoints 시퀀스

    Returns:
        프롬프트 문자열
    """
    keypoints_text = keypoints_sequence_to_text(keypoints_sequence)

    return f"""당신은 강아지 행동 분석 전문가입니다.

주어진 행동의 ABC (Antecedent-Behavior-Consequence) 시나리오를 작성하세요.

=== 식별된 행동 ===
카테고리: {category}
라벨: {label}

=== 연속 프레임 포즈 시퀀스 ===
{keypoints_text}

=== ABC 프레임워크 설명 ===
- Antecedent (선행): 행동 직전에 일어난 사건/자극
- Behavior (행동): 강아지가 실제로 보인 구체적인 행동
- Consequence (결과): 행동 직후 일어난 결과/반응

=== 강도 척도 (1-10) ===
1-2. 미미한 반응: 행동이 거의 보이지 않음
3-4. 약함: 경미한 반응, 쉽게 중단
5-6. 보통: 명확히 관찰되고 지속적
7-8. 강함: 강도 높음, 개입 필요
9-10. 제어 어려움: 즉각 개입 필요

=== 응답 형식 (JSON) ===
{{
  "antecedent": "구체적인 선행 사건",
  "behavior": "관찰된 행동의 상세 설명",
  "consequence": "행동 후 결과 또는 반응",
  "intensity": 6,
  "confidence": 0.0~1.0
}}

주의사항:
- antecedent, behavior, consequence는 각각 20~50자 범위
- intensity는 1~10 정수 (TaillogToss 기준)
- confidence는 0~1 범위의 소수점
- 불확실하면 confidence를 낮춤 (기본값 0.6)
- JSON만 응답"""


def keypoints_sequence_to_text(keypoints_sequence: List[Dict]) -> str:
    """
    연속 프레임 keypoints를 텍스트로 변환

    Args:
        keypoints_sequence: [{"frame_id": 100, "keypoints": [...]}, ...]

    Returns:
        텍스트 표현
    """
    if not keypoints_sequence:
        return "시퀀스 정보 없음"

    lines = []
    for i, frame_data in enumerate(keypoints_sequence[:5]):  # 최대 5프레임
        frame_id = frame_data.get("frame_id", i)
        keypoints = frame_data.get("keypoints", [])

        lines.append(f"프레임 {frame_id}:")

        # A-07: bodypart 필드 직접 사용 (하드코딩 금지)
        for kp in keypoints:
            name = kp.get("bodypart", "unknown")
            x, y, c = kp.get("x", 0), kp.get("y", 0), kp.get("c", 0)
            if c > 0.3:  # 신뢰도 낮으면 생략
                lines.append(f"  - {name}: ({x:.2f}, {y:.2f})")

    return "\n".join(lines)
