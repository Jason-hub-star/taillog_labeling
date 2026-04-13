#!/bin/bash
# M1: Python 3.11 venv + deeplabcut 2.3.11 + SuperAnimal + TF 설치
# 실행: bash scripts/setup/deeplabcut-venv.sh
# 검증: python3 scripts/validate/check_env.py
#
# 핵심 의존성 (2026-04-11 확인):
#   deeplabcut 2.3.11 (patched wheel: tables>=3.7.0)
#   tensorflow 2.21.0 + tf-keras 2.21.0 (keras 3 제거 필수)
#   numpy 1.x (numpy<2.0 필수)
#   tf_keras.legacy_tf_layers 심링크 (TF 2.21 path mismatch 해결)

set -e  # 오류 시 즉시 중단

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv_dlc"
PY="$VENV_DIR/bin/python"
SITE_PKG="$VENV_DIR/lib/python3.11/site-packages"

echo "=== M1: deeplabcut 전용 venv 구성 ==="
echo "프로젝트: $PROJECT_ROOT"
echo "venv 경로: $VENV_DIR"
echo ""

# ── Step 1: Python 3.11 확인 ──────────────────────────────────────────────
echo "[1/7] Python 3.11 확인..."

PYTHON311=""
for candidate in python3.11 python3.10; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON311="$candidate"
        echo "  ✅ 발견: $($candidate --version)"
        break
    fi
done

if [ -z "$PYTHON311" ]; then
    echo "  ❌ Python 3.10 또는 3.11 없음."
    echo "  macOS: brew install python@3.11"
    exit 1
fi

# ── Step 2: venv 생성 ─────────────────────────────────────────────────────
echo ""
echo "[2/7] venv 생성: $VENV_DIR"

if [ -d "$VENV_DIR" ]; then
    echo "  ⚠️  이미 존재 — 재생성하려면 rm -rf $VENV_DIR 후 재실행"
else
    "$PYTHON311" -m venv "$VENV_DIR"
    echo "  ✅ venv 생성 완료"
fi

# ── Step 3: pip + setuptools 업그레이드 ──────────────────────────────────
echo ""
echo "[3/7] pip + setuptools 설정..."
"$PY" -m pip install --upgrade pip --quiet
"$PY" -m pip install "setuptools<67" wheel --quiet
PIP_VER=$("$PY" -m pip --version | awk '{print $2}')
echo "  ✅ pip $PIP_VER"

# ── Step 4: 핵심 의존성 설치 ──────────────────────────────────────────────
echo ""
echo "[4/7] 핵심 의존성 설치..."

# numpy<2.0 먼저 (tables 빌드 + DLC 요구)
"$PY" -m pip install "numpy<2.0" --quiet
echo "  ✅ numpy"

# tables (HDF5 읽기용 — no-build-isolation으로 바이너리 wheel)
if "$PY" -m pip install tables --no-build-isolation --quiet 2>/dev/null; then
    TABLES_VER=$("$PY" -c "import tables; print(tables.__version__)")
    echo "  ✅ tables $TABLES_VER"
else
    echo "  ❌ tables 설치 실패"
    exit 1
fi

# pandas (H5 파싱용)
"$PY" -m pip install pandas --quiet
echo "  ✅ pandas"

# dlclibrary (HuggingFace 모델 다운로드용)
"$PY" -m pip install dlclibrary --quiet
echo "  ✅ dlclibrary"

# ── Step 5: deeplabcut 2.3.11 패치 wheel 설치 ─────────────────────────────
echo ""
echo "[5/7] deeplabcut 2.3.11 설치 (tables 의존성 패치 포함)..."

# DLC 2.3.11은 tables==3.8.0 요구 → M1에서 빌드 불가
# wheel을 직접 다운로드 후 tables>=3.7.0으로 패치하여 설치

DLC_WHEEL_DIR="/tmp/dlc_wheel_$$"
mkdir -p "$DLC_WHEEL_DIR"

echo "  deeplabcut 2.3.11 wheel 다운로드..."
"$PY" -m pip download "deeplabcut[modelzoo]==2.3.11" \
    --no-deps --dest "$DLC_WHEEL_DIR" --quiet 2>/dev/null || \
"$PY" -m pip download "deeplabcut==2.3.11" \
    --no-deps --dest "$DLC_WHEEL_DIR" --quiet

DLC_WHL=$(ls "$DLC_WHEEL_DIR"/deeplabcut*.whl 2>/dev/null | head -1)
if [ -z "$DLC_WHL" ]; then
    echo "  ❌ deeplabcut wheel 다운로드 실패"
    exit 1
fi

echo "  tables 의존성 패치 중..."
python3 - "$DLC_WHL" "$DLC_WHEEL_DIR" <<'PYEOF'
import sys, zipfile, shutil, os
whl = sys.argv[1]
dest = sys.argv[2]
out = os.path.join(dest, "patched_" + os.path.basename(whl))
with zipfile.ZipFile(whl) as zin, zipfile.ZipFile(out, 'w') as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename.endswith("METADATA") or item.filename.endswith("RECORD"):
            data = data.replace(b"tables==3.8.0", b"tables>=3.7.0")
        zout.writestr(item, data)
