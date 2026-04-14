# Tech Stack Decisions — SSOT

> 이 문서는 taillog_labeling의 모든 기술 결정의 단일 진실 원천이다.
> 변경 시 반드시 `docs/status/DECISION-LOG.md`에 기록한다.
> 코드·프롬프트·에이전트 설정은 이 문서를 참조한다.

---

## A. 모델 결정 (B-블록)

### A-01. 포즈 추출 모델
- **✅ 확정**: **SuperAnimal-Quadruped** (2026-04-11, OD-07 해결)
- **결정 근거**: YOLOv8n-pose 강아지 탐지율 평균 18.3% (실용 수준 미달) → SuperAnimal 채택
  - 소형견 탐지 특히 취약 (포메라니안 8.3%, 홈캠 6.7%, 다중 강아지 0%)
  - SuperAnimal-Quadruped Zero-shot mAP **84.6** (Nature Comm. 2024)
- **keypoint 포맷**: SuperAnimal quadruped (39-point) — COCO 17pt 아님
- **conf 임계값**: 0.3 (SuperAnimal 기준, 추후 교정)
- **설치 요건**: deeplabcut **2.3.11** + Python 3.11 가상환경 필요 (Python 3.14 미호환)
  - `deeplabcut 2.3.11`: tables>=3.7.0 wheel 패치 필요 (기본 wheel은 tables==3.8.0으로 M1 빌드 불가)
  - `tensorflow 2.21.0` + `tf-keras 2.21.0` 필수 (Keras 3 단독 설치 시 compat.v1.layers 충돌)
  - `keras` 3.x 패키지는 **유지 필수** (제거 시 TF 2.21 lazy loader RecursionError 발생)
  - `tf_keras/legacy_tf_layers` 심링크 필요 (TF 2.21 경로 불일치 해결)
  - 설정 자동화: `bash scripts/setup/deeplabcut-venv.sh` (패치 포함)
- **공통 확정 항목**:
  - 프레임 추출 속도: `1 FPS`
  - 배치 크기: 기본 16 (DLC `video_inference_superanimal` API가 batch_size 파라미터 미지원 — 외부 제어 불가)

### A-08. 추론 디바이스 전략 ⛔ 보류 (2026-04-12 검증 결과)
- **현재 상태**: **CPU 단일 모드 유지** — tensorflow-metal 설치 불가 확인
- **보류 사유**: `tensorflow-metal 1.2.0` 설치 시 TF 2.21 `import` 파괴 (`libmetal_plugin.dylib` 경로 불일치)
  - `pip uninstall tensorflow-metal` 후 즉시 복구 확인 (check_env.py 16/16 통과)
- **재검토 조건**: tensorflow-metal이 TF 2.21+ 공식 지원 출시 시 또는 DLC 3.0 (PyTorch) 전환 시
- **원설계 (참고용)**:
  - `auto` 모드: GPU 우선 → `ResourceExhaustedError` / `MemoryError` 시 CPU 폴백
  - `superanimal_infer.py --device [auto|gpu|cpu]` 인터페이스
  - ~~`TF_METAL_DEVICE_MASK`~~ — 비공식 환경변수, 사용 금지
- ~~배치 크기 연동~~: `video_inference_superanimal()` 시그니처에 `batch_size` 파라미터 없음 → 삭제

### A-09. YOLOv8 학습 데이터 저장 전략 ✅ 확정 (2026-04-12)

- **결정**: 포즈 추출 시점에 프레임 이미지 + YOLO 39pt 라벨 저장 (부가 출력)
- **저장 경로**: `data/training/frames/` (JPEG), `data/training/labels/39pt/` (.txt)
- **포맷**: YOLO pose format — `class_id cx cy w h [kpx kpy kpv] × 39`
  - bbox: confidence ≥ 0.3 keypoint 외접 사각형 (Convex Hull)
  - 좌표: 정규화 (0~1), visibility: 0/1
  - bodypart 순서: H5 MultiIndex 추출 순서 그대로 (하드코딩 금지)
- **Phase 전략**:
  - Phase 1~3: **39pt 그대로 저장** (`kpt_shape: [39, 2]`)
  - Phase 3 후반 (500건 도달): `sa_to_dogpose24.py` 개발 → 24pt 변환
  - Phase 4: Dog-Pose 공개 24pt (6,773장) + 자체 변환 24pt 병합
- **설계 원칙**: 학습 데이터 저장은 부가 출력 — 실패해도 파이프라인 계속 진행
- **영상 삭제 정책**: 14일 삭제 유지 — 프레임만 별도 보존
- **변경 파일**: `config.py`, `superanimal_infer.py`, `pose_extractor.py`
- **신규 파일**: `scripts/train/generate_dataset_yaml.py`

