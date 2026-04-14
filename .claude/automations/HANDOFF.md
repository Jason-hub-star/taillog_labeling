# Handoff — 현재 운영 상태

> 최신 업데이트: 2026-04-13

---

## 현재 상태

- Phase: **Phase 1 (Vision 라벨링 대기 중)**
- behavior_labels: 10건 (테스트용 수동 주입)
- auto_approved: 2건
- human_review 대기: 2건
- rejected: 6건
- synced (Supabase): 0건 / Cold Start 미해제 (목표 100건)
- pose_results: 0건 (Vision 분류 미실행 상태)
- category_suggestions: 4건

## 정상 작동 중

- Streamlit 검수 앱 (`scripts/review/review_app.py`) — T1~T9 전체 PASS
- DB 스키마 초기화 완료 (behavior_labels, pose_results, category_suggestions 등)
- SSOT 문서 12개 (`docs/ref/`) 최신화 완료
- 외부 few-shot 샘플: `data/external/few_shot_samples/dog_emotion_v2/` (30장)

## 다음 해야 할 일

1. **`nightly-vision-labeling.md`** 실행 — 기존 프레임 gemma4:26b Vision 분류 시작
2. Streamlit 검수 앱으로 human_review 100건 달성 → Cold Start 해제
3. auto_approved 라벨 Supabase sync (`daily-sync-monitor.md`)

## 수동 경계 (자동화 안 됨)

- `.env.local` Supabase 키 직접 관리
- YouTube URL 수집: `urls.txt`에 수동 추가
- Streamlit 검수: 주인님이 직접 A/R 판정

## 자동화 실행 순서

```
nightly-vision-labeling  (야간, 프레임 있을 때)
  → daily-quality-gate   (분류 후)
  → daily-sync-monitor   (auto_approved 발생 시)
```

## 주의사항

- **Cold Start 정책**: synced < 100건이면 QualityGate가 전체 human_review 강제
- **Streamlit 앱**: `review_status = 'human_review'` 기준 조회 (pending 아님)
- **SyncWriter 조건**: `auto_approved + confidence ≥ 0.85`만 Supabase 전송
- **ziya07/dogflw**: 이미지 없거나 라벨 없음 — 활용 불가 (검증 완료 2026-04-13)
- **미결 항목**: OD-01(dog_id 매핑), OD-04(Telegram 봇) → `docs/ref/OPEN-DECISIONS.md`
