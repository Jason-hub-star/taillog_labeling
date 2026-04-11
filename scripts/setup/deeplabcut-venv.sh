#!/bin/bash
# M1: Python 3.10 venv + deeplabcut + SuperAnimal 설치
# 실행: bash scripts/setup/deeplabcut-venv.sh
# 결과: .venv_dlc/ 생성, deeplabcut + dlclibrary 설치

set -e  # 오류 시 즉시 중단

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv_dlc"

echo "=== M1: deeplabcut 전용 venv 구성 ==="
echo "프로젝트: $PROJECT_ROOT"
echo "venv 경로: $VENV_DIR"
echo ""

# ── Step 1: Python 3.10 확인 ──────────────────────────────────────────────
echo "[1/5] Python 3.10 확인..."

PYTHON310=""
for candidate in python3.10 python3.11; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON310="$candidate"
        echo "  ✅ 발견: $($candidate --version)"
        break
    fi
done

if [ -z "$PYTHON310" ]; then
    echo "  ❌ Python 3.10 또는 3.11 없음."
    echo "  macOS: brew install python@3.10"
    echo "  또는: brew install python@3.11"
    exit 1
fi

# ── Step 2: venv 생성 ─────────────────────────────────────────────────────
echo ""
echo "[2/5] venv 생성: $VENV_DIR"

if [ -d "$VENV_DIR" ]; then
    echo "  ⚠️  이미 존재 — 재생성하려면 rm -rf $VENV_DIR 후 재실행"
else
    "$PYTHON310" -m venv "$VENV_DIR"
    echo "  ✅ venv 생성 완료"
fi

# ── Step 3: pip + setuptools 업그레이드 ──────────────────────────────────
echo ""
echo "[3/5] pip + setuptools 설정..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip --quiet
# setuptools<67: pkg_resources가 빌드 격리 환경에서도 동작하는 마지막 버전
"$VENV_DIR/bin/python" -m pip install "setuptools<67" wheel --quiet
PIP_VER=$("$VENV_DIR/bin/python" -m pip --version | awk '{print $2}')
echo "  ✅ pip $PIP_VER (setuptools<67 고정)"

# ── Step 4: deeplabcut 의존성 설치 ────────────────────────────────────────
echo ""
echo "[4/5] deeplabcut 설치 (수 분 소요)..."

PY="$VENV_DIR/bin/python"

# numpy<2.0 먼저 (tables 빌드 요구)
"$PY" -m pip install "numpy<2.0" --quiet
echo "  numpy 완료"

# tables — --no-build-isolation으로 바이너리 wheel 사용
echo "  tables 설치 시도..."
if "$PY" -m pip install tables --no-build-isolation --quiet; then
    echo "  tables 완료"
else
    echo "  ❌ tables 설치 실패"
    exit 1
fi

# tables 버전 고정 (이미 설치된 버전으로 deeplabcut이 다운그레이드 못 하도록)
TABLES_VER=$("$PY" -c "import tables; print(tables.__version__)")
echo "tables>=$TABLES_VER" > /tmp/dlc_constraints.txt
echo "  tables 버전 고정: $TABLES_VER"

# deeplabcut 설치 (modelzoo extras 포함)
echo "  deeplabcut 설치 중 (수 분 소요)..."
if "$PY" -m pip install "deeplabcut[modelzoo]" \
    --constraint /tmp/dlc_constraints.txt --quiet 2>/dev/null; then
    echo "  deeplabcut[modelzoo] 완료"
elif "$PY" -m pip install "deeplabcut" \
    --constraint /tmp/dlc_constraints.txt --quiet; then
    echo "  deeplabcut (base) 완료"
else
    echo "  ❌ deeplabcut 설치 실패"
    exit 1
fi

# dlclibrary (HuggingFace 모델 다운로드용)
"$PY" -m pip install dlclibrary --quiet
echo "  dlclibrary 완료"

# pandas (H5 파싱용)
"$PY" -m pip install pandas --quiet
echo "  pandas 완료"

# ── Step 4b: DLC __init__ TF 패치 (PyTorch-only 환경) ────────────────────
echo ""
echo "[4b/5] deeplabcut TF 패치 적용..."

DLC_INIT="$VENV_DIR/lib/$(ls "$VENV_DIR/lib/")/site-packages/deeplabcut/__init__.py"
DLC_TF_INIT="$VENV_DIR/lib/$(ls "$VENV_DIR/lib/")/site-packages/deeplabcut/pose_estimation_tensorflow/__init__.py"

# __init__.py: import tensorflow → try/except
python3 - "$DLC_INIT" <<'PYEOF'
import sys, re
path = sys.argv[1]
with open(path) as f:
    src = f.read()
old = "import tensorflow as tf\n\ntf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)"
new = "try:\n    import tensorflow as tf\n    tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)\nexcept ImportError:\n    tf = None"
if old in src:
    with open(path, 'w') as f:
        f.write(src.replace(old, new))
    print("  ✅ __init__.py TF 패치 완료")
else:
    print("  ⚠️  __init__.py 이미 패치됨 (또는 변경됨)")
PYEOF

# pose_estimation_tensorflow/__init__.py: 전체 import → try/except
python3 - "$DLC_TF_INIT" <<'PYEOF'
import sys
path = sys.argv[1]
with open(path) as f:
    src = f.read()
if 'try:' not in src:
    wrapped = "# TF-dependent submodules — wrapped for PyTorch-only environments\ntry:\n"
    for line in src.split('\n'):
        if line.startswith('from deeplabcut'):
            wrapped += "    " + line + "\n"
        else:
            wrapped += line + "\n"
    wrapped += "except (ImportError, ModuleNotFoundError, AttributeError):\n    pass\n"
    with open(path, 'w') as f:
        f.write(wrapped)
    print("  ✅ pose_estimation_tensorflow/__init__.py TF 패치 완료")
else:
    print("  ⚠️  pose_estimation_tensorflow/__init__.py 이미 패치됨")
PYEOF

# ── Step 5: 설치 검증 ─────────────────────────────────────────────────────
echo ""
echo "[5/5] 설치 검증..."

"$VENV_DIR/bin/python" - <<'EOF'
import sys
print(f"  Python: {sys.version.split()[0]}")

try:
    import deeplabcut
    print(f"  ✅ deeplabcut: {deeplabcut.__version__}")
except ImportError as e:
    print(f"  ❌ deeplabcut: {e}")
    sys.exit(1)

try:
    import dlclibrary
    print(f"  ✅ dlclibrary: OK")
except ImportError as e:
    print(f"  ❌ dlclibrary: {e}")
    sys.exit(1)

try:
    import tables
    print(f"  ✅ tables: {tables.__version__}")
except ImportError as e:
    print(f"  ❌ tables: {e}")
    sys.exit(1)

try:
    import numpy as np
    print(f"  ✅ numpy: {np.__version__}")
    assert int(np.__version__.split('.')[0]) < 2, "numpy 2.x 미지원"
except AssertionError:
    print(f"  ❌ numpy 버전 2.x — 1.x 필요")
    sys.exit(1)

print("\n✅ M1 완료 — deeplabcut venv 준비됨")
print(f"   사용: {sys.executable}")
EOF

echo ""
echo "=== 완료 ==="
echo "다음 단계 (M2): pose_extractor.py SuperAnimal 교체"
echo "  subprocess 경로: $VENV_DIR/bin/python"
