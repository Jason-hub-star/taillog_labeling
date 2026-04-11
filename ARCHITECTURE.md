# TailLog Labeling — 아키텍처 문서

## 시스템 개요

```
┌─────────────────────────────────────────────────────────────┐
│                    YouTube URLs                             │
│              (urls.txt 또는 CLI 인자)                        │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────▼───────────┐
         │  Orchestrator         │
         │  (파이프라인 조율)      │
         └───────────┬───────────┘
                     │
        ┌────────────┴────────────┬──────────────┬─────────────┐
        │                         │              │             │
   ┌────▼────┐          ┌────────▼──────┐  ┌───▼──────┐  ┌───▼──────┐
   │Collector│          │Pose Extractor │  │Behavior  │  │ABC       │
   │          │          │(YOLOv8n)      │  │Classifier│  │Labeler   │
   │(yt-dlp) │          │               │  │(gemma4)  │  │(gemma4)  │
   └────┬────┘          └────┬──────────┘  └───┬──────┘  └───┬──────┘
        │                    │                 │              │
   [mp4 file]         [pose_results]    [pending labels] [ABC filled]
        │                    │                 │              │
        └────────┬───────────┴─────────────────┴──────────────┘
                 │
        ┌────────▼─────────┐
        │ Critic           │
        │ (gemma4:26b)     │
        │ + Fallback       │
        └────────┬─────────┘
                 │
        [critic_pass: bool]
                 │
        ┌────────▼──────────────┐
        │ Quality Gate          │
        │ (신뢰도 임계값 적용)    │
        └────────┬──────────────┘
                 │
    [review_status 설정]
    (auto_approved / human_review / rejected)
                 │
        ┌────────▼───────────┐
        │ Sync Writer         │
        │ (Supabase)          │
        │ + Retry (3회)       │
        └────────┬────────────┘
                 │
    [Supabase behavior_logs INSERT]
                 │
           ┌─────▼─────┐
           │ Watchdog  │
           │ (모든단계) │
           │ 실패시호출 │
           └───────────┘
```

## 에이전트 상세

### 1️⃣ Collector (`src/agents/collector.py`)
**책임**: YouTube 영상 수집
- yt-dlp로 480p 이상 영상 다운로드
- 메타데이터 추출 (제목, 채널, 길이)
- labeling_runs 테이블 INSERT
- 실패: watchdog에 기록

**입력**: YouTube URL
**출력**: labeling_runs.id, video_path
**에러처리**: transient (retry 3회), permanent (skip)

### 2️⃣ Pose Extractor (`src/agents/pose_extractor.py`)
**책임**: 강아지 탐지 및 포즈 추출
- YOLOv8n object detection (COCO dog class=16)
- 1 FPS로 프레임 샘플링
- 17개 keypoints 좌표 추출 (정규화)
- pose_results 테이블 INSERT

⚠️ **OD-07 미결**: 현재 dummy keypoints (bounding box 기반)
→ Phase 1 후 SuperAnimal로 교체

**입력**: video_path, run_id
**출력**: pose_results (frame_id별 17 keypoints)
**에러처리**: 강아지 미탐지 (discard), GPU OOM (batch size 절반)

### 3️⃣ Behavior Classifier (`src/agents/behavior_classifier.py`)
**책임**: 행동 분류 (1차)
- 프롬프트: keypoints → 텍스트 변환
- LLM: gemma4-unsloth-e4b:latest
- 21개 행동 카테고리 중 선택
- confidence 계산 (llm_confidence)
- behavior_labels INSERT (pending 상태)

**입력**: frame_id, keypoints_json
**출력**: BehaviorLabel (category, label, llm_confidence)
**에러처리**: LLM parse error → critic에 전달 (강제 검수)

### 4️⃣ ABC Labeler (`src/agents/abc_labeler.py`)
**책임**: ABC 라벨 생성
- 연속 5프레임 시퀀스 조회 (±2)
- 프롬프트: category/label + keypoint sequence
- LLM: gemma4-unsloth-e4b:latest
- ABC 생성: antecedent, behavior, consequence, intensity
- behavior_labels UPDATE

**입력**: label_id (분류된 라벨)
**출력**: BehaviorLabel (ABC 필드 추가)
**에러처리**: Partial response → critic mandatory

### 5️⃣ Critic (`src/agents/critic.py`)
**책임**: 최종 검수
- ABC 완전성 검증 (3개 필드 모두 존재)
- intensity 합리성 (1-5 범위, 행동과 일치)
- label validity (21개 preset 확인)
- confidence 조정
- LLM 실패 시 Rule-Based Fallback

**모델**: gemma4:26b-a4b-it-q4_K_M
**입력**: label_id (ABC 채워진 라벨)
**출력**: BehaviorLabel (critic_pass, confidence_adjusted)
**에러처리**: LLM 실패 → 규칙 기반 critic 사용

### 6️⃣ Quality Gate (`src/agents/quality_gate.py`)
**책임**: 신뢰도 임계값 적용
- Cold Start 모드 (초기 100건 모두 human_review)
- 신뢰도 기반 review_status 설정:
  - ≥ 0.85: auto_approved
  - 0.65~0.84: human_review
  - < 0.65: rejected
- unknown 라벨: 항상 rejected

**입력**: label_id (critic 완료된 라벨)
**출력**: review_status 설정
**에러처리**: 없음 (deterministic)

