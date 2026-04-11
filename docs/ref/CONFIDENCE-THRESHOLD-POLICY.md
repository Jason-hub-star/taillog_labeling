# Confidence Threshold Policy — SSOT

> 신뢰도 임계값·계산 방식·이상치 정책 정의.
> quality_gate 에이전트와 watchdog이 이 문서를 참조한다.

---

## 임계값

| 범위 | review_status | 다음 처리 |
|------|-------------|---------|
| ≥ 0.85 | `auto_approved` | sync_writer로 즉시 |
| 0.65 ~ 0.84 | `human_review` | 수동 검수 큐 |
| < 0.65 | `rejected` | 폐기 (SQLite 기록 유지) |

---

## 계산식

```python
confidence = (llm_confidence * 0.5 + consistency_score * 0.3 + keypoint_quality * 0.2)
```

### llm_confidence (가중치 0.5)
- LLM 응답의 `"confidence"` 필드 값 (0~1)
- LLM이 confidence를 제공하지 않으면 0.6 기본값

### consistency_score (가중치 0.3)
- 연속 5프레임에서 동일 label 비율
- 예: 5프레임 중 4프레임이 `walk_pulling` → 0.8
- 단일 프레임만 있는 경우: 0.5 기본값

### keypoint_quality (가중치 0.2)
- YOLOv8 탐지된 17개 keypoints의 평균 confidence
- 탐지된 keypoints가 절반 미만이면 0.3 패널티

---

## Cold Start 정책 (Phase 1 초기 2주)

> 데이터가 없는 초기에는 conservative 모드 적용

```python
# 초기 2주: 모든 라벨을 human_review로 설정
if total_synced_labels < 100:
    review_status = 'human_review'  # confidence 무관
```

- **이유**: 모델 성능 기준선 수립 전 전수 검수로 데이터 품질 확보
- **해제 조건**: 100건 검수 완료 후 정상 임계값 적용

---

## 카테고리별 임계값 (Phase 2 이후 검토)

> 행동 중요도에 따라 임계값 차등 적용 (미래 계획)

| category | 위험도 | 제안 임계값 |
|----------|--------|-----------|
| alert (공격성) | HIGH | ≥ 0.90 |
| condition (분리불안) | HIGH | ≥ 0.88 |
| walk | MEDIUM | ≥ 0.85 |
| play | MEDIUM | ≥ 0.85 |
| meal | LOW | ≥ 0.82 |
| social | LOW | ≥ 0.82 |

> Phase 1~2는 카테고리 무관 동일 임계값(0.85) 적용.

---

## 이상치 탐지 (watchdog 트리거)

| 지표 | 임계값 | 조치 |
|------|--------|------|
| 특정 label avg confidence | < 0.5 (최근 50건) | watchdog → 모델 재평가 요청 |
| 전체 avg confidence 하락 | > 10% 감소 (주간) | watchdog → pipeline audit |
| rejection rate | > 50% (최근 100건) | HALT + 주인님 통지 |
| human_review 누적 | > 500건 미검수 | 자동화 속도 감소 |

---

## Cohen's Kappa 목표 (OD-05 — Phase 3 확정)

> human_review 항목의 라벨러 간 일관성 측정
> Phase 3 시작 전 목표치 확정 예정

- **현재 미결**: Cohen's Kappa ≥ 0.80 (excellent) 잠정 목표
- **측정 방법**: 동일 영상 30건을 2인이 독립 라벨링 후 비교
