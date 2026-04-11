# TailLog Labeling — Claude Code 프로젝트 가이드

YouTube 강아지 영상 → ABC 행동 라벨링 → TailLog Supabase 자동 sync 파이프라인.

## 핵심 원칙
1. **SSOT 우선**: 모든 결정은 `docs/ref/` 문서가 기준. 코드와 충돌 시 문서 먼저 확인.
2. **파일 수정 전 필독**: 수정 전 현재 내용 반드시 읽기.
3. **OPEN-DECISIONS 확인**: 미결 항목은 `docs/ref/OPEN-DECISIONS.md` 참조.
4. **한 에이전트 = 한 결정**: 각 에이전트는 단일 책임만 수행.
5. **하드코딩 금지**: 아래 "하드코딩 방지 규칙" 섹션 준수.

## 빠른 시작
```bash
# 환경 설정
cp .env.example .env.local  # 키 입력 필요
source venv/bin/activate

# 모델 다운로드
bash scripts/setup/bootstrap.sh

# DB 초기화
python -c "from src.core.database import init_db; init_db()"

# 전체 파이프라인 드라이런
python src/pipelines/run.py --dry-run --max-items 1

# 테스트
pytest tests/ -v
```

## 프로젝트 구조
- `src/agents/` — 7개 에이전트 구현 (collector, pose_extractor, behavior_classifier, abc_labeler, critic, sync_writer, watchdog)
- `src/pipelines/` — 파이프라인 오케스트레이션
- `src/core/` — DB, LLM, Supabase 클라이언트
- `docs/ref/` — SSOT 문서 (잠금된 결정)
- `.claude/automations/` — 일일/주간 자동화 프롬프트

## Supabase
- **URL**: `https://qufjlveukaoiokhpkhwj.supabase.co`
- **키**: `.env.local`의 `SUPABASE_SERVICE_ROLE_KEY`
- **대상 테이블**: `behavior_logs`
- **sync 방향**: 로컬 SQLite → Supabase (단방향)

## 환경 변수
- **`.env.local`**: Supabase 키, Ollama URL, 경로 설정
- **`.env.example`**: 템플릿

## SSOT 문서 목록
| 문서 | 역할 |
|------|------|
| `docs/ref/TECH-STACK-DECISIONS.md` | 모든 기술 결정 |
| `docs/ref/AGENT-OPERATING-MODEL.md` | 에이전트 역할 |
| `docs/ref/LABEL-SCHEMA.md` | 라벨 포맷 |
| `docs/ref/CONFIDENCE-THRESHOLD-POLICY.md` | 신뢰도 임계값 |
| `docs/ref/SUPABASE-SYNC-CONTRACT.md` | sync 규약 |
| `docs/ref/OPEN-DECISIONS.md` | 미결 항목 |

## 하드코딩 방지 규칙

### SuperAnimal / DeepLabCut
- **bodypart 이름 절대 하드코딩 금지** — 반드시 런타임에 모델 config에서 읽어야 함
  ```python
  # ❌ 금지
  BODYPARTS = ["nose", "left_ear", ...]

  # ✅ 허용
  from dlclibrary import get_available_models
  # 또는 모델 config yaml에서 직접 파싱
  ```
- **모델명** — `src/utils/config.py`의 상수만 사용. 에이전트 파일에 직접 문자열 금지.
- **dlclibrary API** — 코드 작성 전 실제 API 응답 확인:
  ```bash
  .venv_dlc/bin/python -c "from dlclibrary import get_available_models; print(get_available_models('superanimal_quadruped'))"
  ```
- **DLC 버전 의존 코드** — `deeplabcut.__init__`은 버전마다 다름. 직접 임포트 전 동작 확인 필수.
  - 참고: DLC 2.3.0은 TF 의존성 있어 `__init__.py` 패치 적용됨 (`.venv_dlc` 내부)

### Supabase 스키마
- **테이블/컬럼명** — `docs/ref/SUPABASE-SYNC-CONTRACT.md` 기준. 코드에 문자열 직접 작성 금지.
- **스키마 변경** — TailLog 앱과 협의 없이 컬럼 추가/변경 불가.
- 확인 방법:
  ```bash
  python scripts/validate/check_env.py  # 런타임 스키마 검증
  ```

### Ollama 모델명
- `src/utils/config.py`의 `BEHAVIOR_CLASSIFIER_MODEL`, `ABC_LABELER_MODEL`, `CRITIC_MODEL`만 사용
- 새 모델 추가 시 `config.py` 수정 → `docs/ref/TECH-STACK-DECISIONS.md` 업데이트

### 환경 검증
코드 작성 후 의존성이 있는 외부 API는 반드시 런타임 검증:
```bash
# SuperAnimal 모델/bodypart 확인
.venv_dlc/bin/python scripts/validate/check_env.py

# Ollama 모델 존재 확인
ollama list | grep -E "gemma4"

# Supabase 연결 확인
python -c "from src.core.supabase_client import get_supabase_client; print(get_supabase_client().check_connection())"
```

## 커밋 전 체크리스트
1. `pytest tests/ -v` — 전체 통과
2. `ruff check src/` — lint 통과
3. 새 결정 시 `docs/ref/TECH-STACK-DECISIONS.md` 업데이트
4. 미결 해결 시 `docs/ref/OPEN-DECISIONS.md` resolved 처리
