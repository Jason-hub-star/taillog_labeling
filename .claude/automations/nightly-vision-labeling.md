# 야간 Vision 라벨링 자동 실행

> 기존 프레임(data/training/frames/)에 대해 gemma4:26b Vision LLM으로 행동 분류 실행.
> 분류 안 된 프레임을 탐지하여 순차 처리 후 SQLite에 저장한다.
> 예상 소요: 545프레임 기준 약 11시간 (프레임당 평균 74초)

**목표**: 라벨 데이터 축적 → cold start 100건 검수 → Supabase DB 적재 (모바일 앱은 미개발, DB만 존재)

---

## Phase 1 완료 기준 (이 자동화의 종료 조건)

| 기준 | 목표값 | 확인 쿼리 |
|------|--------|-----------|
| behavior_labels 생성 | 545건 이상 | `SELECT COUNT(*) FROM behavior_labels` |
| unknown 비율 | < 20% | `WHERE preset_id='unknown'` |
| 평균 신뢰도 | > 0.70 | `AVG(llm_confidence)` |
| cold start 검수 | 100건 human_review | `WHERE review_status='human_review'` |
| Supabase 적재 | 1건 이상 | behavior_logs 테이블 확인 |

> ABC 라벨링은 Phase 1 제외. Phase 2(5프레임 콜라주) 이후 도입.
> Critic은 Phase 2 shadow mode 시작. 현재 미실행.

---

## 1. 사전 확인

### 1-1. 환경 활성화
```bash
cd /Users/family/jason/taillog_labeling
source venv/bin/activate
```

### 1-2. Ollama 및 모델 확인
```bash
ollama list | grep "gemma4:26b"
```
`gemma4:26b-a4b-it-q4_K_M` 없으면 즉시 중단.

### 1-3. DB 현황 조회
```bash
python3 - <<'EOF'
from src.core.database import get_db
db = get_db()

frames = db.execute("SELECT COUNT(*) as cnt FROM pose_results WHERE frame_path IS NOT NULL")
labeled = db.execute("SELECT COUNT(*) as cnt FROM behavior_labels")
pending = db.execute("""
    SELECT COUNT(*) as cnt FROM pose_results pr
    WHERE pr.frame_path IS NOT NULL
    AND NOT EXISTS (
        SELECT 1 FROM behavior_labels bl
        WHERE bl.run_id = pr.run_id AND bl.frame_id = pr.frame_id
    )
""")
synced = db.execute("SELECT COUNT(*) as cnt FROM behavior_labels WHERE synced=1", ())
print(f"포즈 프레임: {frames[0]['cnt']}개")
print(f"분류 완료: {labeled[0]['cnt']}개")
print(f"분류 대기: {pending[0]['cnt']}개")
print(f"Supabase 적재: {synced[0]['cnt']}개")
EOF
```

"분류 대기"가 0이면 → 섹션 4(완료 후 검증)로 바로 이동.

---

## 2. Vision 분류 실행

`scripts/classify_frames.py` 없으면 아래 코드로 생성 후 실행:

