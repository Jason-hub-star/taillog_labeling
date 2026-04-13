"""
라벨/카테고리 상수 관리 — SSOT
기준: TaillogToss presets.ts (B2B-001) × LABEL-SCHEMA.md v3.0

모든 파일은 여기서 import해서 사용. 직접 하드코딩 금지.
"""

# ── 카테고리별 라벨 정의 ────────────────────────────────────────────────────
# (preset_id, 한국어명, is_problematic)
# is_problematic: False=정상, True=문제행동, None=미분류

_LABEL_DEFS: dict[str, list[tuple[str, str, bool | None]]] = {
    "walk": [
        ("walk_normal",   "정상 산책",       False),
        ("walk_pulling",  "리드 당김",        True),
        ("walk_reactive", "반응성(짖음)",     True),
        ("walk_refuse",   "산책 거부",        True),
    ],
    "play": [
        ("play_normal",      "정상 놀이",  False),
        ("play_overexcited", "과잉흥분",   True),
        ("play_resource",    "자원 지킴",  True),
    ],
    "condition": [
        ("cond_good",    "컨디션 좋음",   False),
        ("cond_tired",   "피곤/무기력",   True),
        ("cond_anxious", "불안 징후",     True),
        ("cond_excited", "활발/에너지",   False),
    ],
    "alert": [
        ("alert_vomit",      "구토",       True),
        ("alert_diarrhea",   "설사",       True),
        ("alert_limp",       "절뚝거림",   True),
        ("alert_aggression", "공격 행동",  True),
        ("alert_noeat",      "식욕부진",   True),
    ],
    "meal": [
        ("meal_full",   "완식",      False),
        ("meal_half",   "반식",      True),
        ("meal_refuse", "식사 거부", True),
    ],
    "social": [
        ("social_good",     "타견 우호",   False),
        ("social_avoid",    "타견 회피",   True),
        ("social_reactive", "타견 반응",   True),
        ("social_human",    "사람 우호",   False),
    ],
}

# ── 파생 상수 ─────────────────────────────────────────────────────────────

# 카테고리 → 라벨 목록
CATEGORIES: dict[str, list[str]] = {
    cat: [label for label, _, _ in defs]
    for cat, defs in _LABEL_DEFS.items()
}

# 모든 라벨 (unknown 포함)
ALL_LABELS: list[str] = [
    label
    for defs in _LABEL_DEFS.values()
    for label, _, _ in defs
] + ["unknown"]

# 정상행동 라벨 목록 (is_problematic=False)
NORMAL_LABELS: list[str] = [
    label
    for defs in _LABEL_DEFS.values()
    for label, _, is_prob in defs
    if is_prob is False
]

# 문제행동 라벨 목록 (is_problematic=True)
PROBLEM_LABELS: list[str] = [
    label
    for defs in _LABEL_DEFS.values()
    for label, _, is_prob in defs
    if is_prob is True
]

# preset_id → 한국어명
LABEL_TO_KO: dict[str, str] = {
    label: ko
    for defs in _LABEL_DEFS.values()
    for label, ko, _ in defs
}
LABEL_TO_KO["unknown"] = "미분류"

# preset_id → category
LABEL_TO_CATEGORY: dict[str, str] = {
    label: cat
    for cat, defs in _LABEL_DEFS.items()
    for label, _, _ in defs
}
LABEL_TO_CATEGORY["unknown"] = "unknown"

# preset_id → is_problematic
IS_PROBLEMATIC: dict[str, bool | None] = {
    label: is_prob
    for defs in _LABEL_DEFS.values()
    for label, _, is_prob in defs
}
IS_PROBLEMATIC["unknown"] = None

# ── Intensity 척도 ─────────────────────────────────────────────────────────
# TaillogToss 기준 1-10 (LABEL-SCHEMA.md v3.0 확정)

INTENSITY_MIN = 1
INTENSITY_MAX = 10
INTENSITY_DEFAULT = 6  # 보통

INTENSITY_SCALE = {
    (1, 2):  "미미한 반응",
    (3, 4):  "약함",
    (5, 6):  "보통",
    (7, 8):  "강함",
    (9, 10): "제어 어려움",
}

# ── TaillogToss ↔ taillog_labeling 이름 매핑 ──────────────────────────────
# (구 normal_* 이름을 쓴 기존 데이터 마이그레이션용)

LEGACY_TO_CURRENT: dict[str, str] = {
    "normal_walk":   "walk_normal",
    "normal_play":   "play_normal",
    "normal_rest":   "cond_good",
    "normal_eat":    "meal_full",
    "normal_social": "social_good",
    # 제거된 라벨 → unknown으로 폴백
    "walk_fearful":      "unknown",
    "walk_distracted":   "unknown",
    "play_rough":        "unknown",
    "cond_destructive":  "unknown",
    "cond_repetitive":   "unknown",
    "cond_toileting":    "unknown",
    "alert_barking":     "unknown",
    "alert_territorial": "unknown",
    "meal_guarding":     "unknown",
    "meal_picky":        "unknown",
    "meal_stealing":     "unknown",
    "social_fearful":    "unknown",
    "social_dominant":   "unknown",
    "social_separation": "unknown",
}

# ── 검수 앱용 그룹 정의 ────────────────────────────────────────────────────

# 전체 그룹 (정상+문제 모두 포함)
REVIEW_GROUPS: dict[str, list[str]] = {
    "산책 🐕": CATEGORIES["walk"],
    "놀이 🎾": CATEGORIES["play"],
    "컨디션 💤": CATEGORIES["condition"],
    "이상징후 🚨": CATEGORIES["alert"],
    "식사 🍖": CATEGORIES["meal"],
    "사교 👥": CATEGORIES["social"],
}

# 문제행동만 포함한 그룹 (검수 앱 "문제행동" 탭 전용)
PROBLEM_REVIEW_GROUPS: dict[str, list[str]] = {
    group_name: [l for l in labels if IS_PROBLEMATIC.get(l) is True]
    for group_name, labels in REVIEW_GROUPS.items()
    if any(IS_PROBLEMATIC.get(l) is True for l in labels)
}

# 정상행동 시각적 단서 (검수 앱 표시용)
NORMAL_CUES: dict[str, str] = {
    "walk_normal":   "걷기/뛰기, 머리 올려짐, 속력 일정",
    "play_normal":   "뛰기/구르기, 입 벌어짐, 신체 유연",
    "cond_good":     "눈 초롱초롱, 귀·꼬리 자연스러움",
    "cond_excited":  "활발한 움직임, 꼬리 흔들기",
    "meal_full":     "밥/물 먹기, 고개 숙임, 깨끗이 섭취",
    "social_good":   "다른 개/사람과 부드러운 접촉",
    "social_human":  "낯선 사람에게 꼬리 흔들며 접근",
}
