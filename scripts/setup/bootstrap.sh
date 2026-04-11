#!/bin/bash
# bootstrap.sh — 모델 다운로드 + 환경 초기화

set -e

echo "=== TailLog Labeling Bootstrap ==="

# 1. Python 패키지 설치
echo "[1/5] Installing Python packages..."
pip install -r requirements.txt

# 2. YOLOv8n-pose 모델 다운로드
echo "[2/5] Downloading YOLOv8n-pose model..."
python -c "
from ultralytics import YOLO
import shutil, os
model = YOLO('yolov8n-pose.pt')
os.makedirs('data/models', exist_ok=True)
# ultralytics가 ~/.ultralytics에 저장하므로 복사
import glob
candidates = glob.glob(os.path.expanduser('~/.ultralytics/**/yolov8n-pose.pt'), recursive=True)
if candidates:
    shutil.copy(candidates[0], 'data/models/yolov8n-pose.pt')
    print('YOLOv8n-pose.pt saved to data/models/')
else:
    print('Model auto-downloaded by ultralytics')
"

# 3. Ollama 모델 확인
echo "[3/5] Checking Ollama models..."
if ! command -v ollama &> /dev/null; then
    echo "⚠️  Ollama not found. Install from https://ollama.com"
    exit 1
fi

echo "Ollama models available:"
ollama list

echo ""
echo "Required models:"
echo "  - gemma4-unsloth-e4b:latest"
echo "  - gemma4:26b-a4b-it-q4_K_M"
echo ""
echo "If missing, run:"
echo "  ollama pull gemma4-unsloth-e4b:latest"
echo "  ollama pull gemma4:26b-a4b-it-q4_K_M"

# 4. SQLite DB 초기화
echo "[4/5] Initializing SQLite database..."
python -c "
import sys
sys.path.insert(0, '.')
from src.core.database import init_db
init_db()
print('SQLite DB initialized: data/databases/labeling.db')
"

# 5. 환경 변수 확인
echo "[5/5] Checking .env.local..."
if [ ! -f ".env.local" ]; then
    cp .env.example .env.local
    echo "⚠️  .env.local created from template. Please fill in:"
    echo "    - SUPABASE_SERVICE_ROLE_KEY"
    echo "    - (Optional) TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID"
else
    echo ".env.local exists ✓"
fi

echo ""
echo "=== Bootstrap Complete ==="
echo "Next: python src/pipelines/run.py --dry-run --max-items 1"
