# Decision Log

> 주요 결정 기록. 새 결정 시 상단에 추가.

---

## 2026-04-14 — Vision LLM 백엔드 전환 + 배포 전략 확정

| 항목 | 결정 | 근거 |
|------|------|------|
| Vision LLM 모델 | `gemma4:26b` (로컬) → **`gemini-2.5-flash`** (API) | gemini-2.0-flash 신규 계정 차단(2026-06-01 종료), 로컬 발열·수명 우려 |
| GPT-4o-mini 탈락 | 동일 5프레임 비교: complex scene에서 unknown 포기 | Gemini cond_good/0.90 vs GPT unknown/0.50 (000060.jpg 직접 비교) |
| API 비용 (545장) | $0.42 / 3,000건까지 총 ~$2.3 예상 | 사실상 무시 가능, OD-06 해결 |
| 파인튜닝 모델 후보 | YOLOv8-cls nano (3.8MB) / MobileViT-S (5.6MB) | 카테고리당 100~350장으로 파인튜닝 가능 (Ultralytics 공식 가이드) |
| 배포 타겟 단기 | **사용자 폰 (TFLite/CoreML)** | iPhone CoreML <33ms, 추가 비용 0원 |
| 배포 타겟 중기 | RPi 5 + 카메라 (항상켜짐) | 스타터킷 $120~180, Coral 가속기 추가 시 실시간 가능 |
| IP캠 번들 | RTSP 스트림 연동 (폰/Pi에서 추론) | 카메라 자체 칩 탑재는 펌웨어 수정 필요 — 현실적으로 불가 |
| 전용 HW 제작 | MVP 검증 후 검토 (Jetson Orin Nano 등) | 현재 단계에서 보류 |

**변경 파일**: `TECH-STACK-DECISIONS.md` (A-10 업데이트, A-11 신규), `MODEL-ROADMAP.md` (배포 전략 추가), `OPEN-DECISIONS.md` (OD-06 resolved)

---

## 2026-04-12 — 정상행동 카테고리 추가 (v2.0 스키마)

| 항목 | 결정 | 근거 |
|------|------|------|
| 카테고리 수 | ~~21개~~ → **27개** (정상 5 + 문제 21 + unknown) | POC 결과 일상 영상 전부 unknown → 정상행동 선택지 부재가 원인 |
| 정상행동 카테고리 | normal_rest / normal_walk / normal_play / normal_eat / normal_social | 일상 브이로그에서 대부분 등장하는 행동 패턴 |
| is_problematic 필드 | `behavior_labels` 테이블에 BOOLEAN 컬럼 추가 | 정상/문제 필터링, Streamlit 통계 뷰, sync 조건 분기 |
| 신뢰도 임계값 차등 | 정상행동 0.80 / 문제행동 0.85 | 문제행동은 false positive 비용 높음 (부정적 낙인) |
| Vision 프롬프트 | 2단계 분류 (성질 판단 → 구체 카테고리) + reasoning 필드 | 정상/문제 혼동 방지, 디버깅 가능성 |
| 데이터 수집 | 일상 영상 70% + 문제 30% (Phase 1) | 정상행동 프레임 충분히 확보 필요 |

## 2026-04-13 — Streamlit 검수 앱 버그 수정 5건 + T1~T9 완주 테스트

| 항목 | 버그 | 수정 |
|------|------|------|
| `review_app.py` `load_labels()` | `review_status = 'pending'` 조회 — DB에 존재하지 않는 상태값 | `'human_review'`로 수정 (QualityGate가 설정하는 실제 값) |
| `review_app.py` `load_stats()` | `pending` 집계 쿼리 오류, `reviewed`/`approved`/`synced` 통계 누락 | `human_review` 기준으로 수정, 4개 통계 신규 추가 |
| `review_app.py` "✅ 맞음" 버튼 | `save_label(..., "human_review", ...)` — 눌러도 상태 그대로 | `"auto_approved"` 로 수정 → SyncWriter 픽업 가능 |
| `review_app.py` "❌ 틀림" 버튼 | `save_label(..., "human_review", ...)` — 동일 문제 | `"rejected"` + `preset_id='unknown'` 으로 수정 |
| `review_app.py` 카테고리 변경 탭 | 버튼 클릭 시 `"human_review"` 저장 | `"auto_approved"` 로 수정 |
| 사이드바 | Cold Start 진행률 미표시 | `synced < 100` 시 `🔴 Cold Start: N/100건` 표시 추가 |

