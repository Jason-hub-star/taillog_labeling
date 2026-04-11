#!/bin/bash
# YOLOv8 vs SuperAnimal 비교 테스트 전체 실행
# 사용법: bash scripts/compare/run_all.sh [urls.txt]
#
# urls.txt 예시:
#   https://www.youtube.com/watch?v=...   # 포메라니안 (소형견)
#   https://www.youtube.com/watch?v=...   # 리트리버 (대형견)
#   https://www.youtube.com/watch?v=...   # 다중 강아지

set -e
cd "$(dirname "$0")/../.."

URLS_FILE="${1:-urls.txt}"
CONF="${2:-0.3}"

echo "══════════════════════════════════════════════"
echo "  TailLog: YOLOv8n-pose vs SuperAnimal 비교"
echo "══════════════════════════════════════════════"
echo ""

if [ ! -f "$URLS_FILE" ]; then
    echo "❌ URL 파일 없음: $URLS_FILE"
    echo "   사용법: bash scripts/compare/run_all.sh urls.txt"
    exit 1
fi

echo "📹 [1/4] 영상 다운로드 + 프레임 추출..."
python scripts/compare/download.py --urls-file "$URLS_FILE"

echo ""
echo "🤖 [2/4] YOLOv8n-pose 실행..."
python scripts/compare/run_yolo.py \
    --frames-dir data/cache/compare/frames \
    --output-dir data/cache/compare/yolo_results \
    --conf "$CONF"

echo ""
echo "🦮 [3/4] SuperAnimal 실행..."
# SuperAnimal은 프레임이 아닌 비디오 파일 직접 처리
python scripts/compare/run_superanimal.py \
    --video-dir data/cache/compare/videos \
    --output-dir data/cache/compare/superanimal_results

echo ""
echo "📊 [4/4] 시각화 + 리포트 생성..."
python scripts/compare/visualize.py \
    --yolo-dir data/cache/compare/yolo_results \
    --superanimal-dir data/cache/compare/superanimal_results \
    --output-dir data/exports

echo ""
echo "══════════════════════════════════════════════"
echo "✅ 완료!"
echo ""
echo "📋 결과:"
echo "   리포트:  data/exports/compare_report.md"
echo "   이미지:  data/exports/compare_images/"
echo "   원본:    data/cache/compare/"
echo "══════════════════════════════════════════════"
