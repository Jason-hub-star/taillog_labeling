# 구현 완료 노트

## 전체 구조

```
src/
  __init__.py
  core/
    __init__.py
    models.py          # Pydantic 모델 정의
    database.py        # SQLite WAL mode DB 관리
    llm.py             # Ollama 클라이언트
    supabase_client.py # Supabase 초기화
  agents/
    __init__.py
    collector.py       # YouTube 다운로드
    pose_extractor.py  # YOLOv8 탐지 (OD-07 placeholder)
    behavior_classifier.py  # gemma4 행동 분류
    abc_labeler.py     # gemma4 ABC 생성
    critic.py          # gemma4:26b 최종 검수
    quality_gate.py    # 신뢰도 임계값 처리
    sync_writer.py     # Supabase sync
    watchdog.py        # 실패 처리
  prompts/
    __init__.py
    classifier_prompt.py
    abc_labeler_prompt.py
    critic_prompt.py
  pipelines/
    __init__.py
    orchestrator.py    # 에이전트 조율
    run.py             # CLI 진입점
  utils/
    __init__.py
    config.py          # 설정 관리

tests/
  __init__.py
  conftest.py
  test_models.py
  test_database.py
  test_prompts.py
```

## 핵심 에이전트

### 1. Collector
- yt-dlp로 YouTube 영상 다운로드
- 메타데이터 추출 (제목, 채널, 길이)
- labeling_runs 테이블에 INSERT

### 2. Pose Extractor
- YOLOv8n 객체 탐지 (COCO dog class=16)
- 1 FPS로 프레임 샘플링
- 17개 keypoints (OD-07 미결이라 placeholder)
- pose_results 테이블에 저장

### 3. Behavior Classifier
- 단일 프레임 keypoints → 행동 분류
- LLM: gemma4-unsloth-e4b:latest
- 신뢰도 계산 (1차)
- behavior_labels INSERT (pending)

### 4. ABC Labeler
- Antecedent, Behavior, Consequence 생성
- 연속 프레임 시퀀스 분석
- Intensity 1-5 결정
- behavior_labels UPDATE

### 5. Critic
- ABC 완전성 검증
- 강도 합리성 확인
- Confidence 조정
- LLM 실패 시 Rule-Based Fallback

### 6. Quality Gate
- 신뢰도 임계값 적용
- review_status 설정 (auto_approved, human_review, rejected)
- Cold Start 모드 (초기 100건)

### 7. Sync Writer
- Supabase behavior_logs에 INSERT
- Exponential backoff (3회 retry)
- 실패 시 watchdog 호출

### 8. Watchdog
- 실패 분류 (transient, permanent, unknown)
- HALT 조건 감지
- 이상 탐지 (신뢰도 급락, 거부율 상승)
- 로그 기록

## 신뢰도 계산

```python
confidence = (
    llm_confidence * 0.5 +
    consistency_score * 0.3 +
    keypoint_quality * 0.2
)
```

### 임계값
- ≥ 0.85: auto_approved → 즉시 sync
- 0.65~0.84: human_review → 수동 검수
- < 0.65: rejected → 폐기

### Cold Start (초기 2주, 100건)
- 모든 라벨을 human_review로 설정 (신뢰도 무관)

## 설정 및 환경변수

### .env.local (필수)
```
SUPABASE_URL=https://qufjlveukaoiokhpkhwj.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service_role_key>
OLLAMA_URL=http://localhost:11434
LABELING_DB_PATH=data/databases/labeling.db
```

### 모델
- Classifier/ABC: gemma4-unsloth-e4b:latest (5GB)
- Critic: gemma4:26b-a4b-it-q4_K_M (17GB)
- Pose: yolov8n.pt (object detection)

## 실행 방법

### 설치
```bash
cp .env.example .env.local
pip install -e ".[dev]"
source venv/bin/activate
```

### DB 초기화
```bash
python -c "from src.core.database import init_db; init_db()"
```

### 드라이런 (DB 저장 안 함)
```bash
python src/pipelines/run.py --dry-run --max-items 1
```

### 실제 실행
```bash
python src/pipelines/run.py --url <youtube_url>
python src/pipelines/run.py --urls-file urls.txt --max-items 5
```

### 테스트
```bash
pytest tests/ -v
pytest tests/ --cov=src
```

## OD-07 미결 (포즈 추출)

현재: YOLOv8n object detection (bounding box만)
TODO: SuperAnimal keypoint detection으로 교체

pose_extractor.py의 `_generate_dummy_keypoints()` 함수를 다음과 같이 교체 예정:
```python
# Phase 1 확정 후 SuperAnimal 모델로 교체
from superanimal.models import SuperAnimalPose
model = SuperAnimalPose()
results = model.predict(frame)  # 17개 keypoints 반환
```

## OD-01, OD-02 미결

### OD-01: dog_id 매핑
현재: 임시 anonymous dog (`labeling_pipeline_v1`)
향후: YouTube URL → TailLog dogs table 매핑

### OD-02: type_id 매핑
현재: preset_id → 임시 INTEGER (1~21)
향후: TailLog behavior_logs.type_id 실제값 확인 후 교체

PRESET_TO_TYPE_ID 딕셔너리 (sync_writer.py 참고)

## 파이프라인 실행 흐름

```
[YouTube URL]
    ↓
[collector] → labeling_runs.status='collected'
    ↓
[pose_extractor] → pose_results INSERT
    ↓
[behavior_classifier] → behavior_labels INSERT (pending)
    ↓
[abc_labeler] → behavior_labels UPDATE
    ↓
[critic] → critic_pass 검증
    ↓
[quality_gate] → review_status 설정
    ↓
[sync_writer] → Supabase INSERT (if auto_approved)
    ↓
[watchdog] ← 모든 단계에서 실패 시 호출
```

## 중요 참고사항

1. **WAL Mode**: SQLite 동시 접근 대비
2. **Exponential Backoff**: 1s→2s→4s (max 3회)
3. **Rule-Based Fallback**: LLM 실패 시 규칙 기반 critic
4. **HALT 조건**: 스키마 불일치, RLS 오류 → 파이프라인 중단
5. **로그 기록**: data/exports/sync_logs/watchdog.log, HALT_*.log

## 라이선스 및 기여

SSOT 문서 기준: docs/ref/ 참고
