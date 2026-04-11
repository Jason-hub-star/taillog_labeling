# Weekly Model Eval

> gemma4-unsloth vs gemma4:26b 비교. promote 결정.
> 주 1회 실행.

---

## 목적
현재 운영 중인 모델의 성능을 측정하고 promote/rollback을 결정한다.

## 처리
1. 샘플 50건 선택 (최근 라벨 중 human_review 완료 항목)
2. gemma4-unsloth-e4b와 gemma4:26b 양쪽으로 재분류
3. 비교 지표:
   - confidence 분포 (mean, p50, p95)
   - critic pass rate
   - 평균 응답 시간 (ms)
   - human_review 일치율
4. eval report 저장 (`docs/qa/eval-reports/`)

## Promote 조건 (behavior_classifier용 모델 업그레이드 시)
- 신규 모델 pass rate ≥ 95%
- 응답 시간 < 2초
- 주인님 최종 승인

## Rollback 조건
- 현재 모델 pass rate < 70% (최근 100건)
- 응답 실패율 > 20%

## Shadow → Active 전환 결정 (critic용)
- shadow critic pass rate ≥ 90% (200건 기준)
- 주인님 승인 후 `MODEL-ROLE-MAP.md` 업데이트

## 참조
- `docs/ref/MODEL-ROLE-MAP.md`
- `docs/ref/TECH-STACK-DECISIONS.md`