### ❌ A-08 검증 결과 — 보류 확정 (2026-04-12)

| 항목 | 결과 | 근거 |
|------|------|------|
| **tensorflow-metal 1.2.0 × TF 2.21** | **호환 불가** | 설치 즉시 TF import 파괴 — `libmetal_plugin.dylib`가 존재하지 않는 `_solib_darwin_arm64/` 경로 참조. 공식 호환 목록 TF 2.18까지 |
| **Metal × DLC V1 네트워크** | 검증 불가 | TF import 자체 실패로 GPU 감지 단계 도달 불가 |

- **검증 스크립트 실행**: `check_gpu_feasibility.py --install` (2026-04-12)
- **즉각 복구**: `pip uninstall tensorflow-metal` → TF 2.21.0 정상 복구 확인
- **결론: A-08 전체 보류** — CPU 단일 모드 유지 (현 상태)
- **재검토 조건**: tensorflow-metal가 TF 2.21 이상을 공식 지원하는 버전 출시 시

### A-05. 다중 강아지 추적 전략
- **추적 알고리즘**: `BoT-SORT` 확정 (ByteTrack 대비 가려짐·조명 불안정 상황에서 우수)
  - MOTA 80.5%, IDF1 80.2% (MOT17 벤치마크)
  - YOLOv8 기본 지원: `model.track(source=video, tracker='botsort.yaml')`
- **Phase 1~2**: 단일 강아지 영상만 수집 (ID 추적 미활성화)
- **Phase 3 이후**: BoT-SORT 활성화, 다중 강아지 ID 추적
- **데이터 구조 확장 (Phase 3)**:
  ```json
  // 현재 (단일)
  {"frame_id": 100, "keypoints": [...]}
  // Phase 3 이후 (다중)
  {"frame_id": 100, "detections": [
    {"track_id": 1, "keypoints": [...]},
    {"track_id": 2, "keypoints": [...]}
  ]}
  ```
- **한계**: 2마리 강아지가 겹칠 때 ID swap 발생 가능 → Phase 3 후 개선 검토

### A-06. Keypoint 좌표 정규화 정책
- **저장 포맷**: 절대 픽셀 좌표 (0~W, 0~H) 원본 보존
- **모델 입력 시**: (x/W, y/H) 정규화 (0~1 범위)
- **방향(orientation) 보존**: 원본 좌표 그대로 유지 — 방향은 행동 분류에 유의미한 정보
  - `walk_pulling`: 신체 기울기, 머리 위치
  - `social_fearful`: 꼬리 내림, 귀 위치
- **좌우 위치**: 프레임 내 좌/우 절대 위치는 행동 분류와 무관 → 정규화 OK
- **Phase 3 이후 검토**: Procrustes Alignment (강아지 중심축 기준 keypoint 정렬)

### A-07. Keypoint JSON 저장 포맷 ✅ 확정 (2026-04-11)
- **결정**: bodypart 이름 포함 저장 (Option A)
- **이유**: 인덱스만 저장하면 "어떤 인덱스가 어떤 부위인지" 별도 문서 참조 필요 → 디버깅·필터링 불가
- **포맷**:
  ```json
  [
    {"bodypart": "nose",       "x": 123.4, "y": 456.7, "c": 0.91},
    {"bodypart": "left_ear",   "x": 110.2, "y": 440.1, "c": 0.85},
    {"bodypart": "right_ear",  "x": 135.6, "y": 441.3, "c": 0.88},
    ...
  ]
  ```
- **bodypart 이름**: SuperAnimal-Quadruped H5 출력의 MultiIndex 컬럼 level_1 그대로 사용
  - 실제 이름 목록은 최초 추론 실행 시 `run_superanimal.py` 출력에서 확인
  - 39개 bodypart (nose, eyes, ears, spine, tail, 4×3 limbs 등)
- **저장 대상**: `pose_results.keypoints_json` (SQLite TEXT)
- **1 FPS 샘플링 위치**: `pose_extractor.py` 에서 H5 전체 프레임 중 `frame_id % fps == 0` 필터
- **subprocess 인터페이스**:
  - 진입점: `scripts/superanimal_infer.py` (파이프라인 전용 — 배치 비교용 `scripts/compare/run_superanimal.py`와 분리)
  - 입력: `--video <path>` `--output <json_path>`
  - 출력: `[{"bodypart": ..., "x": ..., "y": ..., "c": ...}, ...]` JSON 파일
  - 호출: `Config.DLC_VENV_PYTHON scripts/superanimal_infer.py --video ... --output ...`
  - 확장성: 향후 SLEAP/MMPose 교체 시 `Config.SUPERANIMAL_INFER_SCRIPT` 경로 교체만으로 대응
  - 경로 상수: `Config.SUPERANIMAL_INFER_SCRIPT`, `Config.DLC_VENV_PYTHON` (하드코딩 금지)