```python
"""
기존 프레임 전체 Vision LLM 분류 스크립트
실행: python3 scripts/classify_frames.py
"""
import sys, time, uuid
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(".env.local")

from src.core.database import get_db, init_db
from src.core.llm import get_ollama_client
from src.core.image_utils import load_frame_image, image_to_base64
from src.prompts.vision_classifier_prompt import build_vision_classifier_prompt
from src.utils.label_constants import IS_PROBLEMATIC
from src.utils.config import Config

MODEL = Config.BEHAVIOR_CLASSIFIER_MODEL  # gemma4:26b-a4b-it-q4_K_M
CONSISTENCY_SCORE = 0.5  # Phase 2에서 인접 프레임 비교로 대체

def main():
    init_db()
    db = get_db()
    llm = get_ollama_client()
    prompt = build_vision_classifier_prompt()

    pending = db.execute("""
        SELECT pr.run_id, pr.frame_id, pr.frame_path, pr.confidence as kp_quality
        FROM pose_results pr
        WHERE pr.frame_path IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM behavior_labels bl
            WHERE bl.run_id = pr.run_id AND bl.frame_id = pr.frame_id
        )
        ORDER BY pr.run_id, pr.frame_id
    """)

    total = len(pending)
    if total == 0:
        print("분류 대기 프레임 없음. 종료.")
        return

    print(f"분류 대기: {total}개 | 모델: {MODEL}")
    print(f"예상: {total * 74 // 60}~{total * 103 // 60}분")
    print("=" * 60)

    success, failed, skipped = 0, 0, 0
    start_all = time.time()

    for i, row in enumerate(pending, 1):
        frame_path = Path(row["frame_path"])
        if not frame_path.exists():
            skipped += 1
            continue

        t0 = time.time()
        try:
            image_bytes = load_frame_image(frame_path)
            if not image_bytes:
                skipped += 1
                continue

            image_b64 = image_to_base64(image_bytes)
            resp = llm.generate_with_image(
                model=MODEL, prompt=prompt,
                image_base64=image_b64, temperature=0.3,
            )
            elapsed = time.time() - t0
            r = llm.parse_json_response(resp["content"])

            preset_id = r.get("preset_id", "unknown")
            category  = r.get("category", "unknown")
            confidence = float(r.get("confidence", 0.3))
            reasoning  = r.get("reasoning", "")

            _is_prob = IS_PROBLEMATIC.get(preset_id)
            is_problematic = None if _is_prob is None else int(_is_prob)

            # cold start: review_status는 quality_gate가 일괄 설정 (섹션 3 참조)
            db.insert("""
                INSERT OR IGNORE INTO behavior_labels
                (id, run_id, frame_id, preset_id, category, label,
                 llm_confidence, consistency_score, keypoint_quality, confidence,
                 is_problematic, reviewer_note, labeler_model, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()), row["run_id"], row["frame_id"],
                preset_id, category, preset_id,
                confidence, CONSISTENCY_SCORE, row["kp_quality"], confidence,
                is_problematic,
                f"[AI] {reasoning}" if reasoning else None,
                MODEL, datetime.now().isoformat(),
            ))

            eta = (total - i) * elapsed
            print(f"[{i}/{total}] {frame_path.name} → {preset_id} | {confidence:.2f} | {elapsed:.1f}s | ETA {eta/60:.0f}분")
            success += 1

        except Exception as e:
            print(f"[{i}/{total}] ERROR {frame_path.name}: {e}")
            failed += 1

    elapsed_total = time.time() - start_all
    print("\n" + "=" * 60)
    print(f"완료: {success}성공 / {failed}실패 / {skipped}스킵 | {elapsed_total/3600:.1f}시간")

if __name__ == "__main__":
    main()
```

실행:
```bash
mkdir -p logs
python3 scripts/classify_frames.py 2>&1 | tee logs/vision-labeling-$(date +%Y%m%d-%H%M%S).log
```

중단 후 재실행 안전 (`INSERT OR IGNORE` 적용).

---

## 3. Quality Gate — review_status 일괄 설정

분류 완료 후 실행. `QualityGate.batch_process()`가 cold start 정책을 자동 적용한다.

```bash
python3 - <<'EOF'
import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv(".env.local")

from src.agents.quality_gate import QualityGate
from src.core.database import get_db

db = get_db()

# cold start 현황 확인
synced_count = db.execute_one(
    "SELECT COUNT(*) as cnt FROM behavior_labels WHERE synced = 1", ()
)["cnt"]
cold_start = synced_count < 100

print(f"Cold Start: {'활성' if cold_start else '비활성'} (Supabase 적재: {synced_count}건)")
print("QualityGate.batch_process() 실행 중...")

# QualityGate 클래스 사용 (unknown→rejected, cold_start→human_review 자동 처리)
# 테스트 시 cold_start 비활성화: COLD_START_LIMIT=0 python3 ...
qg = QualityGate()
processed = qg.batch_process(run_id=None, dry_run=False)

# 결과 요약
from collections import Counter
rows = db.execute(
    "SELECT review_status FROM behavior_labels WHERE review_status IS NOT NULL", ()
)
counts = Counter(r["review_status"] for r in rows)
print(f"처리: {processed}건")
print(f"  human_review : {counts.get('human_review', 0)}건 (Streamlit 검수 필요)")
print(f"  auto_approved: {counts.get('auto_approved', 0)}건 (sync 대기)")
print(f"  rejected     : {counts.get('rejected', 0)}건 (제외)")
EOF
```

> **Cold Start 활성 시**: 모든 라벨이 `human_review` → 섹션 4 Streamlit 검수 필수.
> **Cold Start 비활성 시** (100건 이상 적재 후): confidence ≥ 0.85 → `auto_approved`, unknown → `rejected` 자동 처리.
> **테스트 시 cold start 비활성화**: `COLD_START_LIMIT=0 python3 -c "..."`

