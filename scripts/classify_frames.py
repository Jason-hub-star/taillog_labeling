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

            preset_id  = r.get("preset_id", "unknown")
            category   = r.get("category", "unknown")
            confidence = float(r.get("confidence", 0.3))
            reasoning  = r.get("reasoning", "")

            _is_prob = IS_PROBLEMATIC.get(preset_id)
            is_problematic = None if _is_prob is None else int(_is_prob)

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