### 7️⃣ Sync Writer (`src/agents/sync_writer.py`)
**책임**: Supabase 동기화
- review_status='auto_approved' 필터링
- preset_id → type_id 매핑 (OD-02 임시)
- dog_id 매핑 (OD-01 임시: 'labeling_pipeline_v1')
- Supabase behavior_logs INSERT
- Exponential backoff (1s→2s→4s, max 3회)
- sync_attempts 기록
- behavior_labels.synced = TRUE 업데이트

⚠️ **OD-01 미결**: 임시 anonymous dog 사용
⚠️ **OD-02 미결**: 임시 type_id 매핑 (1~21)

**입력**: label_id (review_status='auto_approved')
**출력**: Supabase INSERT, sync_attempts 기록
**에러처리**: Connection error (retry), RLS error (HALT)

### 8️⃣ Watchdog (`src/agents/watchdog.py`)
**책임**: 실패 모니터링 및 복구
- 실패 분류:
  - transient: timeout, rate limit → exponential backoff
  - permanent: schema mismatch, RLS error → HALT
  - unknown: 예상 외 → investigation queue
- 이상 탐지:
  - 특정 label avg confidence < 0.5
  - 거부율 > 50% (최근 100건)
  - human_review 누적 > 500건
- 로그 기록: data/exports/sync_logs/watchdog.log, HALT_*.log

**입력**: 모든 에이전트의 오류
**출력**: retry_decision, manual_queue, status_report
**에러처리**: HALT 조건 → 파이프라인 중단

## 데이터베이스 스키마

### labeling_runs
```sql
id TEXT PRIMARY KEY
url TEXT UNIQUE
title, channel, duration_s TEXT
video_path TEXT
status TEXT (pending, collected, extracted, labeled, reviewed, synced, failed)
error_msg TEXT
created_at, updated_at TIMESTAMP
```

### pose_results
```sql
id TEXT PRIMARY KEY
run_id, frame_id INTEGER
keypoints_json TEXT (17 keypoints)
confidence REAL
created_at TIMESTAMP
UNIQUE(run_id, frame_id)
```

### behavior_labels
```sql
id TEXT PRIMARY KEY
run_id, frame_id INTEGER
preset_id, category, label TEXT
antecedent, behavior, consequence TEXT
intensity INTEGER (1-5)
llm_confidence, consistency_score, keypoint_quality REAL
confidence REAL (종합)
review_status TEXT (pending, auto_approved, human_review, rejected, synced)
critic_pass BOOLEAN
critic_note TEXT
labeler_model TEXT
synced BOOLEAN
taillog_log_id TEXT
created_at, updated_at TIMESTAMP
```

### sync_attempts
```sql
id TEXT PRIMARY KEY
label_id TEXT
attempt_at TIMESTAMP
success BOOLEAN
error_msg TEXT
```

## 신뢰도 계산

```python
confidence = (
    llm_confidence * 0.5 +
    consistency_score * 0.3 +
    keypoint_quality * 0.2
)
```

### 각 요소
- **llm_confidence** (0.5 가중치)
  - LLM 응답의 confidence 필드
  - 미제공 시 0.6 기본값

- **consistency_score** (0.3 가중치)
  - 연속 5프레임에서 동일 label 비율
  - 단일 프레임: 0.5 기본값

- **keypoint_quality** (0.2 가중치)
  - 17개 keypoints 평균 confidence
  - 탐지 < 50%: 0.3 패널티

## 파이프라인 상태 전환

```
labeling_runs.status:
pending → collected → extracted → labeled → reviewed → synced

behavior_labels.review_status:
pending → auto_approved → synced
pending → human_review → (수동) → synced
pending → rejected
```

## LLM 설정

### Classifier & ABC Labeler
- **모델**: gemma4-unsloth-e4b:latest (5GB)
- **온도**: 0.3 (결정론적)
- **재시도**: 3회 exponential backoff
- **타임아웃**: 60초

### Critic
- **모델**: gemma4:26b-a4b-it-q4_K_M (17GB)
- **온도**: 0.1 (매우 보수적)
- **재시도**: 2회
- **Shadow Mode**: 초기 200건 기록만, sync 영향 없음

## 실패 처리 전략

### Transient (자동 복구)
- YouTube timeout: 30분 대기 후 1회 retry
- GPU OOM: batch_size 절반 후 즉시 retry
- Ollama timeout: exponential backoff (1s→2s→4s)
- Supabase connection: exponential backoff

### Permanent (수동 개입)
- Invalid data: rejected + 로그
- Schema mismatch: HALT + Telegram 알림
- RLS violation: HALT + Telegram 알림

### Unknown (조사)
- 예상 외 예외: investigation queue + Telegram

## HALT 조건

파이프라인이 즉시 중단되는 경우:

1. Supabase schema mismatch (컬럼 없음)
2. service_role RLS violation
3. SQLite DB 파일 접근 불가
4. behavior_labels INSERT 연속 10회 실패
5. watchdog 자체 오류

HALT 시: `data/exports/sync_logs/HALT_<timestamp>.log` 생성

## Cold Start 정책

초기 2주 (100건 synced까지):
- 모든 라벨을 human_review로 설정
- confidence 값 무관
- 이유: 모델 성능 기준선 수립 전 전수 검수

## 미결 항목 (Open Decisions)

| OD | 항목 | 현재 상태 | 마감 |
|-------|---------|---------|------|
| OD-01 | dog_id 매핑 | 임시 anonymous dog | Phase 4 전 |
| OD-02 | type_id 매핑 | 임시 1~21 INTEGER | Phase 4 전 |
| OD-07 | 포즈 모델 | YOLOv8n (dummy keypoints) | Phase 1 후 |

자세한 내용: `docs/ref/OPEN-DECISIONS.md`
