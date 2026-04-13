"""설정 관리"""

import os
from pathlib import Path


class Config:
    """애플리케이션 설정"""

    # 경로
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    DATA_DIR = PROJECT_ROOT / "data"
    CACHE_DIR = DATA_DIR / "cache"
    DB_DIR = DATA_DIR / "databases"
    LOGS_DIR = DATA_DIR / "exports" / "sync_logs"

    # DB
    LABELING_DB_PATH = DB_DIR / "labeling.db"

    # LLM
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    # SuperAnimal 포즈 추출 (A-01, A-07 확정 2026-04-11)
    # dlclibrary API 응답 기준: get_available_models('superanimal_quadruped') → ['hrnet_w32', 'resnet_50', 'rtmpose_s']
    SUPERANIMAL_NAME = "superanimal_quadruped"
    SUPERANIMAL_MODEL = "hrnet_w32"                          # dlclibrary 2026-04-11 확인
    SUPERANIMAL_DETECTOR = "fasterrcnn_resnet50_fpn_v2"      # deeplabcut 기본 detector
    SUPERANIMAL_CONF_THRESHOLD = 0.3                         # A-01: SuperAnimal 기준 임계값
    SUPERANIMAL_INFER_SCRIPT = PROJECT_ROOT / "scripts" / "superanimal_infer.py"
    DLC_VENV_PYTHON = PROJECT_ROOT / ".venv_dlc" / "bin" / "python"

    # LLM 모델 (A-02 확정)
    BEHAVIOR_CLASSIFIER_MODEL = "gemma4:26b-a4b-it-q4_K_M"  # Vision 지원 (Phase 3)
    ABC_LABELER_MODEL = "gemma4-unsloth-e4b:latest"
    CRITIC_MODEL = "gemma4:26b-a4b-it-q4_K_M"

    # 파이프라인
    FRAME_RATE = 1  # 1 FPS
    BATCH_SIZE = 16
    CONFIDENCE_THRESHOLD = 0.5

    # 임계값
    AUTO_APPROVED_THRESHOLD = 0.85
    HUMAN_REVIEW_THRESHOLD = 0.65
    COLD_START_LIMIT = 100

    # A-09: YOLOv8 학습 데이터 저장 경로 (Phase 1~3: 39pt, Phase 3 후반: 24pt 변환)
    TRAINING_DIR = DATA_DIR / "training"
    TRAINING_FRAMES_DIR = TRAINING_DIR / "frames"
    TRAINING_LABELS_DIR = TRAINING_DIR / "labels" / "39pt"
    TRAINING_DATASET_YAML = TRAINING_DIR / "dataset.yaml"
    TRAINING_CONF_THRESHOLD = 0.3  # 유효 keypoint 기준 (A-01과 동일)

    @classmethod
    def ensure_dirs(cls):
        """필요한 디렉토리 생성"""
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cls.DB_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        cls.TRAINING_FRAMES_DIR.mkdir(parents=True, exist_ok=True)
        cls.TRAINING_LABELS_DIR.mkdir(parents=True, exist_ok=True)


# 초기화
Config.ensure_dirs()
