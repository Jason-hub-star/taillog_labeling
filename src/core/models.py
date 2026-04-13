"""Pydantic 모델 정의 — 라벨링 데이터 구조"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, TypeVar, Generic
from pydantic import BaseModel, Field
import uuid

T = TypeVar("T")


@dataclass
class BatchResult(Generic[T]):
    """
    배치 처리 결과 — python-error-handling 스킬 BatchResult 패턴 적용.
    단일 실패가 전체 배치를 중단시키지 않도록 성공/실패를 분리해서 추적.
    """
    succeeded: Dict[str, T] = field(default_factory=dict)   # id -> result
    failed: Dict[str, Exception] = field(default_factory=dict)  # id -> error

    @property
    def success_count(self) -> int:
        return len(self.succeeded)

    @property
    def failure_count(self) -> int:
        return len(self.failed)

    @property
    def all_succeeded(self) -> bool:
        return len(self.failed) == 0

    @property
    def total(self) -> int:
        return len(self.succeeded) + len(self.failed)


class KeyPoint(BaseModel):
    """단일 키포인트 — A-07 확정: bodypart 이름 포함 저장
    bodypart는 SuperAnimal H5 MultiIndex level_1에서 동적 파싱 (하드코딩 금지)
    """
    bodypart: str  # SuperAnimal bodypart 이름 (nose, left_ear, ...) — 필수
    x: float                         # 절대 픽셀 좌표 (A-06)
    y: float
    c: float                         # confidence (likelihood)


class PoseResult(BaseModel):
    """포즈 추출 결과"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    frame_id: int
    keypoints: List[KeyPoint]  # SuperAnimal quadruped 39개 keypoints (bodypart 이름 포함 — A-07)
    confidence: float  # 탐지 신뢰도 (0~1)
    frame_path: Optional[str] = None  # A-09: 프레임 이미지 JPEG 절대 경로
    created_at: datetime = Field(default_factory=datetime.utcnow)


class BehaviorLabel(BaseModel):
    """행동 라벨 최종 결과"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    frame_id: int
    preset_id: str  # walk_pulling, etc.
    category: str  # walk, play, condition, alert, meal, social
    label: str
    antecedent: Optional[str] = None  # ABC 선행
    behavior: Optional[str] = None  # ABC 행동
    consequence: Optional[str] = None  # ABC 결과
    intensity: Optional[int] = None  # 1-10 (LABEL-SCHEMA.md v3.0)

    # 신뢰도 계산 요소
    llm_confidence: float  # LLM 응답 confidence (0~1)
    consistency_score: float  # 연속 프레임 일관성 (0~1)
    keypoint_quality: float  # keypoint 평균 confidence (0~1)
    confidence: float  # 종합 신뢰도 = 0.5*llm + 0.3*consistency + 0.2*keypoint

    # 검수 상태
    review_status: str = "pending"  # pending, auto_approved, human_review, rejected
    reviewer_note: Optional[str] = None  # Vision LLM reasoning ([AI] prefix) 또는 검수자 메모
    critic_pass: Optional[bool] = None
    critic_note: Optional[str] = None

    # 메타
    labeler_model: str  # gemma4-unsloth-e4b:latest, etc.
    synced: bool = False
    taillog_log_id: Optional[str] = None  # Supabase behavior_logs.id

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class LabelingRun(BaseModel):
    """라벨링 run (영상 단위)"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    url: str  # YouTube URL
    title: str
    channel: str
    duration_s: float  # 영상 길이 (초)
    video_path: str  # 로컬 파일 경로
    status: str = "pending"  # pending, collecting, collected, extracting, extracted,
    # classifying, labeled, reviewing, reviewed, syncing, synced, failed

    error_msg: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class SyncAttempt(BaseModel):
    """Supabase sync 시도 기록"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label_id: str
    attempt_at: datetime = Field(default_factory=datetime.utcnow)
    success: bool = False
    error_msg: Optional[str] = None


class ClassifierOutput(BaseModel):
    """behavior_classifier LLM 출력"""
    category: str
    label: str
    confidence: float = 0.6  # 제공 안 되면 0.6
    reasoning: Optional[str] = None  # Vision LLM 근거 → reviewer_note에 [AI] prefix로 저장


class ABCLabelerOutput(BaseModel):
    """abc_labeler LLM 출력"""
    antecedent: str
    behavior: str
    consequence: str
    intensity: int  # 1-5
    confidence: float = 0.6


class CriticOutput(BaseModel):
    """critic LLM 검수 결과"""
    pass_decision: bool  # True: 통과, False: 불합격
    confidence_adjusted: float  # 조정된 신뢰도
    exception_reason: Optional[str] = None
