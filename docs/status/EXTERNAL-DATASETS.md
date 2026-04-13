# 외부 공개 데이터셋 조사 — TailLog 행동 분류 활용 가능성

> **목적**: 강아지 행동 라벨링 시간 단축 및 분류 정확도 향상을 위한 공개 데이터셋 조사.
> **결론**: TailLog 23개 preset_id에 바로 쓸 수 있는 데이터셋은 없음.
>           단, few-shot 예시·전이학습 소스로 부분 활용 가능.
> **작성일**: 2026-04-13

---

## 왜 바로 쓸 수 없나 — 근본 원인

| TailLog 라벨 | 공개 데이터셋 한계 |
|------------|-----------------|
| `meal_full`, `meal_half`, `meal_refuse` | 밥그릇 컨텍스트 필요. 야외 행동 데이터셋에 없음 |
| `alert_vomit`, `alert_limp` | 의료 이상징후. 연구용 비공개 또는 극소량 |
| `cond_anxious`, `cond_tired` | 주관적 상태 판단. 표준화된 라벨 없음 |
| `walk_pulling`, `walk_reactive` | TailLog 앱 특화 정의. 학술 라벨과 불일치 |
| `social_avoid`, `social_reactive` | 다두 이상 프레임 필요. 단일 개 중심 데이터셋에 없음 |

---

## 활용 가능성 등급 정의

| 등급 | 의미 |
|-----|------|
| ⭐⭐⭐⭐⭐ | 직접 매핑 가능 (fine-tune 또는 few-shot 바로 사용) |
| ⭐⭐⭐⭐ | 부분 매핑 (카테고리 일치, 라벨 변환 필요) |
| ⭐⭐⭐ | 간접 활용 (전이학습 사전학습 소스) |
| ⭐⭐ | 참고용 (행동 정의 참조) |
| ⭐ | 비관련 (품종 분류 등) |

---

## 1. 감정 / 컨디션 분류 (cond_* 매핑 최우선)

