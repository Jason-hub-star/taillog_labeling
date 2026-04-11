# Handoff — 현재 운영 상태

> 최신 업데이트: 2026-04-11 (초기 설정)

---

## 현재 상태
- Phase: **Phase 1 (환경 초기화 중)**
- 누적 라벨 수: 0건
- auto_approved: 0건
- human_review 대기: 0건

## 정상 작동 중
- 폴더 구조 생성 완료
- 문서 초기화 완료 (docs/ref/ SSOT 문서 10개)
- Supabase 대상: `https://qufjlveukaoiokhpkhwj.supabase.co`

## 수동 경계 (자동화 안 됨)
- `.env.local` Supabase 키 직접 입력 필요
- Ollama 모델 다운로드 상태 수동 확인 (`ollama list`)
- OD-01: dog_id 매핑 전략 결정 (주인님)
- OD-02: type_id INTEGER 매핑 확인 (TailLog DB 조회)
- OD-04: Telegram 봇 토큰 설정 (주인님)

## 실패 semantics
- 아직 파이프라인 미실행, 실패 기록 없음

## 다음 할 일
1. `scripts/setup/bootstrap.sh` 실행 (모델 다운로드)
2. `.env.local` 작성 (Supabase 키, Ollama URL)
3. SQLite DB init (`python -c "from src.core.database import init_db; init_db()"`)
4. 샘플 1건 드라이런