---

## 4. 완료 후 검증 및 통계

```bash
python3 - <<'EOF'
from src.core.database import get_db
db = get_db()

# 전체 요약
total  = db.execute_one("SELECT COUNT(*) as cnt FROM behavior_labels", ())["cnt"]
hr     = db.execute_one("SELECT COUNT(*) as cnt FROM behavior_labels WHERE review_status='human_review'", ())["cnt"]
auto   = db.execute_one("SELECT COUNT(*) as cnt FROM behavior_labels WHERE review_status='auto_approved'", ())["cnt"]
rej    = db.execute_one("SELECT COUNT(*) as cnt FROM behavior_labels WHERE review_status='rejected'", ())["cnt"]
unk    = db.execute_one("SELECT COUNT(*) as cnt FROM behavior_labels WHERE preset_id='unknown'", ())["cnt"]
avg_c  = db.execute_one("SELECT ROUND(AVG(llm_confidence),2) as v FROM behavior_labels", ())["v"]

print(f"\n{'='*45}")
print(f"총 라벨        : {total}건")
print(f"human_review   : {hr}건  ← Streamlit 검수 필요")
print(f"auto_approved  : {auto}건")
print(f"rejected       : {rej}건")
print(f"unknown 비율   : {unk/total*100:.1f}% ({unk}건)")
print(f"평균 신뢰도    : {avg_c}")
print(f"{'='*45}")

# preset_id별 분포
print("\n[카테고리별 분포]")
rows = db.execute("""
    SELECT preset_id, COUNT(*) as cnt, ROUND(AVG(llm_confidence),2) as avg_c
    FROM behavior_labels GROUP BY preset_id ORDER BY cnt DESC
""", ())
for r in rows:
    print(f"  {r['preset_id']:<25} {r['cnt']:>5}건  신뢰도 {r['avg_c']}")
EOF
```

### 성공 기준 (Phase 1 완료 기준과 동일)
- `total` ≥ 545
- `unknown` 비율 < 20%
- `avg_c` > 0.70
- 로그의 `failed` < 10

### 이상 감지
| 상황 | 원인 | 대응 |
|------|------|------|
| ERROR 반복 | Ollama 다운 | `ollama serve` 재시작 후 재실행 |
| unknown > 20% | 강아지 없는 프레임 多 | 정상 가능성 있음, 영상 내용 확인 |
| 진행 멈춤 | LLM 응답 없음 | Ctrl+C 후 재실행 (중복 없음) |
| avg_c < 0.65 | 모델 품질 문제 | Streamlit 샘플 검수 후 판단 |

---

## 5. 다음 단계 (아침에 주인님이 직접)

### Step A: Streamlit 검수 (cold start 100건)
```bash
streamlit run scripts/review/review_app.py
```
- A키: 맞음 / R키: 틀림 / →←: 이동
- 목표: 100건 검수 완료 (약 2~3시간)
- 완료 후 → cold start 해제 → auto_approved 활성화

### Step B: Supabase DB 적재 (검수 후)
```bash
# sync_writer 실행 (auto_approved + confidence≥0.85 + preset_id!='unknown')
python3 - <<'EOF'
import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv(".env.local")

from src.agents.sync_writer import SyncWriter
sw = SyncWriter()
success, failed = sw.batch_sync(run_id=None, dry_run=False)
print(f"Supabase 적재: {success}건 성공 / {failed}건 실패")
EOF
```
> Supabase는 현재 데이터 저장 목적 (모바일 앱 미개발).
> 적재 성공 여부만 확인. TailLog 앱 연동 검증은 Phase 4 이후.

---

## 6. 알려진 한계

| # | 항목 | 내용 |
|---|------|------|
| 1 | 처리 속도 | 평균 74초/프레임. M5 32GB + Ollama 0.20 MLX 최적화 상태 |
| 2 | consistency_score | 0.5 고정. Phase 2 5프레임 콜라주 도입 시 실제 계산으로 교체 |
| 3 | ABC 라벨링 | Phase 1 제외. antecedent/behavior/consequence 미생성 |
| 4 | Supabase sync | 앱 미개발 — 데이터 축적 목적. sync_writer.run_batch() 미구현 시 수동 처리 |
| 5 | cold start 100건 | quality_gate가 자동 설정. Streamlit 검수 전까지 auto_approved 없음 |
