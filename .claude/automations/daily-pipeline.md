# Daily Pipeline

> YouTube 수집 → 포즈 추출 → 행동 분류 → ABC 라벨링
> 매일 1회 실행. 이후 daily-quality-gate.md 실행.

---

## 목적
YouTube 일상 강아지 영상에서 행동 라벨을 자동 수집한다.

## 실행 순서
1. **collector**: YouTube 검색어로 영상 5~50건 다운로드
   - 검색어: `docs/ref/YOUTUBE-SOURCE-POLICY.md` 참조
   - 품질 기준: 480p 이상, 10초~10분, 강아지 화면 5% 이상
2. **pose_extractor**: YOLOv8n-pose로 1FPS 키포인트 추출
   - 탐지 신뢰도 < 0.5 프레임 필터링
3. **behavior_classifier**: gemma4-unsloth-e4b로 행동 1차 분류
   - 6 categories × 21 labels (LABEL-SCHEMA.md 참조)
4. **abc_labeler**: ABC 구조화 + intensity 추정

## 성공 조건
- `labeling_runs.status = 'labeled'` 건수 > 0
- 오류 없이 전 단계 완료

## 실패 조건
- collector: 0건 다운로드 → watchdog 통지
- pose_extractor: 탐지율 < 10% → watchdog 경고
- LLM: 연속 10회 parse 실패 → HALT

## 완료 후
- `daily-quality-gate.md` 자동 실행

## 참조
- `docs/ref/AGENT-OPERATING-MODEL.md`
- `docs/ref/YOUTUBE-SOURCE-POLICY.md`
- `docs/ref/FAILURE-HANDLING.md`
