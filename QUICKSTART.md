# TailLog Labeling — 빠른 시작 가이드

## 1. 환경 설정

```bash
# 저장소 복제 및 이동
cd /Users/family/jason/taillog_labeling

# 환경변수 설정
cp .env.example .env.local
# 주인님이 직접 SUPABASE_SERVICE_ROLE_KEY 입력

# Python 가상환경
python3.11 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -e ".[dev]"
```

## 2. 사전 준비

### Ollama 실행
```bash
ollama serve
# 별도 터미널에서 모델 다운로드:
ollama pull gemma4-unsloth-e4b:latest
ollama pull gemma4:26b-a4b-it-q4_K_M
```

### SQLite DB 초기화
```bash
python -c "from src.core.database import init_db; init_db()"
```

### Supabase 연결 확인
```bash
python -c "from src.core.supabase_client import get_supabase_client; print(get_supabase_client().check_connection())"
```

## 3. 실행 방법

### 드라이런 (DB 저장 안 함)
```bash
python src/pipelines/run.py --dry-run --max-items 1
```

### 단일 URL 처리
```bash
python src/pipelines/run.py --url "https://www.youtube.com/watch?v=..."
```

### 배치 처리 (urls.txt)
```bash
# urls.txt에 URL 입력 (한 줄에 하나씩)
python src/pipelines/run.py --urls-file urls.txt --max-items 5
```

## 4. 테스트

```bash
# 전체 테스트
pytest tests/ -v

# 커버리지 포함
pytest tests/ --cov=src --cov-report=html
```

## 5. 파이프라인 흐름

```
[YouTube URL]
  ↓ collector (yt-dlp 다운로드)
[video.mp4]
  ↓ pose_extractor (YOLOv8n 탐지)
[pose_results] (17 keypoints × N frames)
  ↓ behavior_classifier (gemma4 분류)
[behavior_labels] (pending)
  ↓ abc_labeler (gemma4 ABC 생성)
[behavior_labels] (antecedent/behavior/consequence 추가)
  ↓ critic (gemma4:26b 검수)
[behavior_labels] (critic_pass 기록)
  ↓ quality_gate (신뢰도 임계값)
[review_status 설정]
  ↓ sync_writer (if auto_approved)
[Supabase behavior_logs] (sync 완료)
```

## 6. 모니터링

### 라벨 상태 조회
```bash
python -c "
from src.core.database import get_db
db = get_db()
result = db.execute('SELECT review_status, COUNT(*) as cnt FROM behavior_labels GROUP BY review_status')
for row in result:
    print(f'{row[\"review_status\"]}: {row[\"cnt\"]}건')
"
```

### 실패 로그 확인
```bash
tail -50 data/exports/sync_logs/watchdog.log
```

### HALT 조건 확인
```bash
ls -la data/exports/sync_logs/HALT_*.log
```

## 7. 트러블슈팅

### "Ollama connection refused"
→ Ollama 실행 중인지 확인: `ollama serve`

### "SUPABASE_SERVICE_ROLE_KEY not found"
→ .env.local 파일에 키 입력

### "No valid keypoints detected"
→ 영상에 강아지가 충분히 크게 나오는지 확인 (화면의 5% 이상)

### "JSON parse error"
→ LLM이 valid JSON 응답하지 못함
→ LLM 모델 상태 확인, watchdog 로그 참고

## 8. 개발 팁

### 신뢰도 임계값 변경
- `src/agents/quality_gate.py` → `AUTO_APPROVED_THRESHOLD`, `HUMAN_REVIEW_THRESHOLD`

### 모델 변경
- `src/core/llm.py` → `get_ollama_client()` 모델명 수정
- `src/agents/pose_extractor.py` → `MODEL_PATH` 변경

### Prompt 커스터마이징
- `src/prompts/` 폴더의 프롬프트 파일 수정
- `src/prompts/system_prompts.py` 시스템 프롬프트

### Cold Start 해제
- `src/agents/quality_gate.py` → `COLD_START_LIMIT = 100` 값 변경

## 9. 다음 단계

- Phase 1 (50건): 포즈 추출 검증
- Phase 2 (500건): behavior_classifier 평가
- Phase 3 (2,000건): critic shadow 비교
- Phase 4 (10,000건): 프로덕션 이식

자세한 내용은 `docs/ref/` SSOT 문서 참고!