### A-02. LLM 역할 분담 (2026-04-12 재설계)

| 에이전트 | 모델 | 입력 | 이유 |
|---------|------|------|------|
| behavior_classifier | `gemma4:26b-a4b-it-q4_K_M` (17GB, **Vision**) | **프레임 이미지 (JPEG)** | ~~keypoints JSON~~ → 이미지 직접 분류 (zero-shot Vision) |
| abc_labeler | `gemma4-unsloth-e4b:latest` (5GB) | label + context | 속도 우선, 구조화 반복 |
| critic | `gemma4:26b-a4b-it-q4_K_M` (17GB) | ABC + confidence | 정확도 우선, 최종 검수 |
| watchdog | rule engine (Python) | logs | deterministic, LLM 없음 |
| sync_writer | rule engine (Python) | approved labels | deterministic, LLM 없음 |

- **Ollama 엔드포인트**: `http://localhost:11434`
- **모델 이름 (정확한 tag)**: `gemma4-unsloth-e4b:latest`, `gemma4:26b-a4b-it-q4_K_M`
- **shadow mode 초기**: critic은 `gemma4:26b`로 시작. 데이터 200건 누적 후 promote 여부 평가
- **분류 방식 전환 근거**: dry_run 검증 결과 keypoints 좌표 기반 분류 100% unknown — 구조적 한계 확인 (2026-04-12)

### A-10. Vision LLM 행동 분류 전략 ✅ 확정 (2026-04-12, 업데이트 2026-04-14)

- **결정**: behavior_classifier 입력을 keypoints JSON → **프레임 이미지 (JPEG)** 로 전환
- **현재 모델**: `gemini-2.5-flash` — Google Gemini API (클라우드)
- **백엔드 전환**: `LLM_BACKEND=gemini` (기본값) / `LLM_BACKEND=ollama` (로컬 fallback)
- **Phase 전략**:
  - **Phase 1 (M1, ~100건)**: 단일 프레임 이미지 zero-shot, cold start 100건 전수 검수
  - **Phase 2 (M2, ~500건)**: 5프레임 콜라주 + few-shot (confidence threshold 자동 승인 활성화)
  - **Phase 3+ (M4, ~3,000건)**: 파인튜닝 전환 (→ A-11 참조)
- **처리 시간 (Gemini API 기준)**: 8~10초/프레임, 545장 기준 약 75~90분
- **전체 파이프라인 1건**: 포즈 추출 7분 + 분류 84분 = **~90분/영상**
- **인간 검수 UI**: Streamlit (`scripts/review/review_app.py`) — 이미지 + 맞음/틀림/수정/메모
- **파인튜닝 전환 조건**: 라벨 데이터 3,000건 + Cohen's Kappa ≥ 0.80 (→ A-11)

#### Gemini 2.5 Flash 선택 근거 (2026-04-14)

| 항목 | 내용 |
|------|------|
| **선택 모델** | `gemini-2.5-flash` |
| **탈락: gemini-2.0-flash** | 신규 계정 접근 차단, 2026-06-01 완전 종료 (출처: ai.google.dev/gemini-api/docs/deprecations) |
| **탈락: GPT-4o-mini** | 구성 분석 정확도 11% (GPT-4o 57% 대비), complex scene에서 unknown 포기 — 동일 5프레임 직접 비교: Gemini cond_good/0.90 vs GPT unknown/0.50 (000060.jpg) |
| **탈락: qwen2.5vl:7b (로컬)** | 전 프레임 unknown 출력, 23개 카테고리 프롬프트 이해 불가 |
| **탈락: gemma4:26b (로컬)** | 29~40초/프레임(워밍업 후), M5 MacBook Air 팬리스 발열·수명 부담 |
| **비용 (545장)** | $0.42 (입력 $0.30/M토큰, 출력 $2.50/M토큰) |
| **맥북 부담** | API 방식 — GPU 0%, CPU <10%, 발열 없음 |

#### Vision LLM 비용 비교 (545장 기준)

