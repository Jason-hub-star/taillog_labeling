# Weekly Pipeline Audit

> 파이프라인 드리프트 감시, 회귀 탐지.
> 주 1회 실행.

---

## 목적
파이프라인 각 단계의 성능 기준선 대비 회귀를 탐지한다.

## 처리
1. **단계별 처리량 확인**:
   - collector: 일평균 영상 수집 건수
   - pose_extractor: 탐지율 (탐지 성공 / 전체 프레임)
   - behavior_classifier: parse 성공률
   - critic: pass rate
   - sync_writer: sync 성공률
2. **회귀 탐지**:
   - 각 지표가 기준선 대비 > 15% 저하 시 경고
3. **HALT 이력 확인**:
   - 이번 주 HALT 발생 건 및 원인 분석
4. **OPEN-DECISIONS 점검**:
   - 해결 기한 초과한 OD 항목 확인

## 기준선 (Phase 2 이후 설정)
- 초기: 기준선 미확정 → 수집만 진행

## 참조
- `docs/ref/PIPELINE-OPERATING-MODEL.md`
- `docs/ref/OPEN-DECISIONS.md`