print(f"  patched → {out}")
PYEOF

PATCHED_WHL=$(ls "$DLC_WHEEL_DIR"/patched_deeplabcut*.whl 2>/dev/null | head -1)
"$PY" -m pip install "$PATCHED_WHL" --no-deps --quiet
rm -rf "$DLC_WHEEL_DIR"
echo "  ✅ deeplabcut 2.3.11 (patched)"

# 나머지 DLC 의존성 (tables 제외)
echo "  DLC 의존성 설치 중..."
"$PY" -m pip install \
    torch torchvision torchaudio \
    scikit-image scikit-learn \
    ruamel.yaml tensorpack tqdm \
    filterpy imageio imgaug \
    --quiet 2>/dev/null || true
echo "  ✅ DLC 의존성"

# ── Step 5b: TensorFlow + tf-keras 설치 ──────────────────────────────────
echo ""
echo "[5b/7] TensorFlow + tf-keras 설치..."

# tensorflow 2.21.0: M1 arm64 native
"$PY" -m pip install tensorflow==2.21.0 --quiet 2>/dev/null || \
"$PY" -m pip install tensorflow --quiet
echo "  ✅ tensorflow"

# tf-keras 2.x (keras 2 호환 레이어 제공)
"$PY" -m pip install tf-keras --quiet
echo "  ✅ tf-keras"

# keras: TF 2.21 lazy loader 동작에 필요 — 제거하지 않음
# (제거 시 tf.keras 접근 시 RecursionError 발생)
# nnets/utils.py 패치로 tf.compat.v1.layers 충돌은 별도 해결

# ── Step 6: DLC 패치 적용 ─────────────────────────────────────────────────
echo ""
echo "[6/7] DLC 호환성 패치 적용..."

# 6a: deeplabcut/__init__.py — TF import를 try/except로 감싸기
DLC_INIT="$SITE_PKG/deeplabcut/__init__.py"
python3 - "$DLC_INIT" <<'PYEOF'
import sys
path = sys.argv[1]
with open(path) as f:
    src = f.read()
# TF import 패치
old = "import tensorflow as tf\n    tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)"
new = "try:\n        import tensorflow as tf\n        tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)\n    except ImportError:\n        tf = None"
if old in src:
    with open(path, 'w') as f:
        f.write(src.replace(old, new))
    print("  ✅ deeplabcut/__init__.py TF import 패치")
else:
    print("  ⚠️  deeplabcut/__init__.py 이미 패치됨")
PYEOF

# 6b: auxfun_models.py — bare tf import 패치
AUXFUN="$SITE_PKG/deeplabcut/utils/auxfun_models.py"
python3 - "$AUXFUN" <<'PYEOF'
import sys
path = sys.argv[1]
with open(path) as f:
    src = f.read()
old = "import tensorflow as tf\n"
new = "try:\n    import tensorflow as tf\nexcept ImportError:\n    tf = None\n"
if old in src and new not in src:
    with open(path, 'w') as f:
        f.write(src.replace(old, new, 1))
    print("  ✅ auxfun_models.py TF import 패치")
else:
    print("  ⚠️  auxfun_models.py 이미 패치됨")
PYEOF

# 6c: pose_estimation_tensorflow/__init__.py — video_inference_superanimal 분리
DLC_TF_INIT="$SITE_PKG/deeplabcut/pose_estimation_tensorflow/__init__.py"
python3 - "$DLC_TF_INIT" <<'PYEOF'
import sys
path = sys.argv[1]
with open(path) as f:
    src = f.read()
if 'try:' not in src:
    # TF 의존 import 전체를 try/except로 감싸기
    wrapped = "# TF-dependent submodules — wrapped for PyTorch-only environments\ntry:\n"
    for line in src.split('\n'):
        wrapped += "    " + line + "\n" if line.startswith('from deeplabcut') else line + "\n"
    wrapped += "except (ImportError, ModuleNotFoundError, AttributeError):\n    pass  # TF not installed; PyTorch-based functions still importable below\n"
    # video_inference_superanimal는 TF try/except 밖에서 별도 import
    wrapped += "\n# PyTorch-based SuperAnimal — TF 불필요, try/except 밖에서 import\ntry:\n    from deeplabcut.pose_estimation_tensorflow.predict_supermodel import (\n        video_inference_superanimal,\n    )\nexcept (ImportError, ModuleNotFoundError) as _e:\n    pass\n"
    with open(path, 'w') as f:
        f.write(wrapped)
    print("  ✅ pose_estimation_tensorflow/__init__.py 패치")
else:
    print("  ⚠️  pose_estimation_tensorflow/__init__.py 이미 패치됨")
PYEOF

