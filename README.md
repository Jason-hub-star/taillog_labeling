# TailLog Labeling Pipeline

YouTube 강아지 영상 → ABC 행동 자동 라벨링 → TailLog Supabase sync

## 구조

```
collector → pose_extractor → behavior_classifier → abc_labeler → critic → sync_writer
```

## 빠른 시작

```bash
cp .env.example .env.local   # SUPABASE_SERVICE_ROLE_KEY 입력
bash scripts/setup/bootstrap.sh
python src/pipelines/run.py --dry-run --max-items 1
```

## Supabase
- URL: `https://qufjlveukaoiokhpkhwj.supabase.co`
- 대상: `behavior_logs` 테이블

## 문서
- 전체 결정: `docs/ref/TECH-STACK-DECISIONS.md`
- 에이전트: `docs/ref/AGENT-OPERATING-MODEL.md`
- 미결 사항: `docs/ref/OPEN-DECISIONS.md`
- 파이프라인 다이어그램: `docs/status/PIPELINE-DIAGRAM.md`
