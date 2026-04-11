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

## 필드 매핑 테이블 (실제 스키마 기준 — 2026-04-11 확인)

| taillog_labeling | TailLog behavior_logs | 변환 규칙 | 비고 |
|-----------------|----------------------|---------|------|
| `id` (UUID) | — | 매핑 안함 | TailLog가 새 UUID 생성 |
| `preset_id` (str) | `behavior_type` (TEXT) | 그대로 | ~~type_id INTEGER 없음~~ |
| `antecedent` (TEXT) | `antecedent` (TEXT) | 그대로 | |
| `behavior` (TEXT) | `behavior` (TEXT) | 그대로 | |
| `consequence` (TEXT) | `consequence` (TEXT) | 그대로 | |
| `intensity` (1-5) | `intensity` (INTEGER) | 그대로 | |
| `frame_id` (INT) | `occurred_at` (TIMESTAMPTZ) | run.created_at + frame_id초 | 1 FPS 기준 |
| `is_quick_log` | FALSE | 고정값 | ABC 라벨이므로 quick_log 아님 |
| `dog_id` | `612a3d4f-6fc1-406e-8a15-5430a096eee2` | 고정 UUID | anonymous dog (OD-01 해결) |

---

## dog_id 정책 (OD-01 ✅ 해결 — 2026-04-11)

- anonymous dog UUID: `612a3d4f-6fc1-406e-8a15-5430a096eee2`
- dogs 테이블 name=`labeling_pipeline_v1`, breed=`unknown`
- 모든 YouTube-sourced 라벨은 이 dog에 귀속 (Phase 4에서 실제 dog 매핑 예정)

---

## behavior_type 매핑 (OD-02 ✅ 해결 — 2026-04-11)

`type_id` INTEGER 컬럼 없음 (실제 스키마 확인). 실제 컬럼은 `behavior_type TEXT`.
`preset_id` 값을 그대로 `behavior_type`에 삽입. 별도 매핑 불필요.

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
