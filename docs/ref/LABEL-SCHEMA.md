# Label Schema — SSOT v3.0

> **기준**: TaillogToss `presets.ts` (B2B-001) — 서비스 중인 앱이 단일 진실 공급원
> 이 스키마가 SQLite, Supabase sync, 에이전트 프롬프트, 검수 앱의 단일 기준이다.
> **코드 상수**: `src/utils/label_constants.py` (직접 하드코딩 금지)

---

## 변경 이력

| 버전 | 날짜 | 변경 |
|------|------|------|
| v1.0 | 2026-04-11 | 초기 21개 문제행동 |
| v2.0 | 2026-04-12 | 정상행동 5개(normal_*) 추가 → 27개 |
| **v3.0** | **2026-04-13** | **TaillogToss 기준으로 전면 통합 → 23개 + unknown** |

---

## 6 Categories × 23 Behaviors + unknown (총 24개) — v3.0

### 정상행동 (is_problematic = FALSE) — 7개

| category | preset_id | 한국어 | TaillogToss |
|----------|-----------|--------|------------|
| walk | walk_normal | 정상 산책 | walk_normal ✅ |
| play | play_normal | 정상 놀이 | play_normal ✅ |
| condition | cond_good | 컨디션 좋음 | cond_good ✅ |
| condition | cond_excited | 활발/에너지 | cond_excited ✅ |
| meal | meal_full | 완식 | meal_full ✅ |
| social | social_good | 타견 우호 | social_good ✅ |
| social | social_human | 사람 우호 | social_human ✅ |

### 문제행동 (is_problematic = TRUE) — 16개

| category | preset_id | 한국어 | TaillogToss |
|----------|-----------|--------|------------|
| walk | walk_pulling | 리드 당김 | walk_pulling ✅ |
| walk | walk_reactive | 반응성(짖음) | walk_reactive ✅ |
| walk | walk_refuse | 산책 거부 | walk_refuse ✅ |
| play | play_overexcited | 과잉흥분 | play_overexcited ✅ |
| play | play_resource | 자원 지킴 | play_resource ✅ |
| condition | cond_tired | 피곤/무기력 | cond_tired ✅ |
| condition | cond_anxious | 불안 징후 | cond_anxious ✅ |
| alert | alert_vomit | 구토 | alert_vomit ✅ |
| alert | alert_diarrhea | 설사 | alert_diarrhea ✅ |
| alert | alert_limp | 절뚝거림 | alert_limp ✅ |
| alert | alert_aggression | 공격 행동 | alert_aggression ✅ |
| alert | alert_noeat | 식욕부진 | alert_noeat ✅ |
| meal | meal_half | 반식 | meal_half ✅ |
| meal | meal_refuse | 식사 거부 | meal_refuse ✅ |
| social | social_avoid | 타견 회피 | social_avoid ✅ |
| social | social_reactive | 타견 반응 | social_reactive ✅ |

### 미분류

| preset_id | 설명 | is_problematic |
|-----------|------|---------------|
| unknown | 분류 불가 (occluded, 앵글 부족 등) | NULL |

---

## v2.0에서 제거된 라벨 (12개)

> TaillogToss에 없어서 sync해도 앱에서 표시 불가 → 제거
> 기존 데이터 마이그레이션: `src/utils/label_constants.LEGACY_TO_CURRENT`

| 제거된 라벨 | 대체 |
|------------|------|
| walk_fearful, walk_distracted | unknown |
| play_rough | unknown |
| cond_destructive, cond_repetitive, cond_toileting | unknown |
| alert_barking, alert_territorial | unknown |
| meal_guarding, meal_picky, meal_stealing | unknown |
| social_fearful, social_dominant, social_separation | unknown |

---

## Intensity 척도 (1-10) — v3.0

> TaillogToss 기준으로 통일. (v2.0까지는 1-5)

| 범위 | 의미 |
|------|------|
| 1-2 | 미미한 반응 |
| 3-4 | 약함 |
| 5-6 | 보통 |
| 7-8 | 강함 |
| 9-10 | 제어 어려움, 즉각 개입 필요 |

---

## review_status 값

| 값 | 조건 | 다음 단계 |
|----|------|---------|
| `pending` | 초기 상태 | quality_gate 대기 |
| `auto_approved` | 정상행동 conf ≥ 0.80 OR 문제행동 conf ≥ 0.85 | sync_writer 대상 |
| `human_review` | 정상행동 0.60~0.79 OR 문제행동 0.65~0.84 OR unknown | 수동 검수 큐 |
| `rejected` | 정상행동 conf < 0.60 OR 문제행동 conf < 0.65 OR critic fail | 폐기 |
| `synced` | Supabase sync 완료 | 종료 |

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
  "is_problematic": true,
  "antecedent": "다른 개를 발견한 직후 목줄이 팽팽해짐",
  "behavior": "앞발로 바닥을 긁으며 강하게 앞으로 당김",
  "consequence": "보호자가 줄을 당겨 멈추게 함",
  "intensity": 7,
  "confidence": 0.87,
  "review_status": "auto_approved",
  "synced": false
}
```

---

## TailLog behavior_logs 매핑

```
behavior_labels.preset_id  → behavior_logs.behavior_type (TEXT)
behavior_labels.antecedent → behavior_logs.antecedent (TEXT)
behavior_labels.behavior   → behavior_logs.behavior (TEXT)
behavior_labels.consequence → behavior_logs.consequence (TEXT)
behavior_labels.intensity  → behavior_logs.intensity (INTEGER 1-10)
behavior_labels.run_id.created_at → behavior_logs.occurred_at (TIMESTAMPTZ)
```

> **OD-02 ✅ 확정**: `type_id` INTEGER 없음. 실제 컬럼은 `behavior_type TEXT`. preset_id 그대로 삽입.
