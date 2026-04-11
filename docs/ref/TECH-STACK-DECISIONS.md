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
- **설치 요건**: deeplabcut + Python 3.10 또는 3.11 가상환경 필요 (Python 3.14 미호환)
- **공통 확정 항목**:
  - 프레임 추출 속도: `1 FPS`
  - 배치 크기: 기본 16, GPU 메모리 <4GB 시 8로 fallback

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
  - 입력: `video_path`, `output_json_path`
  - 출력: `[{"bodypart": ..., "x": ..., "y": ..., "c": ...}, ...]` JSON 파일
  - 호출: `.venv_dlc/bin/python scripts/compare/run_superanimal.py --video ... --output ...`

### A-02. LLM 역할 분담
| 에이전트 | 모델 | 이유 |
|---------|------|------|
| behavior_classifier | `gemma4-unsloth-e4b:latest` (5GB) | 속도 우선, 분류 반복 작업 |
| abc_labeler | `gemma4-unsloth-e4b:latest` (5GB) | 속도 우선, 구조화 반복 |
| critic | `gemma4:26b-a4b-it-q4_K_M` (17GB) | 정확도 우선, 최종 검수 |
| watchdog | rule engine (Python) | deterministic, LLM 없음 |
| sync_writer | rule engine (Python) | deterministic, LLM 없음 |

- **Ollama 엔드포인트**: `http://localhost:11434`
- **모델 이름 (정확한 tag)**: `gemma4-unsloth-e4b:latest`, `gemma4:26b-a4b-it-q4_K_M`
- **shadow mode 초기**: critic은 `gemma4:26b`로 시작. 데이터 200건 누적 후 promote 여부 평가

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
