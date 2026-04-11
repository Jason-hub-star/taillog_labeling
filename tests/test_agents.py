"""
에이전트 단위 테스트
— python-testing-patterns 스킬 기반: AAA 패턴, fixture, mock, 예외 경로 테스트
"""

import json
import os
import uuid
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.core.database import Database
from src.core.models import BatchResult, BehaviorLabel, LabelingRun


# ──────────────────────────────────────────────────────────
# Fixtures (python-testing-patterns Pattern 2)
# ──────────────────────────────────────────────────────────

@pytest.fixture
def db(temp_db):
    """초기화된 SQLite DB fixture (scope: function — 테스트 격리)"""
    database = Database(temp_db)
    database.init_schema()
    return database


@pytest.fixture
def sample_run_id():
    return str(uuid.uuid4())


@pytest.fixture
def sample_label_row(db, sample_run_id):
    """behavior_labels에 테스트용 행 삽입 후 id 반환"""
    label_id = str(uuid.uuid4())
    db.insert(
        """
        INSERT INTO labeling_runs
        (id, url, title, channel, duration_s, video_path, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_run_id,
            "https://youtube.com/watch?v=test",
            "테스트 영상",
            "TestChannel",
            120.0,
            "/tmp/test.mp4",
            "collected",
            datetime.utcnow().isoformat(),
        ),
    )
    db.insert(
        """
        INSERT INTO behavior_labels
        (id, run_id, frame_id, preset_id, category, label,
         antecedent, behavior, consequence, intensity,
         llm_confidence, consistency_score, keypoint_quality, confidence,
         review_status, labeler_model, synced, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            label_id, sample_run_id, 10,
            "walk_pulling", "walk", "walk_pulling",
            "목줄이 팽팽해짐", "강하게 앞으로 당김", "보호자가 제지함", 3,
            0.88, 0.80, 0.85, 0.855,
            "pending", "gemma4-unsloth-e4b:latest", 0,
            datetime.utcnow().isoformat(),
        ),
    )
    return label_id


# ──────────────────────────────────────────────────────────
# BatchResult 모델 테스트
# ──────────────────────────────────────────────────────────

class TestBatchResult:
    """python-error-handling BatchResult 패턴 검증"""

    def test_empty_batch_all_succeeded(self):
        batch: BatchResult[str] = BatchResult()
        assert batch.all_succeeded is True
        assert batch.total == 0

    def test_success_count(self):
        batch: BatchResult[str] = BatchResult()
        batch.succeeded["url1"] = "run_id_1"
        batch.succeeded["url2"] = "run_id_2"
        assert batch.success_count == 2
        assert batch.failure_count == 0
        assert batch.all_succeeded is True

    def test_partial_failure(self):
        batch: BatchResult[str] = BatchResult()
        batch.succeeded["url1"] = "run_id_1"
        batch.failed["url2"] = RuntimeError("다운로드 실패")

        assert batch.success_count == 1
        assert batch.failure_count == 1
        assert batch.all_succeeded is False
        assert batch.total == 2

    def test_all_failed(self):
        batch: BatchResult[str] = BatchResult()
        batch.failed["url1"] = RuntimeError("실패1")
        batch.failed["url2"] = RuntimeError("실패2")

        assert batch.success_count == 0
        assert batch.failure_count == 2
        assert batch.all_succeeded is False


# ──────────────────────────────────────────────────────────
# QualityGate 테스트 — mock 없이 DB만 사용
# ──────────────────────────────────────────────────────────