**T1~T9 완주 테스트 결과 (2026-04-13): 6/6 PASS** ✅
- T4 네비게이션: 다음/이전 버튼, 번호 직접 이동 정상
- T5 맞음 버튼: DB `auto_approved` 저장 확인
- T6 틀림 버튼: DB `rejected + preset_id='unknown'` 저장 확인
- T7 카테고리 변경: 문제행동 탭 선택 후 DB 반영 확인
- T8 새 행동 제안: `category_suggestions` 테이블 저장 확인
- T9 마지막 페이지: "다음 ▶" disabled 처리 확인

> 핵심 원인: QualityGate가 `human_review` 상태를 설정하는데 앱이 `pending`으로 조회 → 라벨이 0건으로 보이는 치명적 버그. 수정 후 SyncWriter 연동 흐름까지 end-to-end 정상 확인.

## 2026-04-13 — 외부 데이터셋 실제 다운로드 검증 결과

| 데이터셋 | 실제 내용 | 등급 수정 | 활용 가능성 |
|----------|----------|-----------|------------|
| Dog Emotion v2 (HuggingFace) | 감정별 이미지 4,000장. 30장 few-shot 샘플 저장 완료 | ⭐⭐⭐⭐⭐ 유지 | cond_good/tired/alert_aggression few-shot 예시 즉시 활용 |
| ziya07 (Kaggle) | 합성 센서 CSV만 존재, 이미지 없음 | ⭐⭐⭐⭐⭐ → ⭐⭐ | 활용 불가 |
| dogflw (Kaggle) | 이미지 있으나 46개 좌표만 있고 행동 라벨 없음 | ⭐⭐⭐ → ⭐⭐ | 활용 불가 |

> 다운로드 스크립트: `scripts/setup/download_external_datasets.py`
> 저장 위치: `data/external/few_shot_samples/dog_emotion_v2/` (30장, 944KB)

## 2026-04-13 — Opus 코드 리뷰: 버그 수정 4건

| 항목 | 버그 | 수정 |
|------|------|------|
| `abc_labeler_prompt.py` | bodypart 이름 한국어 하드코딩 (`keypoint_names = ["코", "왼쪽_눈", ...]`) — CLAUDE.md A-07 위반 | bodypart 필드 직접 참조 (`kp.get("bodypart")`) 로 교체 |
| `abc_labeler_prompt.py` | 인덱스 기반 keypoint 접근 (`keypoints[j]`, `keypoint_names[j]`) — bodypart 순서 의존 | `for kp in keypoints` 순회로 변경 (A-07 준수) |
| `review_app.py` `save_suggestion()` | `UPDATE behavior_labels` 시 `category='unknown'` 갱신 누락 → category 컬럼 오염 | `category='unknown'` 추가 |
| `classifier_prompt.py` | `ALL_LABELS[:-1]` — unknown이 마지막이라는 암묵적 가정 | `[l for l in ALL_LABELS if l != "unknown"]` 명시 필터링 |

> Opus 자기 리뷰(2026-04-13) → pytest 38/38 통과 유지

---

> LABEL-SCHEMA.md v2.0 업데이트 완료 (2026-04-12)

## 2026-04-12 — Phase 3 재설계: Vision LLM 기반 행동 분류 전환

| 항목 | 결정 | 근거 |
|------|------|------|
| behavior_classifier 입력 | ~~keypoints JSON~~ → **프레임 이미지 (JPEG)** | raw 좌표 숫자만으론 LLM이 행동 분류 불가 — dry_run 결과 100% unknown 확인 |
| 사용 모델 | ~~gemma4-unsloth-e4b~~ → **gemma4:26b (멀티모달 Vision)** | 이미지 이해 가능, 로컬 실행 |
| 분류 방식 | 단일 프레임 이미지 zero-shot → M2 이후 5프레임 콜라주 + few-shot | 행동은 시각 정보 + 시간 흐름이 필요 |
| 처리 시간 | keypoints 0.1초/건 → 이미지 **12초/건** (M1 기준) | 품질↑ 대가로 속도 하락 허용 |
| 파인튜닝 | **보류** — 라벨 데이터 3000건 이후 검토 | 현재 데이터 0건 — 닭/달걀 문제 |
| 인간 검수 | cold start 100건 전수 검수 유지 + threshold 자동화 병행 | zero-shot 오류율 미지수 — 기준선 확보 필수 |

