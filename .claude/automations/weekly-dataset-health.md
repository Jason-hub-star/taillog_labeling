# Weekly Dataset Health

> 라벨 분포, 신뢰도 트렌드, 이상 탐지.
> 주 1회 실행.

---

## 목적
데이터셋 품질과 분포를 점검하여 파이프라인 이상을 조기 발견한다.

## 처리
1. **분포 분석**:
   - category별 라벨 비율 (6개 카테고리 균형)
   - label별 건수 (21개 행동 분포)
   - intensity 평균 및 분포
2. **신뢰도 트렌드**:
   - 주간 average confidence 변화
   - auto_approved / human_review / rejected 비율 변화
3. **이상 탐지**:
   - 특정 label avg confidence < 0.5 → 경고
   - rejection rate > 50% → HALT 권고
   - sync 성공률 저하 → 경고
4. 리포트 저장 (`docs/qa/`)

## 경고 기준
- 카테고리 쏠림: 1개 카테고리 > 60% → 수집 전략 재검토
- confidence 급락: 전주 대비 > 10% 하락 → 모델 재평가 요청

## 참조
- `docs/ref/CONFIDENCE-THRESHOLD-POLICY.md`
- `docs/ref/LABEL-SCHEMA.md`
