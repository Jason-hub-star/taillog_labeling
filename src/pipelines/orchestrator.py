"""Orchestrator — 에이전트 실행 순서 조율"""

import json
from datetime import datetime
from typing import List, Optional, Dict

from src.core.database import get_db
from src.core.models import BatchResult
from src.agents.collector import Collector
from src.agents.pose_extractor import PoseExtractor
from src.agents.behavior_classifier import BehaviorClassifier
from src.agents.abc_labeler import ABCLabeler
from src.agents.critic import Critic
from src.agents.quality_gate import QualityGate
from src.agents.sync_writer import SyncWriter
from src.agents.watchdog import Watchdog


class Orchestrator:
    """파이프라인 오케스트레이션"""

    def __init__(self):
        self.db = get_db()
        self.collector = Collector()
        self.pose_extractor = PoseExtractor()
        self.behavior_classifier = BehaviorClassifier()
        self.abc_labeler = ABCLabeler()
        self.critic = Critic()
        self.quality_gate = QualityGate()
        self.sync_writer = SyncWriter()
        self.watchdog = Watchdog()

    def run_full_pipeline(
        self,
        url: str,
        dry_run: bool = False,
    ) -> Optional[str]:
        """
        YouTube URL 기준 풀 파이프라인 실행

        Args:
            url: YouTube URL
            dry_run: True면 DB 저장 안 함

        Returns:
            run_id (성공) 또는 None (실패)
        """
        try:
            # Stage 1: Collect
            print(f"\n[Stage 1] Collecting: {url}")
            run = self.collector.run(url, dry_run)
            if not run:
                self.watchdog.log_failure("collector", url, "permanent", "다운로드 실패")
                return None

            run_id = run.id
            print(f"✓ Run created: {run_id}")

            # Stage 2: Extract Pose
            print(f"\n[Stage 2] Extracting pose: {run.video_path}")
            pose_success, pose_result_objs = self.pose_extractor.run(run.video_path, run_id, dry_run)
            if not pose_success:
                self.watchdog.log_failure("pose_extractor", run_id, "transient", "포즈 추출 실패")
                if not dry_run:
                    self.db.update(
                        "UPDATE labeling_runs SET status = ? WHERE id = ?",
                        ("failed", run_id),
                    )
                return None

            print(f"✓ Extracted {len(pose_result_objs)} frames")

            # Stage 3: Classify & Label
            # pose_result_objs: List[PoseResult] — dry_run 시 DB 저장 없으므로 메모리 직접 사용
            print(f"\n[Stage 3] Classifying and labeling")
            classified_count = 0
            for pr in pose_result_objs:
                keypoints_json = json.dumps(
                    [{"bodypart": kp.bodypart, "x": kp.x, "y": kp.y, "c": kp.c}
                     for kp in pr.keypoints]
                )
                label = self.behavior_classifier.run(
                    run_id,
                    pr.frame_id,
                    keypoints_json,
                    frame_path=pr.frame_path,
                    dry_run=dry_run,
                )
                if label:
                    classified_count += 1

                    if dry_run:
                        # dry_run: DB 미저장이므로 abc_labeler/critic 스킵
                        print(
                            f"  Frame {pr.frame_id}: {label.category}/{label.label} "
                            f"(conf={label.confidence:.2f}, dry_run=skip_abc_critic)"
                        )
                    else:
                        # Stage 4: ABC Labeler
                        abc_success = self.abc_labeler.run(label.id, dry_run)
                        if not abc_success:
                            self.watchdog.log_failure(
                                "abc_labeler",
                                label.id,
                                "transient",
                                "ABC 생성 실패",
                            )

                        # Stage 5: Critic
                        critic_pass = self.critic.run(label.id, dry_run)
                        print(
                            f"  Frame {pr.frame_id}: {label.category}/{label.label} "
                            f"(conf={label.confidence:.2f}, critic={'PASS' if critic_pass else 'FAIL'})"
                        )

            print(f"✓ Classified {classified_count}/{len(pose_result_objs)} frames")

            # Stage 6: Quality Gate
            print(f"\n[Stage 4] Quality Gate")
            gate_count = self.quality_gate.batch_process(run_id, dry_run)
            print(f"✓ Quality gate processed {gate_count} labels")

            # Stage 7: Sync
            print(f"\n[Stage 5] Syncing to Supabase")
            sync_success, sync_fail = self.sync_writer.batch_sync(run_id, dry_run)
            print(f"✓ Synced {sync_success} labels (failed: {sync_fail})")

            # Update run status
            if not dry_run:
                self.db.update(
                    "UPDATE labeling_runs SET status = ?, updated_at = ? WHERE id = ?",
                    ("synced", datetime.utcnow().isoformat(), run_id),
                )

            print(f"\n✅ Pipeline completed: {run_id}")
            return run_id

        except Exception as e:
            error_type, is_halt = self.watchdog.classify_failure(str(e))
            self.watchdog.log_failure(
                "orchestrator",
                url,
                error_type,
                str(e),
                is_halt,
            )
            if is_halt:
                raise

            return None

    def run_batch_pipeline(
        self,
        urls: List[str],
        max_items: Optional[int] = None,
        dry_run: bool = False,
    ) -> Dict[str, any]:
        """
        여러 URL 배치 처리 — BatchResult 패턴으로 부분 실패 허용.

        Args:
            urls: YouTube URL 리스트
            max_items: 최대 처리 개수 (None이면 전체)
            dry_run: True면 DB 저장 안 함

        Returns:
            {"success_count", "fail_count", "run_ids", "start_time", "end_time"}
        """
        items = urls[: max_items if max_items else len(urls)]
        batch: BatchResult[str] = BatchResult()  # str = run_id
        start_time = datetime.utcnow().isoformat()

        for i, url in enumerate(items, 1):
            print(f"\n{'='*60}")
            print(f"[{i}/{len(items)}] Processing: {url}")
            print(f"{'='*60}")

            try:
                run_id = self.run_full_pipeline(url, dry_run)
                if run_id:
                    batch.succeeded[url] = run_id
                else:
                    batch.failed[url] = RuntimeError("파이프라인 실패 (run_id 없음)")
            except Exception as e:
                # 단일 URL 실패가 전체 배치를 중단시키지 않음 (BatchResult 패턴)
                batch.failed[url] = e
                print(f"  ❌ URL 처리 실패 (계속 진행): {e}")

        if batch.failure_count > 0:
            print(f"\n⚠️ 배치 부분 실패: {batch.failure_count}건 실패, {batch.success_count}건 성공")

        return {
            "success_count": batch.success_count,
            "fail_count": batch.failure_count,
            "run_ids": list(batch.succeeded.values()),
            "start_time": start_time,
            "end_time": datetime.utcnow().isoformat(),
        }