| 모델 | 비용 | 비고 |
|------|------|------|
| GPT-4o-mini | $0.16 | complex scene 품질 약함 |
| **gemini-2.5-flash** | **$0.42** | **현재 채택** |
| Qwen-VL-Max | $0.83 | 한국어·복잡 장면 미검증 |
| Claude Haiku 4.5 | $1.12 | — |
| GPT-4o / Grok-2-vision | $2.25~2.61 | 과도한 비용 |

#### API → 파인튜닝 전환 임계값

| 단계 | 라벨 수 | 행동 |
|------|---------|------|
| Phase 1~2 | 0 → 3,000건 | Gemini API 유지 (예상 총비용 ~$2.3) |
| Phase 3 검토 시작 | **3,000건** | 파인튜닝 실험 (Cohen's Kappa ≥ 0.80 확인 후) |
| API 완전 대체 | **5,000건** | 자체 모델 정확도 ≥ Gemini 기준 시 중단 |

### A-11. 행동 분류기 파인튜닝 전략 (Phase 3+, 2026-04-14)

> 포즈 추정 모델(YOLOv8n-pose, Phase 4+)과 별도. 행동 분류에 특화된 경량 분류기.

#### 후보 모델 비교

| 모델 | 크기 | iPhone 추론 | Android (S23) | RPi 5 | 권장 용도 |
|------|------|------------|---------------|-------|---------|
| **YOLOv8-cls nano** | 3.8 MB | ~70ms | ~100ms | ~700ms | CPU 환경, 고FPS |
| **MobileViT-S** | 5.6 MB | <33ms | 4.7ms | ~300ms | 모바일 최우선 |

- **최소 학습 데이터**: 카테고리당 100~350장 → 23개 카테고리 × 200장 = **4,600장 권장**
  (출처: Ultralytics YOLOv8 classification guide — 100장/클래스에서 수렴 가능, 300장에서 안정)
- **전이학습 필수**: ImageNet 사전학습 가중치에서 파인튜닝 (scratch 대비 10배 데이터 절약)
- **내보내기**: YOLOv8 → TFLite / CoreML / ONNX 자동 지원 (ultralytics export)

#### 파인튜닝 실험 트리거

| 트리거 | 조건 | 행동 |
|--------|------|------|
| 1차 실험 | 자체 라벨 500건 | YOLOv8-cls nano 소규모 학습, 정확도 측정 |
| 본격 검토 | 자체 라벨 3,000건 + Kappa ≥ 0.80 | MobileViT-S vs YOLOv8-cls 비교 |
| API 대체 | 자체 모델 정확도 ≥ Gemini 85% | Gemini API 호출 중단 |

### A-03. 라벨 출력 포맷 (B-03)
- **기반**: TaillogToss `presets.ts` (6 categories × 21 behaviors)
- **출력 스키마**:
  ```json
  {
    "preset_id": "walk_pulling",
    "category": "walk",
    "label": "walk_pulling",
    "antecedent": "...",
    "behavior": "...",
    "consequence": "...",
    "intensity": 3,
    "confidence": 0.87,
    "pose_keypoints": [...],
    "video_segment_ms": [1200, 3400],
    "labeler_model": "gemma4-unsloth-e4b:latest",
    "review_status": "auto_approved"
  }
  ```
- **미탐지 행동 처리 (B-04)**: 21개 이외 행동 → `unknown` 카테고리로 수집, 라벨링 보류

### A-04. 한국 견종 적응 (B-05)
- **초기**: AP-10K 범용 사용
- **검토 시점**: 데이터 300건 이후, 소형견 비율 측정 후 fine-tune 결정
- **한국 주요 견종**: 포메라니안, 말티즈, 푸들, 비숑 (소형견 다수)

---

## B. 데이터 수집 결정 (D-블록)

### B-01. YouTube 검색 전략 (D-01)
- **전략**: 키워드 무관 일상 강아지 영상 우선
- **초기 검색어 리스트**:
  ```
  KO: "강아지 일상", "강아지 홈캠", "강아지 브이로그", "멍멍이 일상"
  EN: "dog daily routine", "dog home camera", "dog vlog", "puppy daily life"
  ```
- **채널 우선**: 개인 훈련사 채널 > 반려견 일상 채널 > 펫샵 채널
- **피해야 할 영상**: 편집 과다 유튜브 예능, CGI/애니메이션

### B-02. 파이프라인 실행 방식 (D-02)
- **방식**: Claude co-work `.claude/automations/` 마크다운 스케줄러
- **일일 목표**: 500 라벨 (초기 2주), 1000 라벨 (이후)
- **실행 순서**: `daily-pipeline → daily-quality-gate → daily-critic-review → daily-sync-monitor`

### B-03. 신뢰도 임계값 (D-03)
- **≥ 0.85** → `auto_approved` → Supabase sync 즉시
- **0.65 ~ 0.84** → `human_review` → 검수 큐
- **< 0.65** → `discard` → SQLite에 기록, Supabase sync 없음
- **초기 2주**: 모든 라벨을 `human_review`로 설정 (conservative cold-start)
- **계산식**: `confidence = (llm_confidence + consistency_score + keypoint_quality) / 3`

### B-04. 데이터 볼륨 마일스톤 (D-04)
| Phase | 목표 건수 | 활성화 기능 |
|-------|---------|-----------|
| Phase 1 | 50건 | 포즈 추출 검증 |
| Phase 2 | 500건 | behavior_classifier 1차 평가 |
| Phase 3 | 2,000건 | critic shadow 비교 |
| Phase 4 | 10,000건 | 프로덕션 이식 검토 |

### B-05. 영상 품질 기준 (D-05)
- **해상도**: ≥ 480p
- **길이**: 10초 ~ 10분
- **강아지 비율**: 바운딩박스 면적 ≥ 화면의 5%
- **영상 보존 기간**: 14일 후 자동 삭제 (라벨 추출 후)

### B-06. 오디오 처리 (D-06)
- **결정**: **보류** — Phase 2 이후 Whisper 짖음 감지 검토
- **이유**: 초기 복잡도 증가 방지

---

## C. 스택 & 저장소 결정 (S-블록)

### C-01. 파이프라인 언어 (S-01)
- **언어**: Python 3.11+
- **의존성**: `ultralytics`, `yt-dlp`, `ollama` Python SDK, `supabase-py`, `pydantic`, `opencv-python`

### C-02. 로컬 저장소 (S-02)
- **라벨링 DB**: SQLite (`data/databases/labeling.db`)
- **SQLite 설정**: WAL mode 활성화 (동시 접근 대비)
- **원본 영상**: 로컬 파일시스템 (`data/cache/youtube_videos/`) — 14일 후 자동 삭제
- **포즈 결과**: JSON 파일 (`data/cache/pose_results/`) — 라벨링 완료 후 삭제 가능

### C-03. Obsidian 역할 (S-03)
- **역할**: 지식 관리 전용 — `docs/` 폴더를 Obsidian vault로 운영
- **파이프라인 DB 아님**: pipeline state는 SQLite만 사용

### C-04. Supabase 역할 (S-04)
- **역할**: 최종 sync 목적지
- **방향**: 로컬 SQLite → Supabase 단방향 (역방향 sync 없음)
- **대상 테이블**: TailLog `behavior_logs`
- **인증**: `service_role` key (RLS 우회)
- **sync 조건**: `confidence ≥ 0.85` AND `review_status = 'auto_approved'`

### C-05. 모바일 앱 sync (S-05)
- **결정**: **보류** — React Native vs Flutter 미결
- **현재 조치**: REST API 인터페이스만 설계, 구현 없음

---

## D. 프로젝트 구조 결정 (P-블록)

### D-01. 폴더 구조
- vibehub-media 미러링 (`.claude/automations/`, `docs/ref/`, `docs/status/`)

### D-02. 에이전트 실행 순서
```
collector → pose_extractor → behavior_classifier → abc_labeler → critic → quality_gate → sync_writer
                                                                          ↓
                                                                      watchdog (실패 시)
```

### D-03. 첫 실행 순서
1. 모델 다운로드 (`scripts/setup/bootstrap.sh`)
2. SQLite schema init
3. Ollama 연결 확인
4. 샘플 1건 드라이런
5. 자동화 등록

---

## E. 미결 항목 (OPEN-DECISIONS.md 참조)

| ID | 항목 | 마감 |
|----|------|------|
| OD-01 | `dog_id` 매핑 전략 (YouTube 영상 → TailLog anonymous_sid) | Phase 4 전 |
| OD-02 | `type_id` INTEGER 매핑 (preset_id 문자열 → TailLog behavior_logs.type_id) | Phase 4 전 |
| OD-03 | React Native vs Flutter (모바일 sync 아키텍처) | Phase 4 후 |
| OD-04 | Telegram 알림 봇 토큰 설정 | Phase 1 후 |
| OD-05 | Cohen's Kappa 목표치 설정 (human review 일관성 기준) | Phase 3 |
| OD-06 | 예산/비용 한도 (Supabase write 비용) | Phase 3 |
