"""Critic 에이전트 — 최종 검수"""

import json
import uuid
from datetime import datetime
from typing import Optional

from src.core.database import get_db
from src.core.llm import get_ollama_client
from src.core.models import CriticOutput
from src.prompts.critic_prompt import build_critic_prompt, build_rule_based_critic_prompt


class Critic:
    """최종 검수 에이전트 (gemma4:26b)"""

    MODEL = "gemma4:26b-a4b-it-q4_K_M"
    RETRY_COUNT = 2

    def __init__(self):
        self.db = get_db()
        self.llm = get_ollama_client()

    def run(self, label_id: str, dry_run: bool = False) -> bool:
        """
        라벨 최종 검수

        Args:
            label_id: behavior_labels.id
            dry_run: True면 DB 저장 안 함

        Returns:
            통과 여부 (critic_pass 저장)
        """
        # 1. 라벨 조회
        result = self.db.execute_one(
            "SELECT * FROM behavior_labels WHERE id = ?", (label_id,)
        )
        if not result:
            print(f"라벨 없음: {label_id}")
            return False

        category = result["category"]
        label = result["label"]
        antecedent = result["antecedent"]
        behavior = result["behavior"]
        consequence = result["consequence"]
        intensity = result["intensity"]
        keypoint_quality = result["keypoint_quality"]

        # 2. LLM 호출 시도
        try:
            prompt = build_critic_prompt(
                category, label, antecedent, behavior, consequence, intensity, keypoint_quality
            )
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.chat(
                model=self.MODEL,
                messages=messages,
                temperature=0.1,
                retry_count=self.RETRY_COUNT,
            )
            result_dict = self.llm.parse_json_response(response["content"])
            critic_output = CriticOutput(**result_dict)

            pass_decision = critic_output.pass_decision
            confidence_adjusted = critic_output.confidence_adjusted
            exception_reason = critic_output.exception_reason

        except Exception as e:
            # LLM 실패 시 Rule-Based Fallback
            print(f"Critic LLM 실패, Rule-Based Fallback 사용: {str(e)}")
            pass_decision, confidence_adjusted, exception_reason = build_rule_based_critic_prompt(
                category, label, antecedent, behavior, consequence, intensity
            )

        # 3. DB 업데이트
        if not dry_run:
            self.db.update(
                """
                UPDATE behavior_labels
                SET critic_pass = ?, confidence = ?, critic_note = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    pass_decision,
                    confidence_adjusted,
                    exception_reason,
                    datetime.utcnow().isoformat(),
                    label_id,
                ),
            )

        return pass_decision
