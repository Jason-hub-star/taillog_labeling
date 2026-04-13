"""Vision Classifier 프롬프트 — gemma4:26b Vision LLM용 (영어)

Phase 1: 단일 프레임 zero-shot
Phase 2+: 5프레임 콜라주 + few-shot (추후 확장)
"""

from src.utils.label_constants import CATEGORIES, LABEL_TO_KO, IS_PROBLEMATIC, NORMAL_CUES


def build_vision_classifier_prompt(video_context: str = "") -> str:
    """
    Vision LLM용 프롬프트 생성.

    - 모든 카테고리는 label_constants에서 동적 참조 (하드코딩 금지)
    - reasoning → 호출부에서 reviewer_note에 [AI] prefix로 저장
    - 프롬프트 언어: 영어 (Vision LLM 정확도 우선)

    Args:
        video_context: 영상 메타 정보 (선택)

    Returns:
        프롬프트 문자열
    """
    context_line = (
        f"Video context: {video_context}"
        if video_context
        else "Context: Indoor or outdoor daily dog activity"
    )
    category_block = _format_categories()

    return f"""You are an expert in dog behavior analysis.

Analyze the provided dog image and classify the behavior into exactly one of the 23 preset categories below.

{context_line}

=== BEHAVIOR CATEGORIES ===
{category_block}

=== RESPONSE FORMAT ===
Respond with JSON only. No extra text.

{{
  "preset_id": "<preset_id from the list above>",
  "category": "<walk|play|condition|alert|meal|social|unknown>",
  "is_problematic": <true|false|null>,
  "confidence": <0.0 to 1.0>,
  "reasoning": "<2-3 sentences describing the specific visual evidence>"
}}

=== RULES ===
- preset_id MUST be one of the IDs listed above (e.g. walk_normal, walk_pulling)
- Use "unknown" only when no category clearly matches the observed behavior
- confidence: 0.85+ if very certain, 0.65-0.84 if somewhat certain, 0.3-0.64 if uncertain
- reasoning: cite specific visual cues (posture, tail position, ear angle, muscle tension, leash tension, etc.)
- is_problematic: true for problem behaviors, false for normal, null for unknown"""


def _format_categories() -> str:
    """label_constants 공개 상수에서 동적으로 카테고리 블록 생성 (_LABEL_DEFS private 접근 금지)."""
    _CATEGORY_DISPLAY = {
        "walk": "Walk", "play": "Play", "condition": "Condition",
        "alert": "Alert", "meal": "Meal", "social": "Social",
    }

    lines = []
    for cat, labels in CATEGORIES.items():
        cat_label = _CATEGORY_DISPLAY.get(cat, cat.upper())
        lines.append(f"\n[{cat_label}]")
        for preset_id in labels:
            ko_name = LABEL_TO_KO.get(preset_id, preset_id)
            is_prob = IS_PROBLEMATIC.get(preset_id)
            flag = "[PROBLEMATIC]" if is_prob else "[NORMAL]"
            cue = NORMAL_CUES.get(preset_id, "")
            cue_str = f" | Visual cue: {cue}" if cue else ""
            lines.append(f"  • {preset_id} ({ko_name}) {flag}{cue_str}")

    lines.append("\n[Unknown]")
    lines.append("  • unknown — Use when no category clearly matches")

    return "\n".join(lines)
