# Open Decisions — 미결 항목 추적

> 잠금되지 않은 결정들. 결정 완료 시 TECH-STACK-DECISIONS.md에 반영 후 여기서 resolved 처리.

---

## 미결 (주인님 확인 필요)

### ~~OD-01: dog_id 매핑 전략~~ ✅ RESOLVED
- **결정**: anonymous dog UUID `612a3d4f-6fc1-406e-8a15-5430a096eee2` 사용 (dogs 테이블에 생성)
- **해결일**: 2026-04-11

### ~~OD-02: type_id INTEGER 매핑~~ ✅ RESOLVED
- **결정**: `type_id` 컬럼 없음. 실제 컬럼은 `behavior_type TEXT`. `preset_id` 그대로 사용.
- **해결일**: 2026-04-11 (실제 Supabase 스키마 직접 확인)

### OD-03: 모바일 앱 플랫폼 선택
- **질문**: React Native vs Flutter?
- **영향**: sync API 인터페이스 설계 (REST 기준이므로 플랫폼 무관)
- **현재 조치**: API 스펙만 설계, 구현 보류
- **마감**: Phase 4 후 (파이프라인과 무관)
- **담당**: 주인님

### ~~OD-04: Telegram 알림 봇 설정~~ ✅ RESOLVED
- **결정**: `@TailLog_Watchdog_bot` 생성, token + chat_id `.env.local` 등록 완료
- **해결일**: 2026-04-11

### OD-05: Cohen's Kappa 목표치
- **질문**: human_review 검수자 간 일관성 목표 설정
- **잠정 목표**: ≥ 0.80 (excellent)
- **측정 시점**: Phase 3 (500건 누적 후)
- **마감**: Phase 3

### OD-06: Supabase 비용 한도
- **질문**: write 비용 및 월간 예산 한도 설정
- **무료 플랜 확인됨**:
  - DB 용량: **500MB** (라벨 10만 건 수준)
  - 스토리지: 1GB
  - ⚠️ **7일 미사용 시 자동 일시중지** — 파이프라인 장기 중단 시 수동 재개 필요
  - 에지 함수: 50만 건/월
- **현재 판단**: Phase 1~2는 무료 플랜으로 충분
- **Pro 전환 시점**: 라벨 누적 데이터가 400MB 초과하거나 24/7 운영 필요 시
- **마감**: Phase 3

### ~~OD-07: SuperAnimal vs YOLOv8-pose 선택~~ ✅ RESOLVED
- **결정**: **SuperAnimal 채택** — YOLOv8 평균 탐지율 18.3%로 실용 수준 미달
- **근거**: 강아지 영상 5개(60프레임씩) YOLOv8 테스트 결과
  - 포메라니안 8.3%, 홈캠 6.7%, 강아지 두마리 0.0% → 소형견/다중개 탐지 불가
  - SuperAnimal-Quadruped Zero-shot mAP 84.6 (Nature Comm. 2024) 기준 우월 예상
  - deeplabcut Python 3.14 미호환 → 직접 비교 불가 (단, YOLOv8 탐지율 기준으로 판단 충분)
- **후속 조치**: deeplabcut 설치용 Python 3.10/3.11 가상환경 구성 필요 (Phase 1 전)
- **해결일**: 2026-04-11

---

## 해결됨 (Resolved)

| ID | 결정 | 날짜 |
|----|------|------|
| OD-01 | anonymous dog UUID `612a3d4f-6fc1-406e-8a15-5430a096eee2` 사용 | 2026-04-11 |
| OD-02 | `type_id` 없음, `behavior_type TEXT` 사용 | 2026-04-11 |
| OD-04 | Telegram 봇 `@TailLog_Watchdog_bot` 설정 완료 | 2026-04-11 |
| OD-07 | SuperAnimal 채택 (YOLOv8 탐지율 18.3% 실용 미달) | 2026-04-11 |

> 해결 시: TECH-STACK-DECISIONS.md 업데이트 → DECISION-LOG.md 기록 → 여기서 Resolved 이동
