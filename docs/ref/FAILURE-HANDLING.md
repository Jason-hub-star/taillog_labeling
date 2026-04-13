# Failure Handling — SSOT

> 실패 유형·retry 정책·escalation 경로 정의.
> watchdog 에이전트는 이 문서만 참조한다.

---

## 실패 유형 분류

### Transient (자동 복구 가능)
| 원인 | 예시 | retry 정책 |
|------|------|-----------|
| Network timeout | YouTube 다운로드 중단 | exponential backoff (1s→2s→4s), max 3회 |
| Rate limit | yt-dlp 429 응답 | 30분 대기 후 1회 retry |
| GPU OOM (SuperAnimal) | pose_extractor DLC 추론 중 OOM | `--device cpu` 폴백 후 즉시 재시도 (A-08) |
| Ollama timeout | LLM 응답 지연 | 60초 timeout, 3회 retry |
| Supabase connection | DB 연결 실패 | 1s→2s→4s, max 3회 |

### Permanent (수동 개입 필요)
| 원인 | 예시 | 처리 |
|------|------|------|
| Invalid data | pose_results JSON 파손 | `rejected` + watchdog 로그 |
| Schema mismatch | Supabase 컬럼 없음 | **HALT** + Telegram 즉시 알림 |
| RLS violation | service_role인데 403 | **HALT** + Telegram 즉시 알림 |
| LLM parse error (persistent) | 10회 연속 parse 실패 | 모델 재시작 요청 |

### Unknown (조사 필요)
| 원인 | 처리 |
|------|------|
| 예상 외 예외 | investigation queue + Telegram alert |
| 파이프라인 hang | watchdog가 30분 비활성 감지 후 SIGTERM + alert |

---

## 에이전트별 실패 처리

| 에이전트 | 실패 | 조치 |
|---------|------|------|
| collector | YouTube geo-block | 영상 skip + source policy 업데이트 |
| collector | Private video | 영상 skip (정상, 기록만) |
| pose_extractor | 0 detections | discard (watchdog 통지 없음) |
| pose_extractor | GPU OOM (SuperAnimal) | `--device cpu` 폴백 후 재시도 (A-08) |
| behavior_classifier | LLM timeout | retry 3회 → watchdog |
| behavior_classifier | Parse error | critic에 raw_response 전달 |
| abc_labeler | Partial response | critic mandatory |
| critic | LLM failure | rule-based fallback |
| sync_writer | Connection error | retry 3회 → watchdog |
| sync_writer | Schema mismatch | HALT |

---

## Watchdog 알림 채널

| 심각도 | 채널 | 예시 |
|--------|------|------|
| LOW | SQLite 로그만 | 영상 skip, LLM retry |
| MEDIUM | Telegram (OD-04 설정 후) | 연속 실패, 신뢰도 급락 |
| HIGH | Telegram + HALT | HALT 조건 (schema mismatch, RLS 오류) |

> **OD-04 미결**: Telegram 봇 토큰 미설정. Phase 1 완료 후 구성.
> 임시: 로컬 로그 파일 (`data/exports/sync_logs/watchdog.log`)로 대체.

---

## HALT 조건 (파이프라인 강제 중단)

다음 조건에서 파이프라인이 즉시 중단된다:
1. Supabase schema mismatch (컬럼 불일치)
2. service_role RLS violation
3. SQLite DB 파일 접근 불가
4. `behavior_labels` INSERT 연속 10회 실패
5. watchdog 자체 오류

HALT 시:
- `data/exports/sync_logs/HALT_<timestamp>.log` 생성
- 모든 in-progress 작업 중단 (commit 없음)
- 다음 실행은 수동 확인 후만 재시작

---

## 재시작 절차

```bash
# 1. 오류 로그 확인
cat data/exports/sync_logs/watchdog.log | tail -50

# 2. HALT 원인 파악
python scripts/manual/inspect-db.py --status failed --limit 10

# 3. 원인 해결 후 재시작
python src/pipelines/run.py --resume-from <run_id>
```
