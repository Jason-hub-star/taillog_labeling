# Pipeline Diagram

```
[YouTube URL 리스트]
        │
        ▼ daily-pipeline.md 트리거
┌───────────────┐
│   collector   │  yt-dlp 다운로드
│               │  480p+, 10초~10분
└───────┬───────┘
        │ video_file_path
        ▼
┌───────────────┐
│pose_extractor │  SuperAnimal-Quadruped (DeepLabCut)
│               │  1 FPS, 39 keypoints
└───────┬───────┘
        │ pose_results JSON
        ▼
┌──────────────────────┐
│ behavior_classifier  │  gemma4-unsloth-e4b
│                      │  6 categories × 21 labels
└──────────┬───────────┘
           │ category + label + confidence
           ▼
┌──────────────────────┐
│    abc_labeler       │  gemma4-unsloth-e4b
│                      │  antecedent/behavior/consequence + intensity
└──────────┬───────────┘
           │ behavior_labels (pending)
           ▼
┌──────────────────────┐
│       critic         │  gemma4:26b
│   [shadow mode]      │  ABC 완전성 + intensity 합리성
└──────────┬───────────┘
           │ critic_pass_shadow
           ▼
┌──────────────────────┐
│    quality_gate      │  rule engine
│                      │  ≥0.85 → auto_approved
│                      │  0.65~0.84 → human_review
│                      │  <0.65 → rejected
└──────────┬───────────┘
           │ auto_approved only
           ▼
┌──────────────────────┐
│    sync_writer       │  supabase-py
│                      │  → behavior_logs INSERT
│                      │  URL: qufjlveukaoiokhpkhwj.supabase.co
└──────────┬───────────┘
           │ synced = TRUE
           ▼
    [TailLog DB ✓]

         ┌──────────────────────┐
         │       watchdog       │  모든 단계 실패 시 호출
         │                      │  transient: retry
         │                      │  permanent: HALT
         └──────────────────────┘
```

## 상태 흐름

```
labeling_runs.status:
pending → collecting → collected → extracting → extracted
→ classifying → labeled → reviewing → reviewed → synced/failed

behavior_labels.review_status:
pending → auto_approved → synced
pending → human_review → (수동 승인) → synced
pending → rejected
```
