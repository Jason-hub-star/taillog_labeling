# Weekly Autoresearch Loop

> Karpathy autoresearch 패턴 적용 — 프롬프트/모델 실험 keep/discard 루프.
> 주 2~3회 실행. 한 번에 하나의 가설만.

---

## 목적
라벨링 품질을 점진적으로 개선한다. 작은 실험 → 메트릭 비교 → keep/discard.

## 실험 구조 (매 실행마다 아래 포맷 준수)

```yaml
hypothesis: "X를 바꾸면 Y 지표가 Z% 개선될 것"
scope: "프롬프트 / 모델 / 임계값 / 수집 전략 중 하나"
baseline: "현재 avg confidence / auto_approved rate / 기타 지표"
sample_size: 50~100건
time_budget: "조사 20분 + 실행 30분 + 정리 10분"
keep_condition: "기준선 대비 +3% 이상 + 회귀 없음"
discard_condition: "개선 불명확 OR 복잡도 과다 OR 실행 시간 +50% 이상"
```

## 처리
1. `docs/status/SELF-CRITIQUE-LOG.md`에서 "다음 주 실험" 항목 가져오기
2. 가설 1개 선택 (가장 임팩트 클 것)
3. 샘플 50~100건으로 실험 실행
4. `docs/ref/QA-METRICS.md` 기준선과 비교
5. keep/discard 판정
6. keep 시: 코드/프롬프트 반영 + `docs/ref/TECH-STACK-DECISIONS.md` 업데이트
7. discard 시: 이유 기록 + SELF-CRITIQUE-LOG에 교훈 추가

## 실험 후보 예시

| 가설 | 지표 | 예상 효과 |
|------|------|---------|
| few-shot 예시 3개 추가 | abc_labeler 신뢰도 | +5% |
| 연속 3프레임 → 5프레임으로 확장 | consistency_score | +3% |
| intensity 계산을 키포인트 속도 기반으로 변경 | intensity 정확도 | +8% |
| 검색어에 "강아지 훈련" 추가 | alert 카테고리 비율 | +10% |

## 금지 사항
- 기준선 없이 변경 금지
- 2개 이상 변수 동시 변경 금지
- keep 판정 전 코드 반영 금지

## 참조
- `docs/ref/QA-METRICS.md` — 기준선 및 목표값
- `docs/ref/MODEL-ROLE-MAP.md` — promote 사이클
- `docs/status/SELF-CRITIQUE-LOG.md` — 실험 기록
