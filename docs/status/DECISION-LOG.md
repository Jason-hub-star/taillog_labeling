# Decision Log

> 주요 결정 기록. 새 결정 시 상단에 추가.

---

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
