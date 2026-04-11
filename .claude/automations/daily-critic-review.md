# Daily Critic Review

> gemma4:26b 품질 검수. shadow mode (초기 200건) → active mode.
> daily-quality-gate.md 이후 실행.

---

## 목적
critic 에이전트가 auto_approved 라벨을 검수한다.

## Shadow Mode (synced < 200건)
1. `behavior_labels WHERE critic_pass IS NULL` 조회
2. gemma4:26b로 ABC 완전성·intensity 합리성·label 유효성 검사
3. 결과를 `critic_pass_shadow` 컬럼에 기록만 함 (sync 영향 없음)
4. pass rate 측정 및 기록

## Active Mode (synced ≥ 200건, pass rate ≥ 90% 확인 후)
1. critic fail → `review_status = 'human_review'` 강제 변경
2. critic pass → quality_gate 결과 유지

## Shadow → Active 전환 조건
- shadow 200건 누적
- shadow pass rate ≥ 90%
- 주인님 승인

## 성공 조건
- critic 처리 건수 > 0
- shadow pass rate 기록 완료

## 참조
- `docs/ref/MODEL-ROLE-MAP.md`
- `docs/ref/AGENT-OPERATING-MODEL.md`
