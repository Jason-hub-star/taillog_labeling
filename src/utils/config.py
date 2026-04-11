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

    # 모델
    POSE_MODEL = "yolov8n.pt"
    BEHAVIOR_CLASSIFIER_MODEL = "gemma4-unsloth-e4b:latest"
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

    @classmethod
    def ensure_dirs(cls):
        """필요한 디렉토리 생성"""
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cls.DB_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)


# 초기화
Config.ensure_dirs()
