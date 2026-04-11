"""프롬프트 테스트"""

import pytest
from src.prompts.classifier_prompt import build_classifier_prompt, keypoints_to_text
from src.prompts.abc_labeler_prompt import build_abc_labeler_prompt


def test_keypoints_to_text():
    """키포인트 텍스트 변환"""
    keypoints = [
        {"x": 0.5, "y": 0.5, "c": 0.9},
        {"x": 0.6, "y": 0.4, "c": 0.85},
        {"x": 0.4, "y": 0.6, "c": 0.8},
    ]

    text = keypoints_to_text(keypoints)
    assert "코" in text
    assert "위치" in text
    assert "신뢰도" in text


def test_classifier_prompt():
    """Classifier 프롬프트 생성"""
    keypoints = [{"x": 0.5, "y": 0.5, "c": 0.9} for _ in range(17)]
    keypoints_text = keypoints_to_text(keypoints)

    prompt = build_classifier_prompt(keypoints_text, "실내 환경")

    assert "강아지 행동 분석" in prompt
    assert "walk_pulling" in prompt
    assert "JSON" in prompt


def test_abc_labeler_prompt():
    """ABC Labeler 프롬프트 생성"""
    keypoints_sequence = [
        {
            "frame_id": 100,
            "keypoints": [
                {"x": 0.5, "y": 0.5, "c": 0.9},
                {"x": 0.6, "y": 0.4, "c": 0.85},
            ],
        }
    ]

    prompt = build_abc_labeler_prompt("walk", "walk_pulling", keypoints_sequence)

    assert "Antecedent" in prompt
    assert "Behavior" in prompt
    assert "Consequence" in prompt
    assert "intensity" in prompt
    assert "JSON" in prompt
