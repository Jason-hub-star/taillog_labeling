#!/bin/bash
# test-ollama.sh — Ollama 연결 + 두 모델 응답 확인

echo "=== Ollama Connection Test ==="

OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"

# 연결 확인
if ! curl -s "$OLLAMA_URL/api/tags" > /dev/null; then
    echo "❌ Ollama not reachable at $OLLAMA_URL"
    echo "   Start with: ollama serve"
    exit 1
fi
echo "✓ Ollama reachable at $OLLAMA_URL"

# gemma4-unsloth 테스트
echo ""
echo "[1/2] Testing gemma4-unsloth-e4b:latest..."
RESPONSE=$(curl -s -X POST "$OLLAMA_URL/api/generate" \
  -H "Content-Type: application/json" \
  -d '{"model":"gemma4-unsloth-e4b:latest","prompt":"Reply with only: OK","stream":false}')

if echo "$RESPONSE" | grep -q '"response"'; then
    echo "✓ gemma4-unsloth-e4b: OK"
else
    echo "❌ gemma4-unsloth-e4b: FAILED"
    echo "$RESPONSE" | head -3
fi

# gemma4:26b 테스트
echo ""
echo "[2/2] Testing gemma4:26b-a4b-it-q4_K_M..."
RESPONSE=$(curl -s -X POST "$OLLAMA_URL/api/generate" \
  -H "Content-Type: application/json" \
  -d '{"model":"gemma4:26b-a4b-it-q4_K_M","prompt":"Reply with only: OK","stream":false}')

if echo "$RESPONSE" | grep -q '"response"'; then
    echo "✓ gemma4:26b: OK"
else
    echo "❌ gemma4:26b: FAILED (may need: ollama pull gemma4:26b-a4b-it-q4_K_M)"
fi

echo ""
echo "=== Test Complete ==="
