# Pre-Dev Checklist — 개발 시작 전 완료 항목

> 파이프라인 개발(Phase 1) 시작 전 반드시 완료해야 하는 검증 작업.
> 완료 시 체크 후 DECISION-LOG에 기록.

---

## 상태

| 항목 | 상태 | 담당 |
|------|------|------|
| OD-07: SuperAnimal vs YOLOv8 비교 테스트 | 🔴 미완료 | 주인님 |
| OD-01: dog_id 매핑 전략 확정 | 🔴 미완료 | 주인님 |
| Supabase 연결 테스트 | 🔴 미완료 | - |
| Ollama + gemma4 모델 로딩 확인 | 🔴 미완료 | - |

---

## OD-07: 모델 비교 테스트

**실행 방법**:
```bash
# 1. 의존성 설치
pip install -r scripts/compare/requirements_compare.txt

# 2. URL 파일 준비 (소형견 + 대형견 + 다중 강아지 포함)
cat > urls.txt << EOF
# 소형견 (포메라니안/말티즈) - 필수
https://www.youtube.com/watch?v=...
# 대형견 (리트리버/허스키)
https://www.youtube.com/watch?v=...
# 다중 강아지
https://www.youtube.com/watch?v=...
EOF

# 3. 실행
bash scripts/compare/run_all.sh urls.txt
```

**결과 위치**: `data/exports/compare_report.md`

**판단 기준**:
- SuperAnimal 탐지율 15%p↑ → `docs/ref/MODEL-ROADMAP.md` Phase 1 모델 = SuperAnimal 확정
- 비슷하거나 YOLOv8↑ → MODEL-ROADMAP Phase 1 모델 재검토

**완료 후 할 일**:
1. `docs/ref/TECH-STACK-DECISIONS.md` A-01 확정 (PENDING 제거)
2. `docs/ref/OPEN-DECISIONS.md` OD-07 → Resolved 이동
3. `docs/status/DECISION-LOG.md` 기록

---

## OD-01: dog_id 매핑 전략

**옵션**:
- A: YouTube URL → CSV 파일로 anon_sid 매핑 (권장)
- B: 채널 1개 = anon dog 1개
- C: 수동 지정 (비추천)

**완료 후 할 일**:
1. `docs/ref/SUPABASE-SYNC-CONTRACT.md` 업데이트
2. OPEN-DECISIONS.md OD-01 → Resolved 이동

---

## Supabase 연결 테스트

```python
from supabase import create_client
client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
# behavior_logs 테이블 접근 확인
result = client.table("behavior_logs").select("id").limit(1).execute()
```

---

## Ollama + gemma4 모델 확인

```bash
ollama list  # gemma4-unsloth-e4b:latest, gemma4:26b-a4b-it-q4_K_M 있는지
ollama run gemma4-unsloth-e4b:latest "강아지가 줄을 당기고 있어. 행동 분류해줘."
```