> TECH-STACK-DECISIONS.md A-02, A-10 업데이트 완료

## 2026-04-12 — Streamlit 검수 앱 채택 (POC 선행)

| 항목 | 결정 | 근거 |
|------|------|------|
| 검수 UI | **Streamlit** (`scripts/review/review_app.py`) | 브라우저 기반, 이미지 크게 표시, 빠른 개발 |
| 검수 액션 | 맞음(A) / 틀림(R) / 수정(E) / 메모(M) | 최소 인터페이스로 빠른 검수 |
| 진행 순서 | Streamlit 앱 구현 → POC 테스트 → Vision LLM 재설계 | 검수 툴 없이 POC 결과 판단 불가 |
| CLI 검수 | 보류 — Streamlit으로 대체 | 이미지 표시 및 수정 UX 부족 |

## 2026-04-12 — orchestrator dry_run 버그 수정

| 항목 | 결정 | 근거 |
|------|------|------|
| 버그 | `dry_run=True` 시 Stage 3~5 완전 스킵 | pose_extractor가 DB 미저장 → orchestrator DB 쿼리 결과 0건 |
| 수정 | `pose_extractor.run()` 반환값 `bool` → `(bool, List[PoseResult])` | 메모리 직접 전달로 DB 의존 제거 |
| dry_run 스킵 조건 | abc_labeler/critic은 `dry_run=True` 시 스킵 | label이 DB에 없어 545개 "라벨 없음" 오류 방지 |
| COLD_START_LIMIT | 클래스 기본값 100 유지, `COLD_START_LIMIT=0` 환경변수 오버라이드 가능 | 테스트/첫 sync 시 cold_start 비활성화 필요 |
| 결과 | `pytest tests/ -v` 37/37 통과, dry_run Stage 1~5 에러 없이 완주 | |

## 2026-04-12 — A-07 포맷 전면 적용 (코드·테스트 정렬)

| 항목 | 결정 | 근거 |
|------|------|------|
| 테스트 포맷 통일 | `{"bodypart": "nose", "x": ..., "y": ..., "c": ...}` A-07 포맷으로 전면 교체 | M3에서 `KeyPoint.bodypart` 필수 필드로 변경됐으나 테스트 4곳·docstring 1곳이 레거시 포맷 유지 |
| 레거시 탐지 방법 | `bodypart` 없을 때 `"unknown"` fallback → 테스트 통과 위장 | 포맷 불일치 상태였음 — `Grep` 교차검증으로 발견 |
| 수정 범위 | `tests/test_models.py` 2곳, `tests/test_prompts.py` 3곳, `src/agents/behavior_classifier.py` docstring 1곳 | |
| 결과 | `pytest tests/ -v` 37/37 통과 | |

## 2026-04-12 — YOLOv8 학습 데이터 저장 구현 (A-09)

| 항목 | 결정 | 근거 |
|------|------|------|
| keypoint 포맷 수정 | ~~COCO 17pt~~ → **Dog-Pose 24pt** | Dog-Pose 공개 데이터셋이 24pt (17pt 아님) |
| 저장 전략 | 39pt 그대로 저장, Phase 3에서 24pt 변환 | 변환 전 실제 데이터 분포 확인 필요 |
| bbox 추정 | keypoint convex hull (confidence ≥ 0.3) | H5에 bbox 없음 확인 |
| 변환 스크립트명 | ~~sa_to_coco.py~~ → `sa_to_dogpose24.py` | 타겟 포맷이 Dog-Pose 24pt |
| 영상 삭제 정책 | 14일 유지 | 프레임 이미지 별도 보존으로 해결 |

## 2026-04-12 — YOLOv8 학습 데이터 전략 확정

