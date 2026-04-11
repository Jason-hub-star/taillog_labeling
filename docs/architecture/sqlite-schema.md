# SQLite Schema

> `data/databases/labeling.db` 전체 스키마.
> `src/core/database.py`에서 `init_db()` 호출 시 생성됨.

---

## 테이블 목록

| 테이블 | 역할 |
|--------|------|
| `labeling_runs` | 파이프라인 실행 기록 (영상 1개 = 1 run) |
| `video_frames` | 추출된 프레임 메타데이터 |
| `pose_results` | YOLOv8 keypoints JSON |
| `behavior_labels` | 최종 라벨 데이터 (sync 대상) |
| `classifier_responses` | LLM 원본 응답 저장 |
| `sync_attempts` | Supabase sync 이력 |
| `quality_metrics` | 일별 품질 지표 집계 |

---

```sql
PRAGMA journal_mode=WAL;  -- 동시 접근 대비

-- ===== labeling_runs
CREATE TABLE IF NOT EXISTS labeling_runs (
    id TEXT PRIMARY KEY,
    youtube_url TEXT UNIQUE NOT NULL,
    dedupe_key VARCHAR(64) UNIQUE NOT NULL,
    video_file_path TEXT,
    title TEXT,
    channel TEXT,
    duration_sec INTEGER,
    resolution TEXT,
    status TEXT DEFAULT 'pending',
    -- pending/collecting/collected/extracting/extracted
    -- /classifying/labeled/reviewing/reviewed/syncing/synced/failed
    error_message TEXT,
    frame_count INTEGER DEFAULT 0,
    detected_frame_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_runs_status ON labeling_runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_created ON labeling_runs(created_at DESC);

-- ===== video_frames
CREATE TABLE IF NOT EXISTS video_frames (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    frame_number INTEGER NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    frame_image_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES labeling_runs(id)
);
CREATE INDEX IF NOT EXISTS idx_frames_run_id ON video_frames(run_id);

-- ===== pose_results
CREATE TABLE IF NOT EXISTS pose_results (
    id TEXT PRIMARY KEY,
    frame_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    keypoints TEXT NOT NULL,  -- JSON: [{x, y, c}, ...] × 17
    detection_confidence REAL NOT NULL,
    bbox_area_ratio REAL,     -- 강아지 bbox / 전체 화면 비율
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (frame_id) REFERENCES video_frames(id),
    FOREIGN KEY (run_id) REFERENCES labeling_runs(id)
);
CREATE INDEX IF NOT EXISTS idx_pose_frame_id ON pose_results(frame_id);
CREATE INDEX IF NOT EXISTS idx_pose_run_id ON pose_results(run_id);

-- ===== behavior_labels
CREATE TABLE IF NOT EXISTS behavior_labels (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    frame_id TEXT,
    preset_id TEXT NOT NULL,
    category TEXT NOT NULL,
    label TEXT NOT NULL,
    antecedent TEXT,
    behavior TEXT,
    consequence TEXT,
    intensity INTEGER CHECK(intensity BETWEEN 1 AND 5),
    llm_confidence REAL,
    consistency_score REAL,
    keypoint_quality REAL,
    confidence REAL,          -- 최종 신뢰도 (가중 평균)
    critic_pass BOOLEAN,
    critic_pass_shadow BOOLEAN,
    review_status TEXT DEFAULT 'pending',
    -- pending/auto_approved/human_review/rejected/synced
    synced BOOLEAN DEFAULT FALSE,
    taillog_log_id TEXT,      -- Supabase behavior_logs.id
    video_segment_start_ms INTEGER,
    video_segment_end_ms INTEGER,
    labeler_model TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES labeling_runs(id)
);
CREATE INDEX IF NOT EXISTS idx_labels_run_id ON behavior_labels(run_id);
CREATE INDEX IF NOT EXISTS idx_labels_review_status ON behavior_labels(review_status);
CREATE INDEX IF NOT EXISTS idx_labels_synced ON behavior_labels(synced);
CREATE INDEX IF NOT EXISTS idx_labels_confidence ON behavior_labels(confidence DESC);

-- ===== classifier_responses
CREATE TABLE IF NOT EXISTS classifier_responses (
    id TEXT PRIMARY KEY,
    label_id TEXT NOT NULL,
    stage TEXT NOT NULL,      -- behavior_classifier/abc_labeler/critic
    model TEXT NOT NULL,
    prompt TEXT,
    raw_response TEXT,
    parsed_output TEXT,       -- JSON
    latency_ms INTEGER,
    token_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (label_id) REFERENCES behavior_labels(id)
);
CREATE INDEX IF NOT EXISTS idx_responses_label_id ON classifier_responses(label_id);
CREATE INDEX IF NOT EXISTS idx_responses_stage ON classifier_responses(stage);

-- ===== sync_attempts
CREATE TABLE IF NOT EXISTS sync_attempts (
    id TEXT PRIMARY KEY,
    label_id TEXT NOT NULL,
    supabase_log_id TEXT,
    status TEXT NOT NULL,     -- success/failed/retry
    error_message TEXT,
    attempt_number INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (label_id) REFERENCES behavior_labels(id)
);
CREATE INDEX IF NOT EXISTS idx_sync_label_id ON sync_attempts(label_id);
CREATE INDEX IF NOT EXISTS idx_sync_status ON sync_attempts(status);

-- ===== quality_metrics
CREATE TABLE IF NOT EXISTS quality_metrics (
    id TEXT PRIMARY KEY,
    metric_date DATE NOT NULL UNIQUE,
    total_labels INTEGER DEFAULT 0,
    auto_approved_count INTEGER DEFAULT 0,
    human_review_count INTEGER DEFAULT 0,
    rejected_count INTEGER DEFAULT 0,
    avg_confidence REAL,
    sync_success_count INTEGER DEFAULT 0,
    sync_failure_count INTEGER DEFAULT 0,
    critic_shadow_pass_count INTEGER DEFAULT 0,
    critic_shadow_fail_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