### DEBIw Dataset ⭐⭐⭐⭐⭐
- **출처**: ACM ACI 2022 | [논문](https://dl.acm.org/doi/10.1145/3565995.3566041)
- **크기**: 7,899개 이미지 (원본 15,599 → 필터링 후)
- **감정 카테고리**: Fear(공포), Contentment(만족), Anxiety(불안), Aggression(공격)
- **TailLog 매핑**:
  - Contentment → `cond_good`
  - Anxiety → `cond_anxious`
  - Aggression → `alert_aggression`
  - Fear → `cond_anxious` (부분)
- **활용법**: few-shot 예시 이미지 소스, fine-tune 학습 데이터
- **라이선스**: 공개

### CREMD Dataset ⭐⭐⭐⭐
- **출처**: arXiv 2602.15349 (2026년 최신)
- **크기**: 923개 비디오 클립, 평균 15.8초
- **형식**: 멀티모달 (영상 + 오디오)
- **감정 라벨**: anger, fear, excitement, contentment
- **TailLog 매핑**:
  - excitement → `cond_excited`, `play_overexcited`
  - contentment → `cond_good`
  - fear → `cond_anxious`
  - anger → `alert_aggression`
- **활용법**: 컨디션 분류 few-shot 예시 영상 프레임 추출
- **라이선스**: 공개

### Dog Emotion Dataset v2 ⭐⭐⭐
- **출처**: [Hugging Face](https://huggingface.co/datasets/Dewa/Dog_Emotion_Dataset_v2)
- **크기**: 4,000개 이미지
- **라벨**: sad, angry, relaxed, happy
- **TailLog 매핑**:
  - happy → `cond_good`, `cond_excited`
  - sad → `cond_tired`
  - angry → `alert_aggression`
  - relaxed → `cond_good`
- **활용법**: 감정 분류 few-shot 예시 이미지 (바로 다운로드 가능)
- **라이선스**: 공개

### DogFLW Dataset ⭐⭐⭐
- **출처**: arXiv 2405.11501 | [Kaggle](https://www.kaggle.com/datasets/georgemartvel/dogflw)
- **크기**: 4,335개 이미지
- **주석**: 46개 얼굴 특징점 (DogFACS 기반)
- **TailLog 매핑**: 얼굴 표정 기반 `cond_anxious`, `cond_excited`, `cond_tired` 구분
- **활용법**: Phase 2에서 Critic 에이전트 보조 (얼굴 표정 검증)
- **라이선스**: CC BY-NC 4.0

---

## 2. 산책 / 놀이 행동 (walk_*, play_* 매핑)

### Dog Behavior Monitoring Dataset (ziya07) ⭐⭐⭐⭐⭐
- **출처**: [Kaggle](https://www.kaggle.com/datasets/ziya07/dog-behavior-monitoring-dataset)
- **최신 업데이트**: 2025년 4월
- **특징**: Multi-Level Postures, Atomic Behaviors, Complex Behavior Annotation (계층적 라벨)
- **TailLog 매핑**: `walk_*`, `play_*`, `meal_*`, `social_*` 전반에 걸쳐 매핑 가능
- **활용법**: 가장 포괄적인 소스. few-shot 예시 이미지 추출 우선 검토
- **라이선스**: 공개

### DogMo Dataset ⭐⭐⭐⭐
- **출처**: arXiv 2510.24117
- **크기**: 1,200개 모션 시퀀스, 10마리 개
- **형식**: 멀티뷰 RGB-D 비디오
- **11가지 액션**: running, jumping, walking, standing, sitting, lying, sniffing,
  tail_wagging, head_turning, ear_movement, body_stretching
- **TailLog 매핑**:
  - walking → `walk_normal`
  - running → `cond_excited`, `play_overexcited`
  - lying → `cond_tired`
  - tail_wagging → `cond_excited`, `cond_good`
- **활용법**: 운동 패턴 기반 `alert_limp` 감지 (비정상 walking 패턴 식별)
- **라이선스**: 공개

### DECADE Dataset ⭐⭐⭐
- **출처**: arXiv 1803.10827 | [GitHub](https://github.com/ehsanik/dogTorch)
- **크기**: 380개 비디오 클립, 24,500 프레임
- **형식**: Ego-centric (강아지 시점 카메라)
- **라벨**: walking, playing, sniffing, standing
- **TailLog 매핑**: `walk_normal`, `play_normal` 기본 분류
- **활용법**: 전이학습 사전학습 소스

### EgoPet Dataset ⭐⭐⭐
- **출처**: arXiv 2404.09991 | [공식 사이트](https://www.amirbar.net/egopet/)
- **크기**: 6,646개 비디오 세그먼트, 84시간 (TikTok 482개 + YouTube 338개)
- **라벨**: Locomotion, Visual Interaction (person, cat, dog 구분)
- **TailLog 매핑**:
  - person interaction → `social_human`
  - dog interaction → `social_good`, `social_avoid`, `social_reactive`
- **활용법**: 사회화 행동 분류 few-shot 예시

### Roboflow — Dogs Behavior (YOLO) ⭐⭐⭐
- **출처**: [Roboflow Universe](https://universe.roboflow.com/custom-yolo-dataset-f1bxb/dogs-behavior-pawqf)
- **크기**: ~1,000개 이미지
- **라벨 6가지**: Barking, Eating, Lying, Running, Sitting, Standing
- **TailLog 매핑**:
  - Eating → `meal_full`, `meal_half`
  - Barking → `walk_reactive`, `alert_aggression`
  - Lying → `cond_tired`
- **활용법**: 식사 행동 few-shot 예시 이미지 (meal_* 분류 보조)
- **라이선스**: 공개

### TigDog Dataset ⭐⭐
- **출처**: [CALVIN Lab](https://calvin-vision.net/datasets/tigdog/)
- **크기**: 600개 비디오 (tiger, horse, dog 혼합)
- **라벨**: walk, turn head, sitting, lying
- **활용법**: 기본 posture 전이학습 참고용

---

## 3. 포즈 추정 보조 (DeepLabCut/SuperAnimal 연계)

### SyDog-Video Dataset ⭐⭐⭐
- **출처**: arXiv 2108.00249 | [GitHub](https://github.com/mshooter/SyDogVideo_release)
- **크기**: 500개 비디오, 87,500 프레임
- **형식**: Unity3D 합성 영상
- **주석**: 2D keypoint 33개, bounding box, segmentation
- **행동**: walking, running, jumping, sitting, lying down
- **활용법**: SuperAnimal 포즈 추정 fine-tune 보조 데이터 (합성이라 실제 영상과 도메인 갭 존재)

### RGBD-Dog Dataset ⭐⭐⭐
- **출처**: CVPR 2020 | [GitHub](https://github.com/CAMERA-Bath/RGBD-Dog)
- **형식**: RGB-D (Kinect v2)
- **주석**: 3D 골격 + 포즈 제약
- **활용법**: `alert_limp` 감지 — 3D 포즈 기반 비정상 보행 패턴 분류
- **라이선스**: 공개

---

## 4. 센서/웨어러블 기반 (향후 Phase 4+ 고려)

### Movement Sensor Dataset ⭐⭐⭐
- **출처**: [Mendeley Data](https://data.mendeley.com/datasets/mpph6bmn7g/1)
- **크기**: 45마리 개
- **센서**: 6-DOF (collar + harness)
- **7가지 행동**: Sitting, Standing, Lying, Trotting, Walking, Playing, Sniffing
- **정확도**: Back harness 91%, Neck collar 75%
- **TailLog 매핑**: `walk_normal`, `play_normal`, `cond_tired` (lying)
- **활용법**: 웨어러블 센서 연동 시 참고 (Phase 4+)

### Inertial Data for Dog Behaviour (Kaggle) ⭐⭐⭐
- **출처**: [Kaggle](https://www.kaggle.com/datasets/benjamingray44/inertial-data-for-dog-behaviour-classification)
- **형식**: IMU (accelerometer + gyroscope)
- **최고 정확도**: CNN_LSTM ensemble 96.73%
- **활용법**: 실시간 행동 감지 모듈 참고 (Phase 4+)

---

## 5. TailLog 23개 Preset → 데이터셋 매핑 표

| preset_id | 최적 데이터셋 | 비고 |
|-----------|------------|------|
| `walk_normal` | Dog Behavior Monitoring (ziya07), DogMo | 기본 분류 |
| `walk_pulling` | — | **공개 데이터셋 없음** (직접 수집 필요) |
| `walk_reactive` | EgoPet, Roboflow Barking | 부분 매핑 |
| `walk_refuse` | — | **공개 데이터셋 없음** |
| `play_normal` | DECADE, Dog Behavior Monitoring | 기본 분류 |
| `play_overexcited` | CREMD (excitement), DogMo (running) | 간접 매핑 |
| `play_resource` | — | **공개 데이터셋 없음** |
| `cond_good` | DEBIw (Contentment), Dog Emotion v2 (happy) | ✅ 직접 매핑 |
| `cond_excited` | CREMD (excitement), Dog Emotion v2 | ✅ 직접 매핑 |
| `cond_tired` | Dog Emotion v2 (sad), DogMo (lying) | 간접 매핑 |
| `cond_anxious` | DEBIw (Anxiety), CREMD (fear) | ✅ 직접 매핑 |
| `alert_vomit` | — | **공개 데이터셋 없음** |
| `alert_diarrhea` | — | **공개 데이터셋 없음** |
| `alert_limp` | RGBD-Dog (비정상 보행), DogMo | 간접 매핑 |
| `alert_aggression` | DEBIw (Aggression), CREMD (anger) | ✅ 직접 매핑 |
| `alert_noeat` | — | **공개 데이터셋 없음** |
| `meal_full` | Roboflow (Eating) | 간접 매핑 |
| `meal_half` | — | **공개 데이터셋 없음** |
| `meal_refuse` | — | **공개 데이터셋 없음** |
| `social_good` | EgoPet (dog/person interaction) | 간접 매핑 |
| `social_human` | EgoPet (person interaction) | 간접 매핑 |
| `social_avoid` | — | **공개 데이터셋 없음** |
| `social_reactive` | DEBIw (Aggression + Anxiety) | 간접 매핑 |

> **공개 데이터셋 없음 분류 (7개)**: walk_pulling, walk_refuse, play_resource,
> alert_vomit, alert_diarrhea, alert_noeat, meal_half, meal_refuse, social_avoid
> → 이 라벨들은 TailLog 자체 수집·검수만이 유일한 확보 경로.

---

## 활용 로드맵

### Phase 1 (현재): 무시
- Vision LLM zero-shot 분류 중. 외부 데이터셋 통합할 타이밍 아님.
- cold start 100건 검수 완료가 우선.

### Phase 2 (~500건): Few-shot 예시 이미지 추가
```
1. DEBIw에서 cond_good/cond_anxious/alert_aggression 예시 5장씩 추출
2. Dog Emotion Dataset v2에서 감정 카테고리별 3장씩 추출
3. Dog Behavior Monitoring (ziya07)에서 walk/play 예시 추출
4. vision_classifier_prompt에 few-shot 이미지 첨부
   → 예상 정확도 향상: ~15-20%
```

### Phase 3 (~3,000건): 전이학습 검토
```
1. DECADE + SyDog-Video로 사전학습 → TailLog 라벨로 fine-tune
2. DEBIw + CREMD로 cond_*/alert_* 카테고리 강화
3. 공개 데이터셋으로 채울 수 없는 7개 라벨은 자체 수집 강화
```

### Phase 4+: 센서 연동 (선택)
```
Movement Sensor Dataset + Inertial Data → 웨어러블 연동 시 참고
```

---

## 빠른 다운로드 우선순위

```bash
# 1순위 — Hugging Face (가장 간단)
pip install datasets
from datasets import load_dataset
ds = load_dataset("Dewa/Dog_Emotion_Dataset_v2")

# 2순위 — Kaggle
kaggle datasets download ziya07/dog-behavior-monitoring-dataset
kaggle datasets download georgemartvel/dogflw
kaggle datasets download benjamingray44/inertial-data-for-dog-behaviour-classification

# 3순위 — GitHub
git clone https://github.com/ehsanik/dogTorch          # DECADE
git clone https://github.com/CAMERA-Bath/RGBD-Dog       # RGBD-Dog
git clone https://github.com/mshooter/SyDogVideo_release # SyDog-Video
```

---

## 참고 논문

| 논문 | 데이터셋 | arXiv/DOI |
|-----|---------|-----------|
| Who Let The Dogs Out? | DECADE | arXiv:1803.10827 |
| DogMo: Dog Motion Capture | DogMo | arXiv:2510.24117 |
| Animal Kingdom | Animal Kingdom | CVPR 2022 |
| EgoPet | EgoPet | arXiv:2404.09991 |
| RGBD-Dog | RGBD-Dog | CVPR 2020 |
| SyDog-Video | SyDog-Video | arXiv:2108.00249 |
| DogFLW | DogFLW | arXiv:2405.11501 |
| CREMD | CREMD | arXiv:2602.15349 |
| DEBIw | DEBIw | ACM ACI 2022 |
