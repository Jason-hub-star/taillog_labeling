# Supabase Sync Contract — SSOT

> taillog_labeling → TailLog `behavior_logs` 동기화 규약.
> sync_writer 에이전트는 이 문서만 참조한다.

---

## 동기화 방향

```
[taillog_labeling SQLite]
    behavior_labels (review_status='auto_approved', synced=FALSE)
        ↓  단방향 (역방향 없음)
[TailLog Supabase]
    behavior_logs
```

---

## 필드 매핑 테이블

| taillog_labeling | TailLog behavior_logs | 변환 규칙 | 비고 |
|-----------------|----------------------|---------|------|
| `id` (UUID) | — | 매핑 안함 | TailLog가 새 UUID 생성 |
| `preset_id` (str) | `type_id` (INTEGER) | **OD-02 매핑 테이블 필요** | 미결 |
| `antecedent` (TEXT) | `antecedent` (TEXT) | 그대로 | |
| `behavior` (TEXT) | `behavior` (TEXT) | 그대로 | |
| `consequence` (TEXT) | `consequence` (TEXT) | 그대로 | |
| `intensity` (1-5) | `intensity` (INTEGER) | 그대로 | |
| `video_segment_ms[0]` | `occurred_at` (TIMESTAMPTZ) | run.created_at + segment offset | |
| `is_quick_log` | FALSE | 고정값 | ABC 라벨이므로 quick_log 아님 |
| `dog_id` | **OD-01 필요** | 아래 `dog_id 정책` 참조 | 미결 |
| `duration` | NULL | Phase 2 이후 추정 | |

---

## dog_id 정책 (OD-01 미결)

현재 3가지 옵션 중 **미결정**:

| 옵션 | 방식 | 장단점 |
|------|------|--------|
| A | YouTube URL → 사전 정의 `anonymous_sid` 매핑 | 관리 필요, 유연 |
| B | YouTube 채널별 1개 anonymous dog 자동 할당 | 간단, 채널별 dog |
| C | 라벨링 시 `dog_id` 수동 지정 | 정확, 수동 작업 |

**임시 처리 (Phase 4 전까지)**: 전용 anonymous dog 1개 생성 (`labeling_pipeline_dog`) 사용
- Supabase `dogs` 테이블에 `anonymous_sid='labeling_pipeline_v1'` 레코드 생성
- 모든 YouTube-sourced 라벨은 이 dog에 임시 귀속

---

## type_id 매핑 (OD-02 미결)

```python
# 임시 매핑 (Phase 4 전까지)
# TailLog behavior_logs.type_id 실제 값 확인 후 교체 필요
PRESET_TO_TYPE_ID = {
    "walk_pulling": 1,
    "walk_reactive": 2,
    "walk_fearful": 3,
    "walk_distracted": 4,
    "play_overexcited": 5,
    "play_resource": 6,
    "play_rough": 7,
    "cond_anxious": 8,
    "cond_destructive": 9,
    "cond_repetitive": 10,
    "cond_toileting": 11,
    "alert_aggression": 12,
    "alert_barking": 13,
    "alert_territorial": 14,
    "meal_guarding": 15,
    "meal_picky": 16,
    "meal_stealing": 17,
    "social_reactive": 18,
    "social_fearful": 19,
    "social_dominant": 20,
    "social_separation": 21,
    "unknown": None,  # sync 제외
}
```

> ⚠️ 이 매핑은 임시값이다. TailLog `behavior_logs.type_id` 실제 ENUM/정수값 확인 후 교체 필수.

---

## sync 조건 (AND 조건)

```python
confidence >= 0.85
AND review_status == 'auto_approved'
AND synced == False
AND preset_id != 'unknown'  # unknown은 sync 제외
AND dog_id IS NOT NULL
```

---

## 인증

- **key**: `SUPABASE_SERVICE_ROLE_KEY` (`.env.local`)
- **RLS**: service_role이므로 우회
- **주의**: anon key 절대 사용 금지 (RLS 차단됨)

---

## 실패 처리

| 오류 | 처리 |
|------|------|
| Connection timeout | retry 3회 (1s→2s→4s) |
| RLS violation | HALT → watchdog 즉시 통지 (service_role인데 RLS 오류면 설정 문제) |
| Schema mismatch (컬럼 없음) | HALT → `OPEN-DECISIONS.md`에 기록 |
| Duplicate (동일 occurred_at+dog_id) | skip (중복 허용 안 함) |

---

## sync 후 처리

```sql
-- SQLite 업데이트
UPDATE behavior_labels
SET synced = TRUE,
    taillog_log_id = '<supabase_uuid>',
    review_status = 'synced',
    updated_at = CURRENT_TIMESTAMP
WHERE id = '<label_id>';
```
