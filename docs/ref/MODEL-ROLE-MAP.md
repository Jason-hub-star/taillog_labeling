# Model Role Map — LLM 역할 분담 SSOT

> vibehub-media `LLM-ORCHESTRATION-MAP.md` 패턴 이식.
> 어떤 단계에 어떤 모델을 사용하는지, shadow 정책, promote 사이클을 정의한다.

---

## 역할 분담 테이블

| 단계 | 역할 | 모델 | 우선순위 | 이유 |
|------|------|------|---------|------|
| pose_extraction | 키포인트 추출 | YOLOv8n-pose (local) | deterministic | 규칙 기반, LLM 불필요 |
| behavior_classifier | 행동 1차 분류 | `gemma4-unsloth-e4b:latest` | 속도 | 반복 작업, 비용 최소화 |
| abc_labeler | ABC 구조화 | `gemma4-unsloth-e4b:latest` | 속도 | 반복 작업 |
| critic | 품질 검수 | `gemma4:26b-a4b-it-q4_K_M` | 정확도 | 최종 게이트 |
| quality_gate | 신뢰도 필터 | rule engine (Python) | deterministic | 임계값 기계적 적용 |
| sync_writer | Supabase sync | rule engine (Python) | deterministic | 데이터 이동, LLM 불필요 |
| watchdog | 실패 감시 | rule engine (Python) | deterministic | 상태 관리 |

---

## Shadow Mode 정책

### 초기 (0~200건)
- **critic**은 `gemma4:26b`를 사용하지만 결과를 기록만 함
- sync 여부는 `confidence` 계산식에만 의존
- critic 결과를 별도 컬럼(`critic_pass_shadow`)에 저장

### 전환 조건 (200건 이후)
- shadow critic pass rate ≥ 90%이면 **critic active mode** 전환
- critic fail 시 `human_review` 강제 (sync 차단)

### Active Mode (200건 이후)
- critic pass → quality_gate 진행
- critic fail → human_review (confidence와 무관)

---

## Promote 사이클

```
eval → shadow → activate → (rollback 준비)
```

1. **eval**: 새 모델 50건 샘플 평가 (기존 모델과 비교)
2. **shadow**: 새 모델 결과 기록만, 기존 모델이 운영 계속
3. **activate**: shadow pass rate ≥ 95% 확인 후 주인님 승인 → 새 모델로 전환
4. **rollback 준비**: 이전 모델 설정 보존, 오류 급증 시 1분 내 롤백 가능

---

## Fallback 정책

| 단계 | 주 모델 | fallback | 조건 |
|------|--------|---------|------|
| behavior_classifier | gemma4-unsloth | rule-based (intensity만) | Ollama 연결 실패 |
| abc_labeler | gemma4-unsloth | critic에 partial 전달 | 응답 파싱 실패 |
| critic | gemma4:26b | rule-based critic | Ollama 연결 실패 |

---

## 자동 rollback 트리거 (watchdog 기준)

| 지표 | 임계값 | 조치 |
|------|--------|------|
| LLM 응답 실패율 | > 20% (최근 100건) | watchdog alert + human review |
| parse error율 | > 30% (최근 50건) | 모델 재시작 요청 |
| critic pass rate | < 70% (최근 100건) | shadow mode 강제 복귀 |
| 평균 응답 시간 | > 30초 | gemma4-unsloth fallback |

---

## 모델 파일 정보

| 모델 | 크기 | 위치 | 확인 명령 |
|------|------|------|---------|
| YOLOv8n-pose | ~70MB | `data/models/yolov8n-pose.pt` | `python -c "from ultralytics import YOLO; YOLO('yolov8n-pose.pt')"` |
| gemma4-unsloth-e4b | ~5GB | Ollama 내부 | `ollama list` |
| gemma4:26b | ~17GB | Ollama 내부 | `ollama list` |
