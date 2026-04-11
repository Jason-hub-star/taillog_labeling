# Daily Quality Gate

> 신뢰도 임계값 기반 라벨 분류.
> daily-pipeline.md 이후 실행. 이후 daily-critic-review.md 실행.

---

## 목적
behavior_labels 중 pending 항목을 신뢰도 기준으로 분류한다.

## 처리
1. SQLite `behavior_labels WHERE review_status = 'pending'` 조회
2. confidence 기준 분류:
   - ≥ 0.85 → `auto_approved`
   - 0.65 ~ 0.84 → `human_review`
   - < 0.65 → `rejected`
3. **cold start 모드** (synced < 100건): 전체 `human_review` 강제
4. auto_approved 건수 → sync_writer 대기 큐 등록

## 성공 조건
- pending 항목 전체 처리 완료
- auto_approved 또는 human_review 건수 > 0

## 실패 조건
- rejection rate > 80% → watchdog 경고 (프롬프트 품질 점검 필요)

## 참조
- `docs/ref/CONFIDENCE-THRESHOLD-POLICY.md`
