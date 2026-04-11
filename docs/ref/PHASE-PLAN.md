# Phase Plan — SSOT

> 4주 구현 마일스톤. 각 Phase의 목표·완료 기준·검증 방법 정의.

---

## Phase 1: 환경 + 기초 인프라 (Week 1)

**목표**: 모든 모델·도구 연결 확인, SQLite 초기화, 샘플 1건 드라이런

| 스텝 | 파일 | 완료 기준 |
|------|------|---------|
| 1.1 | `scripts/setup/bootstrap.sh` | `data/models/yolov8n-pose.pt` 존재 |
| 1.2 | `src/core/config.py` | `python -c "from src.core.config import *"` 오류 없음 |
| 1.3 | `src/core/database.py` | `sqlite3 labeling.db ".tables"` → 7개 테이블 출력 |
| 1.4 | `scripts/setup/test-ollama.sh` | gemma4-unsloth-e4b 응답 확인 |
| 1.5 | `src/core/supabase_client.py` | TailLog DB 연결 확인 |
| 1.6 | `tests/` | `pytest tests/ -v` 전체 통과 |

**Phase 1 완료 기준**:
- [ ] SQLite 7개 테이블 생성 완료
- [ ] `ollama list`에서 두 모델 확인
- [ ] YOLOv8n-pose.pt 다운로드 완료
- [ ] TailLog Supabase 연결 성공
- [ ] 샘플 1건 드라이런 (영상 → 포즈 추출 → 라벨) 오류 없음

---

## Phase 2: 수집 → 포즈 추출 (Week 2)

**목표**: YouTube 자동 다운로드 + YOLOv8 키포인트 추출 파이프라인

| 스텝 | 파일 | 완료 기준 |
|------|------|---------|
| 2.1 | `src/utils/youtube_helper.py` | 1건 다운로드 성공 |
| 2.2 | `src/utils/video_processor.py` | 프레임 추출 (1fps) 성공 |
| 2.3 | `src/agents/collector.py` | SQLite `labeling_runs` 생성 확인 |
| 2.4 | `src/agents/pose_extractor.py` | `pose_results` JSON 저장 확인 |
| 2.5 | `tests/test_collector.py` | pytest 통과 |
| 2.6 | `tests/test_pose_extractor.py` | pytest 통과 |

**Phase 2 완료 기준**:
- [ ] 50건 영상 → 포즈 추출 성공
- [ ] `pose_results` 테이블 50건 이상 저장
- [ ] pose_extractor 탐지율 ≥ 70% (50건 중 35건 이상 강아지 탐지)
- [ ] 일일 자동화 (`daily-pipeline.md`) 1회 실행 성공

---

## Phase 3: 행동 분류 → ABC 라벨링 (Week 3)

**목표**: gemma4-unsloth로 행동 분류 + ABC 구조화, 신뢰도 측정

| 스텝 | 파일 | 완료 기준 |
|------|------|---------|
| 3.1 | `src/utils/prompt_builder.py` | 프롬프트 텍스트 생성 확인 |
| 3.2 | `src/core/llm_client.py` | Ollama 응답 파싱 성공 |
| 3.3 | `src/agents/behavior_classifier.py` | label + confidence 저장 |
| 3.4 | `src/agents/abc_labeler.py` | ABC 3필드 + intensity 저장 |
| 3.5 | `src/agents/critic.py` | critic pass/fail 기록 |
| 3.6 | `tests/test_behavior_classifier.py` | pytest 통과 |

**Phase 3 완료 기준**:
- [ ] 500건 라벨 생성
- [ ] 신뢰도 분포 측정 (≥0.85 비율 확인)
- [ ] critic shadow mode 200건 누적
- [ ] 카테고리별 분포 확인 (6개 중 최소 4개 카테고리 등장)
- [ ] auto_approved 첫 100건 인간 검수 완료

---

## Phase 4: 신뢰도 필터 → Supabase Sync (Week 4)

**목표**: 전체 파이프라인 연결, TailLog behavior_logs 자동 생성

| 스텝 | 파일 | 완료 기준 |
|------|------|---------|
| 4.1 | `src/pipelines/quality_gate_step.py` | review_status 분류 확인 |
| 4.2 | `src/agents/sync_writer.py` | Supabase INSERT 1건 성공 |
| 4.3 | `src/pipelines/run.py` | 전체 파이프라인 1회 실행 성공 |
| 4.4 | `tests/test_integration_e2e.py` | e2e 테스트 통과 |
| 4.5 | `src/agents/watchdog.py` | 실패 큐 + 로그 정상 동작 |

**Phase 4 완료 기준**:
- [ ] TailLog Supabase에 100건 이상 behavior_logs 생성
- [ ] auto_approved rate ≥ 30% (전체 대비)
- [ ] watchdog HALT 없이 3일 연속 자동화 실행
- [ ] weekly-model-eval 1회 실행 완료
- [ ] **OD-01, OD-02 결정 완료** (dog_id 매핑, type_id 매핑)

---

## 전체 데이터 마일스톤

| 마일스톤 | 목표 건수 | 다음 단계 활성화 |
|---------|---------|--------------|
| M1 | 100건 synced | cold start 모드 해제 |
| M2 | 500건 synced | critic active mode |
| M3 | 2,000건 synced | category별 임계값 차등 검토 |
| M4 | 10,000건 synced | 프로덕션 모델 이식 검토 |

---

## 프로덕션 이식 기준 (M4 이후)

- [ ] 10,000건 라벨 누적
- [ ] auto_approved rate ≥ 50%
- [ ] critic active mode pass rate ≥ 90%
- [ ] Cohen's Kappa ≥ 0.80 (human reviewer 간 일관성)
- [ ] 6개 카테고리 균형 분포 (각 카테고리 ≥ 5%)
- [ ] 주인님 최종 승인
