"""
TailLog 라벨 검수 앱 v2
실행: streamlit run scripts/review/review_app.py

키보드 단축키:
  A       → ✅ 맞음
  R       → ❌ 틀림
  →       → 다음 프레임
  ←       → 이전 프레임
"""

import sys
import uuid
import sqlite3
from pathlib import Path
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.utils.label_constants import (
    NORMAL_LABELS, LABEL_TO_KO, IS_PROBLEMATIC, LABEL_TO_CATEGORY,
    PROBLEM_REVIEW_GROUPS, NORMAL_CUES, ALL_LABELS,
)

# ── 상수 ───────────────────────────────────────────────────────────────────

DB_PATH = ROOT / "data" / "databases" / "labeling.db"
FRAMES_DIR = ROOT / "data" / "training" / "frames"

LABEL_KO = LABEL_TO_KO
PROBLEM_GROUPS = PROBLEM_REVIEW_GROUPS  # 문제행동만 포함


# ── DB 헬퍼 ────────────────────────────────────────────────────────────────

def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def load_labels(filter_mode: str) -> list[dict]:
    if not DB_PATH.exists():
        return []
    with get_conn() as conn:
        base = """
            SELECT bl.id, bl.run_id, bl.frame_id, bl.preset_id, bl.category,
                   bl.confidence, bl.is_problematic, bl.review_status,
                   bl.reviewer_note, bl.created_at, lr.title
            FROM behavior_labels bl
            LEFT JOIN labeling_runs lr ON bl.run_id = lr.id
        """
        where = {
            "검수 대기": "WHERE bl.review_status = 'pending'",
            "정상행동":  "WHERE bl.is_problematic = 0",
            "문제행동":  "WHERE bl.is_problematic = 1",
            "미분류":    "WHERE bl.preset_id = 'unknown'",
        }.get(filter_mode, "")
        rows = conn.execute(f"{base} {where} ORDER BY bl.created_at DESC").fetchall()
        return [dict(r) for r in rows]


def load_stats() -> dict:
    if not DB_PATH.exists():
        return dict(total=0, pending=0, reviewed=0, normal=0, problem=0, unknown=0, suggestions=0)
    with get_conn() as conn:
        def n(where=""):
            r = conn.execute(f"SELECT COUNT(*) FROM behavior_labels {where}").fetchone()
            return r[0] if r else 0
        def ns():
            r = conn.execute("SELECT COUNT(*) FROM category_suggestions").fetchone()
            return r[0] if r else 0
        return dict(
            total=n(), pending=n("WHERE review_status='pending'"),
            reviewed=n("WHERE review_status IN ('auto_approved','human_review')"),
            normal=n("WHERE is_problematic=0"), problem=n("WHERE is_problematic=1"),
            unknown=n("WHERE preset_id='unknown'"), suggestions=ns(),
        )


def save_label(label_id: str, preset_id: str, status: str, note: str | None):
    is_prob = IS_PROBLEMATIC.get(preset_id)
    cat = LABEL_TO_CATEGORY.get(preset_id, preset_id)  # cond_* → "condition" 올바르게 매핑
    with get_conn() as conn:
        conn.execute("""
            UPDATE behavior_labels
               SET preset_id=?, category=?, is_problematic=?,
                   review_status=?, reviewer_note=?, updated_at=?
             WHERE id=?
        """, (preset_id, cat, is_prob, status, note, datetime.now().isoformat(), label_id))


