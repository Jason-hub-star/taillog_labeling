# Open Decisions — 미결 항목 추적

> 잠금되지 않은 결정들. 결정 완료 시 TECH-STACK-DECISIONS.md에 반영 후 여기서 resolved 처리.

---

## 미결 (주인님 확인 필요)

### OD-01: dog_id 매핑 전략
- **질문**: YouTube 영상 기반 라벨을 TailLog의 어떤 dog에 귀속시킬까?
- **옵션**:
  - A: YouTube URL → 사전 정의 `anonymous_sid` 매핑 파일 관리
  - B: YouTube 채널 1개 = anonymous dog 1개 자동 할당
  - C: 라벨링 시 `dog_id` 수동 지정
- **임시 처리**: `anonymous_sid='labeling_pipeline_v1'` 1개 dog에 모두 귀속
- **마감**: Phase 4 전
- **담당**: 주인님

### ~~OD-02: type_id INTEGER 매핑~~ ✅ RESOLVED
- **결정**: `behavior_logs.type_id` = FK 없는 순수 `INTEGER` (Column(Integer), 제약 없음)
- **매핑**: `PRESET_TO_TYPE_ID` 딕셔너리 (1~21 순서 매핑) 그대로 사용
- **위치**: `SUPABASE-SYNC-CONTRACT.md` 임시 매핑 → **확정 매핑으로 승격**
- **해결일**: 2026-04-11

### OD-03: 모바일 앱 플랫폼 선택
- **질문**: React Native vs Flutter?
- **영향**: sync API 인터페이스 설계 (REST 기준이므로 플랫폼 무관)
- **현재 조치**: API 스펙만 설계, 구현 보류
- **마감**: Phase 4 후 (파이프라인과 무관)
- **담당**: 주인님

### OD-04: Telegram 알림 봇 설정
- **질문**: watchdog 알림용 Telegram 봇 토큰 및 채팅 ID
- **임시 처리**: 로컬 파일 로그 (`data/exports/sync_logs/watchdog.log`)
- **마감**: Phase 1 완료 후
- **담당**: 주인님 (봇 토큰 제공)

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

### OD-07: SuperAnimal vs YOLOv8-pose 선택 🔴 개발 시작 전 필수
- **질문**: 포즈 추출 모델로 YOLOv8n-pose와 SuperAnimal 중 어떤 것을 쓸 것인가?
- **⚠️ 개발 시작 전에 반드시 비교 테스트 완료 후 결정해야 함**
  - 결정 이후에 교체하면 keypoint 형식, 파이프라인 전체 수정 필요
  - 영상 2~3개 + 30분이면 결론 가능
- **배경**:
  - YOLOv8n-pose: 강아지 전용 mAP 미공개, 인간 COCO 기준 mAP 50.0
  - SuperAnimal-Quadruped: 강아지 포함 Zero-shot mAP **84.6** (Nature Comm. 2024)
  - 점수 기준이 달라 단순 비교 불가 → 실제 강아지 영상으로 직접 확인 필요
- **비교 방법**:
  1. 강아지 영상 2~3개 준비 (소형견 포함)
  2. YOLOv8n-pose 실행 → keypoint 시각화 저장
  3. SuperAnimal (HuggingFace 경량 버전) 실행 → keypoint 시각화 저장
  4. 탐지율, keypoint 품질, 속도 비교 후 결정
- **판단 기준**:
  - SuperAnimal 탐지율이 유의미하게 높으면 → SuperAnimal 채택 (파이프라인 설계 변경)
  - 비슷하면 → YOLOv8 유지 (설정 간단, 현재 스택 호환)
- **마감**: **개발 시작 전 (Phase 0)**
- **담당**: 주인님 (영상 준비) + Claude (테스트 스크립트 작성)

---

## 해결됨 (Resolved)

| ID | 결정 | 날짜 |
|----|------|------|
| — | — | — |

> 해결 시: TECH-STACK-DECISIONS.md 업데이트 → DECISION-LOG.md 기록 → 여기서 Resolved 이동
