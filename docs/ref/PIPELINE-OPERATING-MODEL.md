# Pipeline Operating Model — SSOT

> vibehub-media `PIPELINE-OPERATING-MODEL.md` 패턴 이식.
> taillog_labeling 파이프라인 5단계 구조와 운영 원칙을 정의한다.

---

## 파이프라인 개요

```
수집(collect) → 추출(extract) → 분류(classify) → 검수(review) → 동기화(sync)
```

---

## 5단계 상세

### Stage 1: 수집 (Collect)
- **에이전트**: `collector`
- **입력**: YouTube URL 리스트 (`.claude/automations/daily-pipeline.md` 트리거)
- **출력**: `labeling_runs` 레코드, 로컬 mp4 파일
- **이벤트 트리거**: `daily-pipeline.md` 자동화 스케줄러
- **완료 신호**: SQLite `labeling_runs.status = 'collected'`

### Stage 2: 추출 (Extract)
- **에이전트**: `pose_extractor`
- **입력**: video_file_path
- **출력**: `pose_results` 레코드, keypoints JSON
- **이벤트 트리거**: Stage 1 완료 이벤트
- **완료 신호**: `labeling_runs.status = 'extracted'`

### Stage 3: 분류 (Classify)
- **에이전트**: `behavior_classifier` → `abc_labeler`
- **입력**: pose_results
- **출력**: `behavior_labels` 레코드 (pending 상태)
- **이벤트 트리거**: Stage 2 완료 이벤트
- **완료 신호**: `labeling_runs.status = 'labeled'`

### Stage 4: 검수 (Review)
- **에이전트**: `critic` → `quality_gate`
- **입력**: behavior_labels (pending)
- **출력**: review_status 업데이트 (auto_approved / human_review / rejected)
- **이벤트 트리거**: Stage 3 완료 이벤트
- **완료 신호**: `behavior_labels.review_status != 'pending'`

### Stage 5: 동기화 (Sync)
- **에이전트**: `sync_writer`
- **입력**: behavior_labels (auto_approved)
- **출력**: TailLog Supabase `behavior_logs` INSERT
- **이벤트 트리거**: `daily-sync-monitor.md` 자동화 OR Stage 4 완료 이벤트
- **완료 신호**: `behavior_labels.synced = TRUE`

---

## Event-Driven 흐름

```
[YouTube URL]
    ↓ daily-pipeline.md (트리거)
[collector] → labeling_runs.status='collected'
    ↓
[pose_extractor] → labeling_runs.status='extracted'
    ↓
[behavior_classifier] → behavior_labels INSERT (pending)
    ↓
[abc_labeler] → behavior_labels UPDATE (antecedent/behavior/consequence)
    ↓
[critic] → behavior_labels UPDATE (critic_pass)
    ↓
[quality_gate] → behavior_labels UPDATE (review_status)
    ↓
[sync_writer] → TailLog Supabase INSERT + behavior_labels.synced=TRUE

    ← [watchdog] 실패 시 모든 단계에서 호출
```

---

## 자동화 실행 순서 (일일)

```
daily-pipeline
    ↓
daily-quality-gate
    ↓
daily-critic-review
    ↓
daily-sync-monitor
```

주간:
```
weekly-model-eval
weekly-dataset-health
weekly-pipeline-audit
```

---

## 운영 원칙

1. **한 단계가 한 번에 하나의 결정**을 내린다.
2. **실패는 즉시 watchdog으로 에스컬레이션**한다.
3. **원본 영상은 최대 14일 보존** 후 자동 삭제.
4. **confidence < 0.65 데이터는 SQLite에만 기록** (Supabase 전송 없음).
5. **cold start 2주**: 모든 라벨을 human_review로 처리.
6. **promote 전 shadow 증거** 필수.

---

## 상태 전환 다이어그램

```
labeling_runs.status:
  pending → collecting → collected → extracting → extracted
  → classifying → labeled → reviewing → reviewed → syncing → synced
  → failed (watchdog에서 설정)

behavior_labels.review_status:
  pending → auto_approved → synced
  pending → human_review → (수동 승인) → synced
  pending → rejected
```