class TestQualityGate:
    """QualityGate: review_status 설정 로직 검증"""

    def test_auto_approved_above_threshold(self, db, sample_label_row, temp_db):
        """confidence ≥ 0.85 → auto_approved (cold start 해제 후)"""
        # Arrange: cold start 조건 해제 (synced 100건 이상 시뮬레이션)
        # 직접 DB patch 대신 cold start limit을 낮게 설정
        from src.agents.quality_gate import QualityGate

        with patch.object(QualityGate, "COLD_START_LIMIT", 0):
            with patch("src.agents.quality_gate.get_db", return_value=db):
                gate = QualityGate()
                # Act
                result = gate.run(sample_label_row, dry_run=False)

        # Assert
        assert result is True
        label = db.execute_one("SELECT review_status FROM behavior_labels WHERE id = ?", (sample_label_row,))
        assert label["review_status"] == "auto_approved"

    def test_cold_start_forces_human_review(self, db, sample_label_row):
        """cold start 상태(synced=0) → human_review 강제"""
        from src.agents.quality_gate import QualityGate

        with patch("src.agents.quality_gate.get_db", return_value=db):
            gate = QualityGate()
            gate.run(sample_label_row, dry_run=False)

        label = db.execute_one("SELECT review_status FROM behavior_labels WHERE id = ?", (sample_label_row,))
        assert label["review_status"] == "human_review"

    def test_unknown_label_rejected(self, db, sample_run_id):
        """preset_id='unknown' → rejected"""
        from src.agents.quality_gate import QualityGate

        label_id = str(uuid.uuid4())
        db.insert(
            """
            INSERT INTO behavior_labels
            (id, run_id, frame_id, preset_id, category, label,
             llm_confidence, consistency_score, keypoint_quality, confidence,
             review_status, labeler_model, synced, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                label_id, sample_run_id, 20,
                "unknown", "unknown", "unknown",
                0.9, 0.9, 0.9, 0.9,
                "pending", "gemma4-unsloth-e4b:latest", 0,
                datetime.utcnow().isoformat(),
            ),
        )

        with patch.object(QualityGate, "COLD_START_LIMIT", 0):
            with patch("src.agents.quality_gate.get_db", return_value=db):
                gate = QualityGate()
                gate.run(label_id, dry_run=False)

        label = db.execute_one("SELECT review_status FROM behavior_labels WHERE id = ?", (label_id,))
        assert label["review_status"] == "rejected"

    def test_nonexistent_label_returns_false(self, db):
        """존재하지 않는 label_id → False 반환"""
        from src.agents.quality_gate import QualityGate

        with patch("src.agents.quality_gate.get_db", return_value=db):
            gate = QualityGate()
            result = gate.run("nonexistent-id", dry_run=False)

        assert result is False


# ──────────────────────────────────────────────────────────
# Critic 테스트 — LLM mock (python-testing-patterns Pattern 4)
# ──────────────────────────────────────────────────────────

class TestCritic:
    """Critic: LLM 호출 mock으로 외부 의존성 격리"""

    def test_pass_decision_updates_db(self, db, sample_label_row):
        """LLM이 pass_decision=True → critic_pass=1 업데이트"""
        from src.agents.critic import Critic

        mock_llm = MagicMock()
        mock_llm.chat.return_value = {"content": '{"pass_decision": true, "confidence_adjusted": 0.9, "exception_reason": null}'}
        mock_llm.parse_json_response.return_value = {
            "pass_decision": True,
            "confidence_adjusted": 0.9,
            "exception_reason": None,
        }

        with patch("src.agents.critic.get_db", return_value=db):
            with patch("src.agents.critic.get_ollama_client", return_value=mock_llm):
                critic = Critic()
                result = critic.run(sample_label_row, dry_run=False)

        assert result is True
        label = db.execute_one("SELECT critic_pass, confidence FROM behavior_labels WHERE id = ?", (sample_label_row,))
        assert label["critic_pass"] == 1
        assert abs(label["confidence"] - 0.9) < 0.01

    def test_fail_decision(self, db, sample_label_row):
        """LLM이 pass_decision=False → critic_pass=0"""
        from src.agents.critic import Critic

        mock_llm = MagicMock()
        mock_llm.parse_json_response.return_value = {
            "pass_decision": False,
            "confidence_adjusted": 0.3,
            "exception_reason": "ABC 내용 불충분",
        }

        with patch("src.agents.critic.get_db", return_value=db):
            with patch("src.agents.critic.get_ollama_client", return_value=mock_llm):
                critic = Critic()
                result = critic.run(sample_label_row, dry_run=False)

        assert result is False

    def test_llm_failure_falls_back_to_rule_based(self, db, sample_label_row):
        """LLM 호출 실패 → Rule-Based Fallback 사용, 크래시 없음"""
        from src.agents.critic import Critic

        mock_llm = MagicMock()
        mock_llm.chat.side_effect = ConnectionError("Ollama 연결 실패")

        with patch("src.agents.critic.get_db", return_value=db):
            with patch("src.agents.critic.get_ollama_client", return_value=mock_llm):
                critic = Critic()
                # 예외가 전파되지 않고 Rule-Based로 처리되어야 함
                result = critic.run(sample_label_row, dry_run=False)

        assert isinstance(result, bool)  # True 또는 False, 크래시 없음

    def test_dry_run_does_not_write_db(self, db, sample_label_row):
        """dry_run=True → DB critic_pass 변경 없음"""
        from src.agents.critic import Critic

        mock_llm = MagicMock()
        mock_llm.parse_json_response.return_value = {
            "pass_decision": True,
            "confidence_adjusted": 0.95,
            "exception_reason": None,
        }

        original = db.execute_one("SELECT critic_pass FROM behavior_labels WHERE id = ?", (sample_label_row,))

        with patch("src.agents.critic.get_db", return_value=db):
            with patch("src.agents.critic.get_ollama_client", return_value=mock_llm):
                critic = Critic()
                critic.run(sample_label_row, dry_run=True)

        after = db.execute_one("SELECT critic_pass FROM behavior_labels WHERE id = ?", (sample_label_row,))
        assert after["critic_pass"] == original["critic_pass"]  # 변경 없음


# ──────────────────────────────────────────────────────────
# Watchdog 테스트
# ──────────────────────────────────────────────────────────

class TestWatchdog:
    """Watchdog: 실패 분류 로직 검증 (DB 없음 — 파일 기반)"""

    def test_transient_failure_classification(self, tmp_path, monkeypatch):
        from src.agents.watchdog import Watchdog
        monkeypatch.setattr(Watchdog, "LOG_DIR", str(tmp_path))
        wd = Watchdog()
        error_type, is_halt = wd.classify_failure("Connection timeout")
        assert error_type == "transient"
        assert is_halt is False

    def test_permanent_failure_classification(self, tmp_path, monkeypatch):
        from src.agents.watchdog import Watchdog
        monkeypatch.setattr(Watchdog, "LOG_DIR", str(tmp_path))
        wd = Watchdog()
        error_type, is_halt = wd.classify_failure("schema mismatch detected")
        assert is_halt is True

    def test_log_failure_does_not_crash(self, tmp_path, monkeypatch):
        """log_failure → 크래시 없이 실행"""
        from src.agents.watchdog import Watchdog
        monkeypatch.setattr(Watchdog, "LOG_DIR", str(tmp_path))
        wd = Watchdog()
        wd.log_failure("collector", "https://youtube.com/test", "transient", "timeout")
        assert True


# ──────────────────────────────────────────────────────────
# 파라미터화 테스트 (python-testing-patterns Pattern 3)
# ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("confidence,expected_status", [
    (0.90, "auto_approved"),
    (0.85, "auto_approved"),
    (0.75, "human_review"),
    (0.65, "human_review"),
    (0.64, "rejected"),
    (0.30, "rejected"),
])
def test_confidence_thresholds(db, sample_run_id, confidence, expected_status):
    """CONFIDENCE-THRESHOLD-POLICY 기준값 전체 검증 (파라미터화)"""
    from src.agents.quality_gate import QualityGate

    label_id = str(uuid.uuid4())
    db.insert(
        """
        INSERT INTO behavior_labels
        (id, run_id, frame_id, preset_id, category, label,
         llm_confidence, consistency_score, keypoint_quality, confidence,
         review_status, labeler_model, synced, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            label_id, sample_run_id, 1,
            "walk_pulling", "walk", "walk_pulling",
            confidence, confidence, confidence, confidence,
            "pending", "gemma4-unsloth-e4b:latest", 0,
            datetime.utcnow().isoformat(),
        ),
    )

    with patch.object(QualityGate, "COLD_START_LIMIT", 0):
        with patch("src.agents.quality_gate.get_db", return_value=db):
            gate = QualityGate()
            gate.run(label_id, dry_run=False)

    result = db.execute_one("SELECT review_status FROM behavior_labels WHERE id = ?", (label_id,))
    assert result["review_status"] == expected_status, (
        f"confidence={confidence} → 기대: {expected_status}, 실제: {result['review_status']}"
    )
