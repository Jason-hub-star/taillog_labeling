# Daily Sync Monitor

> Supabase sync 상태 감시 + 실패 항목 복구.
> daily-critic-review.md 이후 실행.

---

## 목적
auto_approved 라벨을 TailLog Supabase로 동기화하고 실패를 복구한다.

## 처리
1. `behavior_labels WHERE review_status='auto_approved' AND synced=FALSE` 조회
2. sync_writer: Supabase `behavior_logs` INSERT
   - URL: `https://qufjlveukaoiokhpkhwj.supabase.co`
   - 인증: `SUPABASE_SERVICE_ROLE_KEY`
   - 매핑: `docs/ref/SUPABASE-SYNC-CONTRACT.md` 참조
3. 실패 항목 재시도:
   - `sync_attempts WHERE status='failed' AND attempt_number < 3` 조회
   - exponential backoff retry
4. 일일 sync 리포트 생성 (`data/exports/sync_logs/`)

## 성공 조건
- synced 건수 증가
- 실패율 < 5%

## HALT 조건
- schema mismatch → 즉시 중단 + 로그
- RLS violation → 즉시 중단 + 로그

## 리포트 항목
- 오늘 synced 건수
- 누적 synced 건수
- 실패 건수 + 원인
- human_review 대기 건수

## 참조
- `docs/ref/SUPABASE-SYNC-CONTRACT.md`
- `docs/ref/FAILURE-HANDLING.md`
