"""모델 테스트"""

import pytest
from src.core.models import KeyPoint, PoseResult, BehaviorLabel, LabelingRun


def test_keypoint_creation():
    """KeyPoint 생성"""
    kp = KeyPoint(x=0.5, y=0.5, c=0.9)
    assert kp.x == 0.5
    assert kp.y == 0.5
    assert kp.c == 0.9


def test_pose_result_creation():
    """PoseResult 생성"""
    keypoints = [KeyPoint(x=0.5, y=0.5, c=0.9) for _ in range(17)]
    pose = PoseResult(run_id="run1", frame_id=0, keypoints=keypoints, confidence=0.95)

    assert pose.run_id == "run1"
    assert pose.frame_id == 0
    assert len(pose.keypoints) == 17
    assert pose.confidence == 0.95


def test_behavior_label_creation():
    """BehaviorLabel 생성"""
    label = BehaviorLabel(
        run_id="run1",
        frame_id=0,
        preset_id="walk_pulling",
        category="walk",
        label="walk_pulling",
        llm_confidence=0.8,
        consistency_score=0.7,
        keypoint_quality=0.75,
        confidence=0.75,
        labeler_model="gemma4-unsloth-e4b:latest",
    )

    assert label.category == "walk"
    assert label.preset_id == "walk_pulling"
    assert label.review_status == "pending"
    assert label.synced is False


def test_labeling_run_creation():
    """LabelingRun 생성"""
    run = LabelingRun(
        url="https://youtube.com/watch?v=abc123",
        title="강아지 일상",
        channel="My Dog",
        duration_s=120,
        video_path="/path/to/video.mp4",
    )

    assert run.url == "https://youtube.com/watch?v=abc123"
    assert run.status == "pending"
