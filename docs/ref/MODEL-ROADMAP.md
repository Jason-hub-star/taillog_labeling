# Model Roadmap — SSOT

> 포즈 추출 모델의 단계별 전략. 잠금된 결정.
> 변경 시 `docs/status/DECISION-LOG.md`에 기록.

---

## 전략 요약

```
Phase 0    비교 테스트     → SuperAnimal vs YOLOv8 실증 결과로 Phase 1 모델 확정
Phase 1~3  라벨링 도구     → SuperAnimal-Quadruped (정확도 우선)
Phase 4+   앱 탑재 모델    → YOLOv8-pose Korean Dog (속도·경량 우선)
```

**핵심 원칙**: SuperAnimal이 생성한 고품질 라벨 10,000건이 YOLOv8 재학습 데이터가 된다.
두 모델은 경쟁 관계가 아니라 파이프라인 상의 전후 관계다.

---

## Phase별 모델 역할

### Phase 0 — 비교 테스트 (개발 시작 전)

- **목적**: 실제 강아지 영상에서 두 모델 성능 직접 측정
- **스크립트**: `scripts/compare/run_all.sh`
- **판단 기준**:
  - SuperAnimal 탐지율이 15%p 이상 높음 → SuperAnimal 채택
  - 비슷하거나 YOLOv8이 높음 → YOLOv8 Dog-Pose 재학습 검토
- **완료 조건**: `data/exports/compare_report.md` 생성 → OD-07 resolved
- **참조**: `docs/ref/OPEN-DECISIONS.md` OD-07

### Phase 1~3 — 라벨링 파이프라인 모델

- **모델**: `SuperAnimal-Quadruped` (DeepLabCut ModelZoo)
  - `model_name`: `hrnet_w32`
  - `detector_name`: `fasterrcnn_resnet50_fpn_v2`
- **선택 이유**:
  - Zero-shot mAP 84.6 (강아지 포함 사각형동물, Nature Comm. 2024)
  - 재학습 없이 즉시 사용 가능
  - 39개 keypoint (COCO 17개보다 세밀)
  - 라벨링은 속도보다 정확도가 우선
- **출력**: H5 파일 → 프레임별 keypoint → LLM 행동 분류 컨텍스트
- **한계**:
  - DeepLabCut 생태계 (설치 복잡)
  - 비디오 단위 처리 (프레임 실시간 불가)
  - 모바일 탑재 불가

### Phase 4+ — TailLog 앱 탑재 모델

- **모델**: `YOLOv8n-pose` (Korean Dog fine-tuned)
- **학습 데이터**: Phase 1~3에서 생성된 라벨 10,000건 이상
- **선택 이유**:
  - 경량 (모바일/엣지 탑재 가능)
  - 실시간 추론 (~50ms/frame GPU)
  - ultralytics 생태계 (배포 툴링 완비)
  - BoT-SORT 내장 (다중 강아지 추적)
- **재학습 전략**:
  - SuperAnimal keypoint → COCO 17-point 포맷 변환
  - 한국 소형견 비율 보정 (포메라니안·말티즈 오버샘플링)
  - Dog-Pose 데이터셋 + 자체 라벨 병합 학습
- **완료 조건**: 소형견 탐지율 ≥ 85%, 추론 속도 ≤ 100ms/frame

---

## keypoint 포맷 전환 계획

```
SuperAnimal 39-point                    COCO 17-point (YOLOv8)
────────────────────────────────────── ──────────────────────────
nose, left_eye, right_eye, ...    →    nose, left_eye, right_eye, ...
39개 사각형동물 전용 포인트          →    17개 (공통 서브셋만 매핑)
```

- **변환 스크립트**: Phase 3 후반 개발 예정 (`scripts/convert/sa_to_coco.py`)
- **매핑 테이블**: 미결 → Phase 3에서 확정

---

## 의존성 타임라인

```
OD-07 resolved (Phase 0)
    ↓
SuperAnimal 파이프라인 개발 (Phase 1~2)
    ↓
라벨 2,000건 누적 (Phase 3)
    ↓
keypoint 포맷 변환 스크립트 개발 (Phase 3 후반)
    ↓
YOLOv8 Korean Dog 재학습 (Phase 4)
    ↓
TailLog 앱 탑재 (Phase 4+)
```
