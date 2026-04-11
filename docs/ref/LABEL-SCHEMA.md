# Label Schema — SSOT

> TaillogToss `presets.ts` 기반 라벨 포맷 정의.
> 이 스키마가 SQLite, Supabase sync, 에이전트 프롬프트의 단일 기준이다.

---

## 6 Categories × 21 Behaviors

| category | preset_id | label (한국어) | defaultIntensity |
|----------|-----------|--------------|----------------|
| walk | walk_pulling | 줄 당기기 | 3 |
| walk | walk_reactive | 산책 중 반응성 | 3 |
| walk | walk_fearful | 산책 중 공포 반응 | 2 |
| walk | walk_distracted | 산책 중 집중력 저하 | 2 |
| play | play_overexcited | 과도한 흥분 | 4 |
| play | play_resource | 자원 지키기 (장난감) | 3 |
| play | play_rough | 거친 놀이 | 3 |
| condition | cond_anxious | 분리불안 / 불안행동 | 3 |
| condition | cond_destructive | 파괴 행동 | 4 |
| condition | cond_repetitive | 반복 행동 (강박) | 3 |
| condition | cond_toileting | 배변 문제 | 3 |
| alert | alert_aggression | 공격성 | 4 |
| alert | alert_barking | 과도한 짖음 | 3 |
| alert | alert_territorial | 영역 방어 | 3 |
| meal | meal_guarding | 음식 자원 지키기 | 4 |
| meal | meal_picky | 편식 / 식욕부진 | 2 |
| meal | meal_stealing | 음식 훔치기 | 3 |
| social | social_reactive | 사회적 반응성 | 3 |
| social | social_fearful | 사회적 공포 | 3 |
| social | social_dominant | 지배 행동 | 3 |
| social | social_separation | 분리 불안 | 3 |

**미탐지 행동**: `unknown` category → 수집·기록, 라벨링 보류

---

## 라벨 출력 JSON 스키마

```json
{
  "id": "UUID",
  "run_id": "labeling_runs.id",
  "frame_id": "video_frames.id",
  "preset_id": "walk_pulling",
  "category": "walk",
  "label": "walk_pulling",
  "antecedent": "다른 개를 발견한 직후 목줄이 팽팽해짐",
  "behavior": "앞발로 바닥을 긁으며 강하게 앞으로 당김",
  "consequence": "보호자가 줄을 당겨 멈추게 함",
  "intensity": 4,
  "confidence": 0.87,
  "pose_keypoints": [
    {"x": 0.45, "y": 0.32, "c": 0.91},
    ...
  ],
  "video_segment_ms": [1200, 3400],
  "labeler_model": "gemma4-unsloth-e4b:latest",
  "review_status": "auto_approved",
  "synced": false,
  "taillog_log_id": null
}
```

---

## Intensity 척도 (1-5)

| 점수 | 의미 | 기준 |
|------|------|------|
| 1 | 매우 약함 | 행동이 거의 보이지 않음, 관찰만 가능 |
| 2 | 약함 | 경미한 반응, 쉽게 중단됨 |
| 3 | 보통 | 명확히 관찰되고 지속적 |
| 4 | 강함 | 강도 높음, 개입 필요 |
| 5 | 매우 강함 | 제어 어려움, 즉각 개입 필요 |

---

## review_status 값

| 값 | 조건 | 다음 단계 |
|----|------|---------|
| `pending` | 초기 상태 | quality_gate 대기 |
| `auto_approved` | confidence ≥ 0.85 | sync_writer 대상 |
| `human_review` | 0.65 ≤ confidence < 0.85 | 수동 검수 큐 |
| `rejected` | confidence < 0.65 OR critic fail | 폐기 |
| `synced` | Supabase sync 완료 | 종료 |

---

## TailLog behavior_logs 매핑

```
behavior_labels.preset_id → behavior_logs.type_id (INTEGER 매핑 — OD-02 미결)
behavior_labels.antecedent → behavior_logs.antecedent (TEXT)
behavior_labels.behavior → behavior_logs.behavior (TEXT)
behavior_labels.consequence → behavior_logs.consequence (TEXT)
behavior_labels.intensity → behavior_logs.intensity (INTEGER 1-5)
behavior_labels.run_id.created_at → behavior_logs.occurred_at (TIMESTAMPTZ)
```

> **OD-02 미결**: `preset_id` (문자열) → `type_id` (INTEGER) 변환 테이블 미정.
> `docs/ref/OPEN-DECISIONS.md` 참조.
