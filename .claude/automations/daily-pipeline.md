# Daily Pipeline

> YouTube 수집 → 포즈 추출 → Vision 행동 분류
> 새 영상이 생기면 실행. 야간 자동 분류는 `nightly-vision-labeling.md` 참조.

---

## 목적
YouTube 강아지 영상에서 행동 라벨을 자동 수집한다.

## 실행 순서

1. **collector**: YouTube URL로 영상 다운로드
   - 품질 기준: 480p 이상, 10초~10분, 강아지 화면 5% 이상
   - `urls.txt`에 URL 추가 후 실행

2. **pose_extractor**: SuperAnimal-Quadruped로 1FPS 키포인트 추출
   - `.venv_dlc` 격리 환경에서 subprocess 실행
   - 탐지 신뢰도 < 0.5 프레임 필터링
   - 프레임 이미지 `data/training/frames/`에 저장

3. **behavior_classifier**: gemma4:26b Vision LLM으로 행동 분류
   - 프레임 이미지 직접 입력 (keypoints 텍스트 방식 구형, 미사용)
   - 23개 preset_id 분류 → behavior_labels DB 저장
   - Ollama 0.20.2 MLX 백엔드 (M5 32GB 자동 활성화)

> ⚠️ **ABC 라벨링 Phase 1 제외**
> antecedent / behavior / consequence 생성은 Phase 2 이후 (5프레임 콜라주 도입 시).

## 실행 명령
```bash
cd /Users/family/jason/taillog_labeling
source venv/bin/activate
python3 src/pipelines/run.py --url <YouTube_URL>
# 또는
python3 src/pipelines/run.py --urls-file urls.txt
```

## 성공 조건
- `labeling_runs.status = 'labeled'` 건수 > 0
- `behavior_labels` 신규 생성 건수 > 0
- 오류 없이 전 단계 완료

## 실패 조건
- collector: 0건 다운로드 → watchdog 통지
- pose_extractor: 탐지율 < 10% → discard (watchdog 없음)
- LLM: 연속 10회 parse 실패 → HALT

## 완료 후
1. `nightly-vision-labeling.md` 섹션 3 (Quality Gate) 실행
2. `streamlit run scripts/review/review_app.py` 로 검수
3. cold start 100건 완료 후 → Supabase sync

## Phase별 분류 전략
| Phase | 건수 | 방식 |
|-------|------|------|
| Phase 1 (현재) | ~100건 | 단일 프레임 zero-shot, 전수 검수 |
| Phase 2 | ~500건 | 5프레임 콜라주 + few-shot |
| Phase 3 | ~3,000건 | 파인튜닝 검토 |

## 참조
- `docs/ref/AGENT-OPERATING-MODEL.md`
- `docs/ref/CONFIDENCE-THRESHOLD-POLICY.md`
- `docs/ref/SUPABASE-SYNC-CONTRACT.md`
- `.claude/automations/nightly-vision-labeling.md` — 기존 프레임 야간 분류
