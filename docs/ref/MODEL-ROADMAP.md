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

**핵심 원칙**: SuperAnimal이 생성한 고품질 라벨 **자체 3,000건 + Dog-Pose 공개 6,773장 병합**이
YOLOv8 재학습 데이터가 된다. 두 모델은 경쟁 관계가 아니라 파이프라인 상의 전후 관계다.

---

## Phase별 모델 역할

### Phase 0 — 비교 테스트 (완료 ✅)

- **목적**: 실제 강아지 영상에서 두 모델 성능 직접 측정
- **결과**: SuperAnimal 채택 — YOLOv8 탐지율 18.3%로 실용 불가 (OD-07 resolved 2026-04-11)

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
  - **DLC 2.x (TF V1 기반): M1 Metal GPU 가속 불가** — DLC 3.0 (PyTorch) 정식 출시 시 해소 예정 (OD-08)

### Phase 4+ — TailLog 앱 탑재 모델

- **모델**: `YOLOv8n-pose` (Korean Dog fine-tuned)
- **학습 데이터 전략 (전략 A — Dog-Pose 병합)**:
  - **자체 라벨**: Phase 1~3에서 생성된 라벨 **3,000건**
  - **공개 데이터**: Ultralytics Dog-Pose 데이터셋 **6,773장** (훈련셋)
  - **총 학습 데이터**: ~9,773장 (Dog-Pose 6,773 + 자체 3,000)
  - **근거**: Ultralytics 공식 Dog-Pose 데이터셋 + transfer learning 100~800장 기준
    (출처: https://docs.ultralytics.com/datasets/pose/dog-pose/, Ultralytics 블로그)
- **중간 실험 트리거**:
  - 자체 500건 → 첫 학습 실험 (소형견 도메인 영향 측정)
  - 자체 1,500건 → 소형견 비율 보정 의미있는 시점
  - 자체 3,000건 → 프로덕션 결정
- **선택 이유**:
  - 경량 (모바일/엣지 탑재 가능)
  - 실시간 추론 (~50ms/frame GPU)
  - ultralytics 생태계 (배포 툴링 완비)
  - BoT-SORT 내장 (다중 강아지 추적)
- **재학습 전략**:
  - SuperAnimal 39pt → **Dog-Pose 24pt 공통 서브셋** 변환 (COCO 17pt 아님)
  - 한국 소형견 비율 보정 (포메라니안·말티즈 오버샘플링)
  - Dog-Pose 공개 24pt 데이터셋 + 자체 변환 24pt 라벨 병합 학습
- **완료 조건**: 소형견 탐지율 ≥ 85%, 추론 속도 ≤ 100ms/frame

---

## keypoint 포맷 전환 계획

```
SuperAnimal 39-point              Dog-Pose 24-point (YOLOv8 병합 기준)
────────────────────────────────  ─────────────────────────────────────
nose, left_eye, right_eye,        nose, left_eye, right_eye,
left_ear_tip, right_ear_tip,      left_ear_tip, right_ear_tip,
withers, tail_base ...            withers, tail_start, tail_end,
front/rear paw, knee 포함  →      front/rear paw·knee·elbow (×4),
39개 중 공통 포인트 추출           chin, throat (총 24개)
```

- **Dog-Pose 24pt 이름**: front/rear_left/right_paw·knee·elbow, tail_start·end,
  left/right_ear_base·tip, nose, chin, left/right_eye, withers, throat
  (출처: https://docs.ultralytics.com/datasets/pose/dog-pose/)
- **변환 스크립트**: Phase 3 후반 개발 예정 (`scripts/convert/sa_to_dogpose24.py`)
- **매핑 테이블**: 미결 → Phase 3 자체 라벨 500건 도달 후 실제 데이터 보고 확정
- **저장 전략**: Phase 1~3는 **39pt 그대로 저장**, Phase 3에서 24pt 변환 레이어 추가

---

## 예상 기간

파이프라인 자동화 완성 기준 (하루 영상 5개, 영상당 ~50 라벨):

| 마일스톤 | 자체 라벨 목표 | 예상 소요 |
|---------|------------|---------|
| 첫 학습 실험 | 500건 | ~2주 |
| 소형견 보정 | 1,500건 | ~6주 |
| 프로덕션 결정 | 3,000건 | ~12주 |

---

## 의존성 타임라인

```
OD-07 resolved (Phase 0) ✅
    ↓
SuperAnimal 파이프라인 개발 (Phase 1~2)
    ↓
자체 라벨 500건 누적 → sa_to_dogpose24.py 개발 + 첫 YOLOv8 실험
    ↓
자체 라벨 1,500건 → 소형견 비율 보정 학습
    ↓
자체 라벨 3,000건 + Dog-Pose 6,773장 → YOLOv8 Korean Dog 프로덕션 결정
    ↓
TailLog 앱 탑재 (Phase 4+)
```
