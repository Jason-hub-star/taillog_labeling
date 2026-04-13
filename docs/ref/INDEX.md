# TailLog Labeling — Reference Index

> SSOT(Single Source of Truth) 문서 목록.
> 모든 에이전트·파이프라인 결정은 이 문서들이 최종 기준이다.
> 코드와 문서가 충돌하면 문서를 먼저 확인하고 즉시 갱신한다.

## 문서 거버넌스 규칙

| 폴더 | 들어갈 내용 | 들어가면 안 되는 것 |
|------|-----------|-----------------|
| `docs/ref/` | **확정·잠금된 결정만** | 미결, 리서치 노트, 비교 결과 |
| `docs/status/` | 진행 상태, pre-dev 체크리스트, 결정 로그 | 잠금 결정 |
| `docs/architecture/` | 스키마, 다이어그램, 구현 상세 | 정책·전략 |

**오염 방지 규칙**:
- `PENDING` 항목이 ref에 있으면 → 확정 후 즉시 채우거나 삭제
- 리서치·비교·실험 결과 → `docs/status/` 에 저장
- ref 파일이 늘어나야 한다면 → 기존 파일 확장 우선, 신규 파일은 독립 주제일 때만

---

## docs/ref — 잠금된 결정 (변경 시 DECISION-LOG 기록 필수)

| 파일 | 용도 | 상태 |
|------|------|------|
| `TECH-STACK-DECISIONS.md` | **모든 기술 결정 SSOT** — 스택·모델·임계값·정책 | ✅ LOCKED |
| `AGENT-OPERATING-MODEL.md` | 에이전트 팀 역할·한계·에스컬레이션 규칙 | ✅ LOCKED |
| `PIPELINE-OPERATING-MODEL.md` | event-driven 파이프라인 5단계 구조 | ✅ LOCKED |
| `MODEL-ROLE-MAP.md` | LLM 역할 분담·shadow 정책·promote 사이클 | ✅ LOCKED |
| `LABEL-SCHEMA.md` | 라벨 출력 포맷·6 categories·21 behaviors | ✅ LOCKED |
| `CONFIDENCE-THRESHOLD-POLICY.md` | 신뢰도 임계값·계산 방식·이상치 정책 | ✅ LOCKED |
| `SUPABASE-SYNC-CONTRACT.md` | behavior_logs 동기화 규약·매핑·dog_id 정책 | ✅ LOCKED |
| `YOUTUBE-SOURCE-POLICY.md` | 영상 수집 기준·검색어·품질 필터·보존 정책 | ✅ LOCKED |
| `FAILURE-HANDLING.md` | 실패 유형·retry 정책·escalation 경로 | ✅ LOCKED |
| `PHASE-PLAN.md` | Phase 1~4 마일스톤·완료 기준·검증 방법 | ✅ LOCKED |
| `MODEL-ROADMAP.md` | 포즈 모델 단계별 전략 (SuperAnimal→YOLOv8 로드맵) | ✅ LOCKED |

## docs/ref — 미결 (협의 필요)

| 파일 | 항목 | 담당 |
|------|------|------|
| `QA-METRICS.md` | 라벨 품질 지표·기준선·이상 탐지 기준 | ✅ LOCKED |
| `OPEN-DECISIONS.md` | 미잠금 항목 목록 (dog_id 매핑 전략 등) | 주인님 확인 필요 |

## docs/status — 운영 상태

| 파일 | 용도 |
|------|------|
| `DECISION-LOG.md` | 결정 기록 (pending/resolved) |
| `PIPELINE-DIAGRAM.md` | 파이프라인 ASCII 다이어그램 |
| `SELF-CRITIQUE-LOG.md` | 주간 자기 회고 + 실험 기록 |
| `PRE-DEV-CHECKLIST.md` | Phase 1 시작 전 완료 항목 (모델 비교, 연결 테스트) |
| `EXTERNAL-DATASETS.md` | 공개 강아지 행동 데이터셋 조사 — few-shot/전이학습 활용 로드맵 |

## docs/architecture — 구현 상세

| 파일 | 용도 |
|------|------|
| `sqlite-schema.md` | SQLite 전체 스키마 (테이블·인덱스·제약) |
| `model-architecture.md` | YOLOv8-pose + Gemma4 조합 설명 |
