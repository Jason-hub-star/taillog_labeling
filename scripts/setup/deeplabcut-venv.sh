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

# ── Step 3: pip 업그레이드 ────────────────────────────────────────────────
echo ""
echo "[3/5] pip 업그레이드..."
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
echo "  ✅ pip $(\"$VENV_DIR/bin/pip\" --version | awk '{print $2}')"

# ── Step 4: deeplabcut 의존성 설치 ────────────────────────────────────────
echo ""
echo "[4/5] deeplabcut 설치 (수 분 소요)..."

# numpy<2.0 먼저 (tables 빌드 요구)
"$VENV_DIR/bin/pip" install "numpy<2.0" --quiet
echo "  numpy 완료"

# tables 명시적 버전 (deeplabcut 필요)
"$VENV_DIR/bin/pip" install "tables==3.8.0" --quiet
echo "  tables 완료"

# deeplabcut modelzoo 포함 설치
"$VENV_DIR/bin/pip" install "deeplabcut[modelzoo]" --quiet
echo "  deeplabcut 완료"

# dlclibrary (HuggingFace 모델 다운로드용)
"$VENV_DIR/bin/pip" install dlclibrary --quiet
echo "  dlclibrary 완료"

# pandas (H5 파싱용)
"$VENV_DIR/bin/pip" install pandas --quiet
echo "  pandas 완료"

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
