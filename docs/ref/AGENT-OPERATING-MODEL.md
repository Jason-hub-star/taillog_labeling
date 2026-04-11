# Agent Operating Model

> vibehub-media `AGENT-OPERATING-MODEL.md` 패턴 이식.
> taillog_labeling은 단일 에이전트가 아니라 역할 분리형 7개 에이전트 팀으로 운영한다.
> 기본 원칙: **human-on-exception** — 사람은 신뢰도 임계값 미달 항목과 정책 설계만 담당한다.

---

## Agent Team

### `collector`
- **입력**: YouTube URL 리스트, source tier, 이전 run history
- **출력**: run_id, video_file_path, metadata (제목·채널·길이·해상도)
- **모델**: rule engine (yt-dlp, Python)
- **처리**:
  1. yt-dlp로 영상 다운로드 (480p 이상)
  2. 메타데이터 추출 (JSON)
  3. dedupe_key 생성 (URL hash)
  4. SQLite `labeling_runs` INSERT
- **handoff**: 성공 → `pose_extractor` / 실패 → `watchdog`
- **실패 처리**: rate-limit, geo-block, private video, timeout, low-quality 기록

---

### `pose_extractor`
- **입력**: video_file_path (mp4)
- **출력**: pose_results (JSON: per-frame keypoints[17])
- **모델**: `yolov8n-pose.pt` (ultralytics, local)
- **처리**:
  1. OpenCV로 1 FPS 프레임 추출
  2. YOLOv8n-pose 배치 추론 (batch=16)
  3. 탐지 신뢰도 < 0.5 프레임 필터링
  4. keypoints JSON → SQLite `pose_results` + 파일 저장
- **handoff**: 성공 → `behavior_classifier` / 강아지 미탐지 → discard / GPU OOM → cpu fallback retry
- **실패 처리**: 0 detections → discard (watchdog 통지 없음), GPU 오류 → watchdog

---

### `behavior_classifier`
- **입력**: pose_results (keypoints), video_metadata
- **출력**: category, label, confidence, raw_llm_response
- **모델**: `gemma4-unsloth-e4b:latest` (Ollama local)
- **처리**:
  1. 키포인트 JSON → 텍스트 표현 변환
  2. `CLASSIFIER_PROMPT` 조립 (prompt_builder.py)
  3. Ollama 호출 → JSON 파싱
  4. 신뢰도 점수 1차 계산
- **handoff**: 성공 → `abc_labeler` / parse error → critic (shadow) / timeout → retry(3회)
- **실패 처리**: LLM timeout → 3회 exponential backoff, 이후 watchdog

---

### `abc_labeler`
- **입력**: category, label, keypoint sequence
- **출력**: antecedent, behavior, consequence, intensity(1-5), confidence
- **모델**: `gemma4-unsloth-e4b:latest` (Ollama local)
- **처리**:
  1. 연속 프레임 키포인트 시퀀스 → 행동 흐름 설명 생성
  2. `ABC_LABELER_PROMPT` 조립
  3. Ollama 호출 → JSON 파싱
  4. intensity 검증 (1-5 범위)
- **handoff**: 성공 → `critic` / partial response → critic (강제 검수) / timeout → retry
- **실패 처리**: ABC 불완전 → critic mandatory

---

### `critic`
- **입력**: behavior_label (antecedent/behavior/consequence/intensity), pose_keypoints, frame
- **출력**: pass/fail, confidence_adjusted, exception_reason
- **모델**: `gemma4:26b-a4b-it-q4_K_M` (Ollama local) — shadow mode 초기
- **처리**:
  1. ABC 완전성 검사 (3개 필드 모두 존재)
  2. intensity 합리성 (키포인트 동작 크기와 일관성)
  3. label validity (21개 preset 범위 내)
  4. confidence 조정
- **shadow mode**: 초기 200건은 critic 결과 기록만, sync에 영향 없음
- **handoff**: pass → `quality_gate` / fail → watchdog
- **실패 처리**: LLM 오류 → rule-based fallback critic

---

### `sync_writer`
- **입력**: behavior_label (review_status = 'auto_approved')
- **출력**: taillog_log_id (Supabase behavior_logs.id), sync_status
- **모델**: rule engine (Python, supabase-py)
- **처리**:
  1. `SUPABASE-SYNC-CONTRACT.md` 규약에 따라 필드 매핑
  2. `service_role` key로 Supabase INSERT
  3. SQLite `sync_attempts` 기록
  4. `behavior_labels.synced = TRUE` 업데이트
- **handoff**: 성공 → complete / 실패 → retry 큐(3회) → watchdog
- **실패 처리**: connection error → retry, RLS 오류 → watchdog (즉시), schema mismatch → HALT

---

### `watchdog`
- **입력**: 모든 에이전트의 실패·예외·불확실 상태
- **출력**: retry_decision, manual_queue, status_report
- **모델**: rule engine (Python)
- **실패 유형 분류**:
  | 유형 | 예시 | 처리 |
  |------|------|------|
  | transient | timeout, rate-limit | exponential backoff (1s→2s→4s, max 3회) |
  | permanent | invalid data, schema mismatch | manual_review_required |
  | unknown | 예상 외 오류 | investigation queue + Telegram alert |
- **handoff**: retry → 원 에이전트 재실행 / manual → human review queue

---

## Program Files (운영 규칙 마크다운)

각 에이전트는 아래 항목을 포함하는 program 문서를 가진다:
- 목표
- 성공 조건
- 실패 조건
- escalation 조건
- discard 조건

→ `docs/ref/AGENT-OPERATING-MODEL.md` 가 최상위. 에이전트별 상세는 `src/agents/` 코드 docstring 참조.

---

## Human Role

사람은 아래만 담당한다:
- `human_review` 큐 검수 (신뢰도 0.65~0.84 항목)
- 신뢰도 임계값 정책 수정
- 라벨 스키마 변경 결정
- 모델 promote/rollback 최종 승인

**사람은 auto_approved 항목 전수 검수를 하지 않는다.**

---

## Default Operating Rule

- 한 에이전트가 한 번에 하나의 결정만 내린다.
- promote 전에 항상 shadow/eval 증거를 남긴다.
- 새 모델 도입은 `shadow → eval → activate → rollback 준비` 순서로 진행한다.
- LLM parse 오류는 즉시 discard하지 않고 critic에 먼저 넘긴다.
