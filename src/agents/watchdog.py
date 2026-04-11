"""Watchdog 에이전트 — 실패 처리 및 복구"""

import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class Watchdog:
    """실패 처리 및 모니터링 에이전트"""

    LOG_DIR = "data/exports/sync_logs"
    HALT_THRESHOLD = 10  # 연속 실패 임계값

    def __init__(self):
        Path(self.LOG_DIR).mkdir(parents=True, exist_ok=True)
        self._tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self._tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")

    def _notify(self, text: str):
        """Telegram 알림 전송 (실패해도 파이프라인 중단 안 함)"""
        if not self._tg_token or not self._tg_chat_id:
            return
        try:
            params = urllib.parse.urlencode({"chat_id": self._tg_chat_id, "text": text})
            url = f"https://api.telegram.org/bot{self._tg_token}/sendMessage?{params}"
            urllib.request.urlopen(url, timeout=5)
        except Exception:
            pass

    def log_failure(
        self,
        agent: str,
        label_id: str,
        error_type: str,
        error_msg: str,
        is_halt: bool = False,
    ):
        """
        실패 로그 기록

        Args:
            agent: 에이전트명 (collector, pose_extractor, etc.)
            label_id: 관련 라벨 ID
            error_type: transient, permanent, unknown
            error_msg: 에러 메시지
            is_halt: HALT 조건 여부
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent": agent,
            "label_id": label_id,
            "error_type": error_type,
            "error_msg": error_msg,
            "is_halt": is_halt,
        }

        log_file = os.path.join(self.LOG_DIR, "watchdog.log")
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        # HALT 조건 시 별도 파일 + Telegram 알림
        if is_halt:
            halt_file = os.path.join(
                self.LOG_DIR,
                f"HALT_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.log",
            )
            with open(halt_file, "w") as f:
                f.write(json.dumps(log_entry, indent=2))
            print(f"\n⚠️ HALT 조건 발생: {halt_file}")
            self._notify(f"🚨 HALT [{agent}]\n{error_msg}")
        elif error_type == "permanent":
            self._notify(f"❌ 영구오류 [{agent}]\n{error_msg[:200]}")

    def classify_failure(self, error_msg: str) -> Tuple[str, bool]:
        """
        실패 유형 분류

        Args:
            error_msg: 에러 메시지

        Returns:
            (error_type, is_halt)
            - error_type: transient, permanent, unknown
            - is_halt: HALT 조건 여부
        """
        transient_keywords = [
            "timeout",
            "rate limit",
            "connection refused",
            "temporarily unavailable",
            "oom",
        ]
        permanent_keywords = [
            "schema mismatch",
            "rls violation",
            "permission denied",
            "invalid json",
            "file not found",
        ]
        halt_keywords = [
            "schema mismatch",
            "rls violation",
            "permission denied",
            "file access error",
        ]

        error_lower = error_msg.lower()

        # HALT 먼저 확인
        if any(keyword in error_lower for keyword in halt_keywords):
            return "permanent", True

        # Transient 또는 Permanent 분류
        if any(keyword in error_lower for keyword in transient_keywords):
            return "transient", False
        elif any(keyword in error_lower for keyword in permanent_keywords):
            return "permanent", False
        else:
            return "unknown", False

    def get_retry_decision(
        self, error_type: str, attempt_count: int = 1
    ) -> Dict[str, any]:
        """
        재시도 의사결정

        Args:
            error_type: transient, permanent, unknown
            attempt_count: 현재 시도 횟수

        Returns:
            {
                "should_retry": bool,
                "backoff_seconds": int,
                "max_retries": int,
                "escalate_to_human": bool
            }
        """
        if error_type == "transient":
            max_retries = 3
            if attempt_count <= max_retries:
                backoff = 2 ** (attempt_count - 1)  # 1, 2, 4
                return {
                    "should_retry": True,
                    "backoff_seconds": backoff,
                    "max_retries": max_retries,
                    "escalate_to_human": False,
                }
            else:
                return {
                    "should_retry": False,
                    "backoff_seconds": 0,
                    "max_retries": max_retries,
                    "escalate_to_human": True,
                }

        elif error_type == "permanent":
            return {
                "should_retry": False,
                "backoff_seconds": 0,
                "max_retries": 0,
                "escalate_to_human": True,
            }

        else:  # unknown
            max_retries = 2
            if attempt_count <= max_retries:
                backoff = 60 * attempt_count  # 60s, 120s
                return {
                    "should_retry": True,
                    "backoff_seconds": backoff,
                    "max_retries": max_retries,
                    "escalate_to_human": False,
                }
            else:
                return {
                    "should_retry": False,
                    "backoff_seconds": 0,
                    "max_retries": max_retries,
                    "escalate_to_human": True,
                }

    def check_anomalies(self, db) -> List[Dict]:
        """
        이상 탐지 (CONFIDENCE-THRESHOLD-POLICY 기준)

        Args:
            db: Database 인스턴스

        Returns:
            [{"anomaly_type": "...", "severity": "...", "description": "..."}, ...]
        """
        anomalies = []

        # 1. 특정 label avg confidence < 0.5 (최근 50건)
        low_conf_check = db.execute(
            """
            SELECT preset_id, AVG(confidence) as avg_conf, COUNT(*) as cnt
            FROM behavior_labels
            WHERE created_at > datetime('now', '-1 day')
            GROUP BY preset_id
            HAVING avg_conf < 0.5 AND cnt >= 5
            """
        )
        for row in low_conf_check:
            anomalies.append(
                {
                    "anomaly_type": "low_confidence",
                    "severity": "MEDIUM",
                    "description": f"라벨 '{row['preset_id']}'의 평균 신뢰도가 낮음: {row['avg_conf']:.2f}",
                }
            )

        # 2. Rejection rate > 50% (최근 100건)
        recent_labels = db.execute(
            """
            SELECT review_status, COUNT(*) as cnt
            FROM behavior_labels
            WHERE created_at > datetime('now', '-6 hours')
            GROUP BY review_status
            """
        )
        total_recent = sum(row["cnt"] for row in recent_labels)
        rejected_count = next(
            (row["cnt"] for row in recent_labels if row["review_status"] == "rejected"), 0
        )
        if total_recent >= 100 and rejected_count / total_recent > 0.5:
            anomalies.append(
                {
                    "anomaly_type": "high_rejection_rate",
                    "severity": "HIGH",
                    "description": f"거부율이 높음: {rejected_count / total_recent * 100:.1f}%",
                }
            )

        # 3. human_review 누적 > 500건 미검수
        pending_human_review = db.execute_one(
            """
            SELECT COUNT(*) as cnt FROM behavior_labels
            WHERE review_status = 'human_review'
            """
        )
        if pending_human_review and pending_human_review["cnt"] > 500:
            anomalies.append(
                {
                    "anomaly_type": "pending_human_review_backlog",
                    "severity": "MEDIUM",
                    "description": f"미검수 human_review: {pending_human_review['cnt']}건",
                }
            )

        return anomalies

    def generate_status_report(self, db) -> Dict:
        """
        상태 리포트 생성

        Args:
            db: Database 인스턴스

        Returns:
            리포트 딕셔너리
        """
        # 총 라벨 수
        total_labels = db.execute_one("SELECT COUNT(*) as cnt FROM behavior_labels")[
            "cnt"
        ]

        # 상태별 분류
        status_breakdown = db.execute(
            """
            SELECT review_status, COUNT(*) as cnt FROM behavior_labels
            GROUP BY review_status
            """
        )

        # 평균 신뢰도
        avg_confidence = db.execute_one(
            "SELECT AVG(confidence) as avg_conf FROM behavior_labels"
        )

        # 카테고리별 분류
        category_breakdown = db.execute(
            """
            SELECT category, COUNT(*) as cnt FROM behavior_labels
            GROUP BY category
            """
        )

        # 최근 실패 (최근 24시간) — error_msg는 plain text이므로 json_extract 미사용
        recent_failures = db.execute(
            """
            SELECT COUNT(*) as cnt FROM sync_attempts
            WHERE success = 0
            AND attempt_at > datetime('now', '-1 day')
            """
        )

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_labels": total_labels,
            "status_breakdown": {row["review_status"]: row["cnt"] for row in status_breakdown},
            "avg_confidence": avg_confidence["avg_conf"] if avg_confidence else 0,
            "category_breakdown": {row["category"]: row["cnt"] for row in category_breakdown},
            "recent_failures_24h": (recent_failures[0]["cnt"] if recent_failures else 0),
            "anomalies": self.check_anomalies(db),
        }
