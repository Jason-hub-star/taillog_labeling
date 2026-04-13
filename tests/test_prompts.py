"""프롬프트 테스트"""

import pytest
from src.prompts.classifier_prompt import build_classifier_prompt, keypoints_to_text
from src.prompts.abc_labeler_prompt import build_abc_labeler_prompt
from src.utils.label_constants import ALL_LABELS, PROBLEM_LABELS


def test_keypoints_to_text():
    """키포인트 텍스트 변환 — A-07 포맷: bodypart 이름 직접 사용"""
    keypoints = [
        {"bodypart": "nose", "x": 0.5, "y": 0.5, "c": 0.9},
        {"bodypart": "left_ear", "x": 0.6, "y": 0.4, "c": 0.85},
        {"bodypart": "right_ear", "x": 0.4, "y": 0.6, "c": 0.8},
    ]

    text = keypoints_to_text(keypoints)
    assert "nose" in text
    assert "left_ear" in text
    assert "신뢰도" in text


def test_classifier_prompt_contains_all_labels():
    """Classifier 프롬프트 — label_constants의 모든 라벨 포함 확인"""
    keypoints = [{"bodypart": "nose", "x": 0.5, "y": 0.5, "c": 0.9} for _ in range(17)]
    keypoints_text = keypoints_to_text(keypoints)

    prompt = build_classifier_prompt(keypoints_text, "실내 환경")

    assert "강아지 행동 분석" in prompt
    assert "JSON" in prompt
    assert "unknown" in prompt
    # label_constants 기준 라벨이 모두 포함되어야 함
    for label in ALL_LABELS:
        assert label in prompt, f"라벨 누락: {label}"


def test_classifier_prompt_no_legacy_labels():
    """제거된 구 라벨이 프롬프트에 없어야 함"""
    keypoints = [{"bodypart": "nose", "x": 0.5, "y": 0.5, "c": 0.9}]
    prompt = build_classifier_prompt(keypoints_to_text(keypoints))

    removed = [
        "walk_fearful", "walk_distracted", "play_rough",
        "cond_destructive", "cond_repetitive", "cond_toileting",
        "alert_barking", "alert_territorial",
        "meal_guarding", "meal_picky", "meal_stealing",
        "social_fearful", "social_dominant", "social_separation",
    ]
    for label in removed:
        assert label not in prompt, f"제거된 라벨이 프롬프트에 남아있음: {label}"


def test_abc_labeler_prompt():
    """ABC Labeler 프롬프트 — intensity 1-10 범위 포함 확인"""
    keypoints_sequence = [
        {
            "frame_id": 100,
            "keypoints": [
                {"bodypart": "nose", "x": 0.5, "y": 0.5, "c": 0.9},
                {"bodypart": "left_ear", "x": 0.6, "y": 0.4, "c": 0.85},
            ],
        }
    ]

    prompt = build_abc_labeler_prompt("walk", "walk_pulling", keypoints_sequence)

    assert "Antecedent" in prompt
    assert "Behavior" in prompt
    assert "Consequence" in prompt
    assert "intensity" in prompt
    assert "JSON" in prompt
    assert "1-10" in prompt  # v3.0: intensity 척도 1-10
