# TailLog Labeling — Automation Pack

이 폴더는 Claude 스케줄러에 등록할 운영 프롬프트 모음이다.

## Recommended Set

| File | Purpose | Cadence |
|------|---------|---------|
| `daily-pipeline.md` | YouTube 수집 → 포즈 추출 → 분류 → ABC 라벨링 | 매일 1회 |
| `daily-quality-gate.md` | 신뢰도 필터링 (≥0.85 자동 승인, 0.65~0.85 큐) | 매일 1회, pipeline 이후 |
| `daily-critic-review.md` | gemma4:26b 품질 검수 (shadow → active) | 매일 1회, quality-gate 이후 |
| `daily-sync-monitor.md` | Supabase sync 상태 감시 + 실패 복구 | 매일 1회, critic-review 이후 |
| `weekly-model-eval.md` | gemma4 모델 비교 평가, promote 결정 | 주 1회 |
| `weekly-dataset-health.md` | 라벨 분포, 신뢰도 트렌드, 이상 탐지 | 주 1회 |
| `weekly-pipeline-audit.md` | 파이프라인 드리프트 감시, 회귀 탐지 | 주 1회 |

## Execution Order (Daily)

```
daily-pipeline → daily-quality-gate → daily-critic-review → daily-sync-monitor
```

## Operating Rule

- 한 자동화가 한 번에 하나의 결정만 내린다.
- promote 전에 항상 shadow/eval 증거를 남긴다.
- 새 모델 도입은 shadow → eval → activate 순서로 진행한다.
- HALT 조건 발생 시 파이프라인 중단 + 수동 확인 후 재시작.

## Handoff Rule

- 새 인수인계 문서는 `HANDOFF-TEMPLATE.md`를 복사해서 작성한다.
- `HANDOFF.md`에는 현재 구현 상태·수동 경계·실패 semantics를 반드시 적는다.
- handoff 내용이 코드와 충돌하면 문서보다 구현을 우선 확인하고 즉시 갱신한다.

## SSOT 참조

모든 결정은 `docs/ref/` 문서를 따른다:
- 모델·임계값: `TECH-STACK-DECISIONS.md`
- 에이전트 역할: `AGENT-OPERATING-MODEL.md`
- 파이프라인 구조: `PIPELINE-OPERATING-MODEL.md`
- 실패 처리: `FAILURE-HANDLING.md`