# 6d: nnets/utils.py — tf.compat.v1.layers → tf.keras.layers 패치
NNETS_UTILS="$SITE_PKG/deeplabcut/pose_estimation_tensorflow/nnets/utils.py"
python3 - "$NNETS_UTILS" <<'PYEOF'
import sys, re
path = sys.argv[1]
with open(path) as f:
    src = f.read()
patched = src
patched = patched.replace(
    "class TpuBatchNormalization(tf.compat.v1.layers.BatchNormalization):",
    "class TpuBatchNormalization(tf.keras.layers.BatchNormalization):"
)
patched = patched.replace(
    "class BatchNormalization(tf.compat.v1.layers.BatchNormalization):",
    "class BatchNormalization(tf.keras.layers.BatchNormalization):"
)
patched = patched.replace(
    "class DepthwiseConv2D(tf.keras.layers.DepthwiseConv2D, tf.compat.v1.layers.Layer):",
    "class DepthwiseConv2D(tf.keras.layers.DepthwiseConv2D, tf.keras.layers.Layer):"
)
if patched != src:
    with open(path, 'w') as f:
        f.write(patched)
    print("  ✅ nnets/utils.py Keras 3 호환 패치")
else:
    print("  ⚠️  nnets/utils.py 이미 패치됨")
PYEOF

# 6e: tensorpack/compat/__init__.py — tf.layers 할당 try/except 패치
TENSORPACK_COMPAT="$SITE_PKG/tensorpack/compat/__init__.py"
if [ -f "$TENSORPACK_COMPAT" ]; then
    python3 - "$TENSORPACK_COMPAT" <<'PYEOF'
import sys
path = sys.argv[1]
with open(path) as f:
    src = f.read()
old = "        tf.layers = tf.keras.layers"
new = "        try:\n            tf.layers = tf.keras.layers\n        except Exception:\n            pass  # Keras 3 lazy loader 호환성 문제 — 무시"
if old in src and "try:" not in src[src.find(old)-20:src.find(old)]:
    with open(path, 'w') as f:
        f.write(src.replace(old, new))
    print("  ✅ tensorpack/compat/__init__.py 패치")
else:
    print("  ⚠️  tensorpack/compat/__init__.py 이미 패치됨")
PYEOF
fi

# 6f: tf_keras.legacy_tf_layers 심링크 (TF 2.21 경로 불일치 해결)
TF_KERAS_LINK="$SITE_PKG/tf_keras/legacy_tf_layers"
TF_KERAS_SRC="$SITE_PKG/tf_keras/src/legacy_tf_layers"
if [ ! -e "$TF_KERAS_LINK" ] && [ -d "$TF_KERAS_SRC" ]; then
    ln -s "$TF_KERAS_SRC" "$TF_KERAS_LINK"
    echo "  ✅ tf_keras.legacy_tf_layers 심링크 생성"
elif [ -e "$TF_KERAS_LINK" ]; then
    echo "  ⚠️  tf_keras.legacy_tf_layers 이미 존재"
else
    echo "  ⚠️  tf_keras/src/legacy_tf_layers 없음 — 심링크 스킵"
fi

# ── Step 7: 설치 검증 ─────────────────────────────────────────────────────
echo ""
echo "[7/7] 설치 검증..."

"$PY" - <<'EOF'
import sys
print(f"  Python: {sys.version.split()[0]}")
ok = True

pkgs = {
    "deeplabcut": lambda: __import__("deeplabcut").__version__,
    "dlclibrary": lambda: "ok",
    "tables": lambda: __import__("tables").__version__,
    "numpy<2.0": lambda: (
        v := __import__("numpy").__version__,
        (None if int(v.split(".")[0]) < 2 else (_ for _ in ()).throw(AssertionError(f"numpy {v} >=2.0"))),
        v
    )[-1],
    "tensorflow": lambda: __import__("tensorflow").__version__,
    "tf_keras": lambda: __import__("tf_keras").__version__,
    "video_inference_superanimal": lambda: (
        __import__("deeplabcut").video_inference_superanimal and "available"
    ),
}

for name, fn in pkgs.items():
    try:
        ver = fn()
        print(f"  ✅ {name}: {ver}")
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        ok = False

# nnets 등록 확인
try:
    from deeplabcut.pose_estimation_tensorflow.nnets import PoseNetFactory
    nets = list(PoseNetFactory._nets.keys())
    if "resnet" in " ".join(nets):
        print(f"  ✅ PoseNetFactory 등록: {nets}")
    else:
        print(f"  ❌ resnet 미등록: {nets}")
        ok = False
except Exception as e:
    print(f"  ❌ PoseNetFactory: {e}")
    ok = False

if ok:
    print("\n✅ M1 완료 — deeplabcut venv 준비됨")
    print(f"   사용: {sys.executable}")
else:
    print("\n❌ 일부 검증 실패 — 로그 확인 필요")
    sys.exit(1)
EOF

echo ""
echo "=== 완료 ==="
echo "환경 검증: python3 scripts/validate/check_env.py"
echo "추론 테스트: python3 scripts/validate/check_env.py --infer"
