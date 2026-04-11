# QA Metrics — 라벨 품질 지표 SSOT

> 라벨 품질을 측정하는 기준선 정의.
> weekly-dataset-health.md와 weekly-model-eval.md가 이 문서를 참조한다.

---

## 핵심 지표

| 지표 | 설명 | 목표값 | 측정 주기 |
|------|------|--------|---------|
| **auto_approved rate** | 전체 라벨 중 confidence ≥ 0.85 비율 | ≥ 30% (Phase 2), ≥ 50% (Phase 4) | 일별 |
| **rejection rate** | confidence < 0.65 비율 | ≤ 30% | 일별 |
| **avg confidence** | 전체 라벨 평균 신뢰도 | ≥ 0.75 | 일별 |
| **critic shadow pass rate** | critic이 통과시킨 비율 (shadow mode) | ≥ 90% → active 전환 조건 | 누적 200건 |
| **sync success rate** | Supabase INSERT 성공률 | ≥ 95% | 일별 |
| **pose detection rate** | 프레임 중 강아지 탐지 성공 비율 | ≥ 70% | 영상별 |

---

## 카테고리 분포 목표 (Phase 3 이후)

| category | 최소 비율 | 최대 비율 |
|----------|---------|---------|
| walk | 10% | 40% |
| play | 10% | 30% |
| condition | 5% | 25% |
| alert | 5% | 25% |
| meal | 5% | 20% |
| social | 5% | 20% |

> 한 카테고리가 40% 초과 시 weekly-dataset-health가 경고 → 수집 전략 재조정

---

## 이상 탐지 기준 (watchdog 트리거)

| 조건 | 심각도 | 조치 |
|------|--------|------|
| rejection rate > 50% (최근 100건) | HIGH | HALT + 주인님 통지 |
| avg confidence 전주 대비 -10% | MEDIUM | pipeline-audit 트리거 |
| 특정 label avg confidence < 0.5 | MEDIUM | 해당 label 모델 재평가 |
| sync success rate < 90% | HIGH | sync_monitor 즉시 실행 |
| pose detection rate < 50% | MEDIUM | 영상 소스 품질 점검 |

---

## Cohen's Kappa (OD-05 — Phase 3 확정)

- **목표**: κ ≥ 0.80 (excellent)
- **측정법**: 동일 영상 30건을 2인이 독립 라벨링 후 비교
- **측정 시점**: Phase 3 (500건 누적 후)
- **현재**: 미측정

---

## 기준선 스냅샷 (Phase별 기록)

| Phase | 기간 | avg confidence | auto_approved rate | 총 라벨 |
|-------|------|---------------|-------------------|--------|
| Phase 1 | — | — | — | 0 |
| Phase 2 | — | — | — | — |
| Phase 3 | — | — | — | — |
| Phase 4 | — | — | — | — |

> Phase 완료 시 실제 수치로 업데이트