| 항목 | 결정 | 근거 |
|------|------|------|
| 학습 전략 | **전략 A: Dog-Pose 병합** | Ultralytics 공식 Dog-Pose 6,773장 + 자체 3,000건 |
| 기존 목표 | ~~자체 10,000건~~ | 근거 없는 수치 — 삭제 |
| 신규 목표 | 자체 3,000건 + Dog-Pose 6,773장 = ~9,773장 | Ultralytics 공식 데이터셋 기준 |
| 첫 실험 시점 | 자체 500건 도달 시 | transfer learning 100~800장 범위 |
| 근거 URL | https://docs.ultralytics.com/datasets/pose/dog-pose/ | Ultralytics 공식 |

> MODEL-ROADMAP.md Phase 4+ 섹션 및 의존성 타임라인 업데이트 완료

## 2026-04-12 — GPU 추론 전략 검증 결과

| 항목 | 결정 | 이유 |
|------|------|------|
| A-08 GPU 구현 | **보류** | tensorflow-metal 1.2.0이 TF 2.21 설치 시 import 파괴 (`libmetal_plugin.dylib` 경로 불일치) |
| 환경 복구 | `pip uninstall tensorflow-metal` | TF 2.21.0 즉시 정상 복구 확인 |
| 재검토 시점 | tensorflow-metal TF 2.21+ 공식 지원 출시 시 | PyPI 릴리즈 모니터링 |
| 현재 전략 | CPU 단일 모드 유지 | check_env.py 16/16 통과 상태 유지 |

## 2026-04-12 — GPU 추론 전략 설계

| 항목 | 결정 | 이유 |
|------|------|------|
| 디바이스 전략 | `auto` 기본 (GPU 우선 → CPU 폴백) | M1 Metal GPU 활용, 안정성 확보 |
| M1 GPU 활성화 | `tensorflow-metal` `.venv_dlc`에 추가 | 설치만으로 Metal 자동 감지 |
| 폴백 트리거 | `ResourceExhaustedError` / `MemoryError` | OOM 시 자동 CPU 재시도 |
| 배치 크기 | GPU 16 / CPU 폴백 시 8 | CPU 폴백 시 메모리 압박 완화 |
| 제어 인터페이스 | `superanimal_infer.py --device [auto\|gpu\|cpu]` | subprocess 격리 설계 유지 |
| 스킬화 보류 | 현 단계 불필요 | 멀티모델 교체 실험 시 재검토 |

> 상세: `docs/ref/TECH-STACK-DECISIONS.md` A-08

## 2026-04-11 — 프로젝트 초기 설정

| 항목 | 결정 | 이유 |
|------|------|------|
| Supabase URL | `https://qufjlveukaoiokhpkhwj.supabase.co` | TailLog 프로덕션 |
| 포즈 모델 | YOLOv8n-pose (AP-10K 범용) | 경량, 로컬 추론 |
| LLM 스택 | Ollama (gemma4-unsloth + gemma4:26b) | 로컬, 비용 없음 |
| 신뢰도 임계값 | ≥0.85 auto / 0.65~0.84 human / <0.65 discard | conservative 시작 |
| Cold start 정책 | 초기 100건 전수 human_review | 품질 기준선 확보 |
| 영상 보존 | 14일 후 자동 삭제 | 개인정보 보호 |
| 저장소 구조 | SQLite local → Supabase 단방향 | 분리된 로컬 환경 |

## 미결 (OPEN-DECISIONS.md 참조)

| ID | 항목 | 마감 |
|----|------|------|
| OD-01 | dog_id 매핑 전략 | Phase 4 전 |
| ~~OD-02~~ | type_id INTEGER 매핑 → **RESOLVED** 2026-04-11: FK 없는 순수 INTEGER, 1~21 매핑 확정 | — |
| OD-03 | React Native vs Flutter | Phase 4 후 |
| OD-04 | Telegram 봇 설정 | Phase 1 후 |
| OD-05 | Cohen's Kappa 목표치 | Phase 3 |
| OD-06 | Supabase 비용 한도 | Phase 3 |
| OD-07 | Vision LLM POC 결과 — gemma4:26b zero-shot 품질 기준 확정 | Phase 3.1 후 |
| OD-08 | 5프레임 콜라주 전환 시점 (M2 확정 또는 POC 결과 기반 조기 전환) | Phase 3.2 전 |
| OD-09 | Supabase behavior_logs.is_problematic 컬럼 추가 여부 — TailLog 팀 협의 | Phase 3 전 |