def save_suggestion(label_id: str, frame_id: int, run_id: str, description: str, name: str):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO category_suggestions (id, label_id, frame_id, run_id, description, suggested_name)
            VALUES (?,?,?,?,?,?)
        """, (str(uuid.uuid4()), label_id, frame_id, run_id, description, name or None))
        # 해당 라벨은 unknown + 메모 처리
        conn.execute("""
            UPDATE behavior_labels
               SET preset_id='unknown', category='unknown', is_problematic=NULL,
                   review_status='human_review', reviewer_note=?, updated_at=?
             WHERE id=?
        """, (f"[새 행동 제안] {name}: {description}", datetime.now().isoformat(), label_id))


def get_frame_path(frame_id: int) -> Path | None:
    p = FRAMES_DIR / f"{frame_id:06d}.jpg"
    if p.exists():
        return p
    for c in FRAMES_DIR.rglob(f"{frame_id:06d}.jpg"):
        return c
    return None


# ── 키보드 단축키 JS ───────────────────────────────────────────────────────

KEYBOARD_JS = """
<script>
(function() {
  function clickByText(text) {
    const btns = window.parent.document.querySelectorAll('button');
    for (const b of btns) {
      if (!b.disabled && b.textContent.trim().includes(text)) {
        b.click(); return true;
      }
    }
    return false;
  }
  window.parent.document.addEventListener('keydown', function(e) {
    const tag = (e.target.tagName || '').toLowerCase();
    if (['input','textarea','select'].includes(tag) || e.target.isContentEditable) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    switch(e.key) {
      case 'a': case 'A': e.preventDefault(); clickByText('맞음'); break;
      case 'r': case 'R': e.preventDefault(); clickByText('틀림'); break;
      case 'ArrowRight':  e.preventDefault(); clickByText('다음 ▶'); break;
      case 'ArrowLeft':   e.preventDefault(); clickByText('◀ 이전'); break;
    }
  });
})();
</script>
"""


# ── 카테고리 선택 UI ───────────────────────────────────────────────────────

def render_category_picker(row: dict):
    """정상 / 문제행동 탭 + 새 행동 제안"""
    label_id = row["id"]
    current = row["preset_id"]

    tab_normal, tab_problem, tab_suggest = st.tabs(["✅ 정상행동", "⚠️ 문제행동", "💡 새 행동 제안"])

    # ── 정상행동 탭 ──────────────────────────────────────────────────────
    with tab_normal:
        st.caption("클릭하면 바로 저장돼요.")
        for label in NORMAL_LABELS:
            ko = LABEL_TO_KO[label]
            cue = NORMAL_CUES.get(label, "")
            is_cur = label == current
            col_btn, col_desc = st.columns([2, 3])
            with col_btn:
                if st.button(
                    f"{'✓ ' if is_cur else ''}{ko}",
                    key=f"n_{label}",
                    type="primary" if is_cur else "secondary",
                    use_container_width=True,
                ):
                    save_label(label_id, label, "human_review", None)
                    _advance()
                    st.rerun()
            with col_desc:
                st.caption(cue)

    # ── 문제행동 탭 ──────────────────────────────────────────────────────
    with tab_problem:
        st.caption("그룹 탭에서 선택하세요.")
        group_tabs = st.tabs(list(PROBLEM_GROUPS.keys()))
        for gtab, (group_name, labels) in zip(group_tabs, PROBLEM_GROUPS.items()):
            with gtab:
                for label in labels:
                    is_cur = label == current
                    if st.button(
                        f"{'✓ ' if is_cur else ''}{label} — {LABEL_KO[label]}",
                        key=f"p_{label}",
                        type="primary" if is_cur else "secondary",
                        use_container_width=True,
                    ):
                        save_label(label_id, label, "human_review", None)
                        _advance()
                        st.rerun()

    # ── 새 행동 제안 탭 ──────────────────────────────────────────────────
    with tab_suggest:
        st.caption(f"23개 카테고리에 없는 행동이 보일 때 사용해요. 10건 이상 쌓이면 새 카테고리 추가를 검토해요.")
        sug_name = st.text_input("제안 카테고리명 (영문, 예: normal_yawn)", key="sug_name")
        sug_desc = st.text_area(
            "행동 설명",
            placeholder="예: 강아지가 하품하며 기지개를 켜는 행동. 귀가 뒤로 젖혀지고 입이 크게 벌어짐.",
            key="sug_desc",
            height=100,
        )
        if st.button("제안 저장", key="sug_save", use_container_width=True, type="primary"):
            if sug_desc.strip():
                save_suggestion(label_id, row["frame_id"], row["run_id"], sug_desc.strip(), sug_name.strip())
                st.success("제안이 저장됐어요. 라벨은 unknown으로 처리됩니다.")
                _advance()
                st.rerun()
            else:
                st.error("행동 설명을 입력해 주세요.")


def _advance():
    """다음 프레임으로 자동 이동"""
    total = st.session_state.get("_total", 1)
    idx = st.session_state.get("idx", 0)
    if idx < total - 1:
        st.session_state.idx = idx + 1


# ── 앱 메인 ────────────────────────────────────────────────────────────────

st.set_page_config(page_title="TailLog 검수", page_icon="🐾", layout="wide")
st.title("🐾 TailLog 라벨 검수")
st.caption("단축키: **A** 맞음 · **R** 틀림 · **← →** 이전/다음")

# 사이드바
with st.sidebar:
    st.header("통계")
    stats = load_stats()
    if stats["total"] == 0:
        st.info("라벨 없음. 파이프라인을 실행해 주세요.")
    else:
        st.metric("전체", stats["total"])
        c1, c2 = st.columns(2)
        c1.metric("검수 대기", stats["pending"])
        c2.metric("검수 완료", stats["reviewed"])
        st.divider()
        total_n = stats["total"]
        st.metric("✅ 정상", f"{stats['normal']}건 ({stats['normal']/total_n*100:.0f}%)")
        st.metric("⚠️ 문제", f"{stats['problem']}건 ({stats['problem']/total_n*100:.0f}%)")
        st.metric("❓ 미분류", stats["unknown"])
        if stats["suggestions"]:
            st.metric("💡 새 행동 제안", stats["suggestions"], help="카테고리 없는 행동 제안 건수")
    st.divider()
    if st.button("새로고침", use_container_width=True):
        st.rerun()

# 필터
filter_mode = st.radio(
    "필터",
    ["전체", "검수 대기", "정상행동", "문제행동", "미분류"],
    horizontal=True,
)

labels = load_labels(filter_mode)

if not labels:
    msg = "DB가 없어요. 파이프라인을 먼저 실행해 주세요." if not DB_PATH.exists() else "해당 조건의 라벨이 없어요."
    st.info(msg)
    st.stop()

total = len(labels)
st.session_state["_total"] = total

if "idx" not in st.session_state:
    st.session_state.idx = 0
st.session_state.idx = max(0, min(st.session_state.idx, total - 1))

# 네비게이션
c_prev, c_info, c_next = st.columns([1, 4, 1])
with c_prev:
    if st.button("◀ 이전", use_container_width=True, disabled=st.session_state.idx == 0):
        st.session_state.idx -= 1
        st.rerun()
with c_info:
    pct = (st.session_state.idx + 1) / total * 100
    st.markdown(
        f"<div style='text-align:center;padding:5px 0'>"
        f"<b>{st.session_state.idx + 1}</b> / {total} &nbsp; "
        f"<span style='color:gray;font-size:13px'>({pct:.0f}%)</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
with c_next:
    if st.button("다음 ▶", use_container_width=True, disabled=st.session_state.idx == total - 1):
        st.session_state.idx += 1
        st.rerun()

st.progress((st.session_state.idx + 1) / total)

# 현재 라벨
row = labels[st.session_state.idx]

# 메인: 이미지 | 정보+액션
col_img, col_info2 = st.columns([3, 2])

with col_img:
    frame_path = get_frame_path(row["frame_id"])
    if frame_path:
        st.image(str(frame_path), use_container_width=True)
    else:
        st.warning(f"이미지 없음 (frame_id={row['frame_id']})")

with col_info2:
    # AI 예측 카드
    preset = row["preset_id"]
    conf = row["confidence"]
    is_prob = row["is_problematic"]
    status = row["review_status"]

    badge = "🟢 정상" if is_prob == 0 else ("🔴 문제" if is_prob == 1 else "❓ 미분류")
    conf_color = "green" if conf >= 0.8 else ("orange" if conf >= 0.6 else "red")
    status_ko = {
        "pending": "🟡 검수 대기", "auto_approved": "✅ 자동 승인",
        "human_review": "👁 인간 검수", "rejected": "❌ 거부",
        "synced": "☁️ 싱크 완료",
    }.get(status, status)

    st.markdown(f"### {LABEL_KO.get(preset, preset)}")
    st.markdown(f"`{preset}` &nbsp; {badge}", unsafe_allow_html=False)
    st.markdown(
        f"신뢰도: <span style='color:{conf_color};font-weight:bold;font-size:18px'>{conf:.2f}</span>",
        unsafe_allow_html=True,
    )
    st.caption(f"상태: {status_ko}  |  영상: {row.get('title') or '—'}  |  frame {row['frame_id']}")

    if row.get("reviewer_note"):
        st.info(row["reviewer_note"])

    st.divider()

    # 주요 액션 버튼
    st.markdown("**검수** *(A / R)*")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("✅ 맞음", key="btn_accept", type="primary", use_container_width=True):
            save_label(row["id"], preset, "human_review", None)
            _advance()
            st.rerun()
    with b2:
        if st.button("❌ 틀림", key="btn_reject", use_container_width=True):
            save_label(row["id"], "unknown", "human_review", "검수자 거부")
            _advance()
            st.rerun()

    st.divider()

    # 카테고리 변경 (탭)
    st.markdown("**카테고리 변경**")
    render_category_picker(row)

# 하단: 번호 점프
st.divider()
jump = st.number_input("번호로 이동", min_value=1, max_value=total,
                       value=st.session_state.idx + 1, step=1, label_visibility="visible")
if int(jump) - 1 != st.session_state.idx:
    st.session_state.idx = int(jump) - 1
    st.rerun()

# 키보드 단축키 주입
components.html(KEYBOARD_JS, height=0)
