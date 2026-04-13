"""Pose Extractor 에이전트 — SuperAnimal-Quadruped 키포인트 추출 (M2)

아키텍처:
  - DLC는 .venv_dlc 격리 환경에서만 동작 → subprocess 호출
  - 진입점: Config.SUPERANIMAL_INFER_SCRIPT (scripts/superanimal_infer.py)
  - 결과: A-07 포맷 JSON → SQLite pose_results + 캐시 파일
"""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import List
import uuid

from src.core.database import get_db
from src.core.models import PoseResult, KeyPoint
from src.utils.config import Config


class PoseExtractor:
    """SuperAnimal-Quadruped 기반 포즈 추출 에이전트 (A-01, A-07)"""

    _TRANSIENT = (ConnectionError, TimeoutError, OSError)

    def __init__(self, cache_dir: str = "data/cache/pose_results"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db = get_db()

    def run(
        self,
        video_path: str,
        run_id: str,
        dry_run: bool = False,
        save_training_data: bool = True,
    ) -> tuple[bool, List[PoseResult]]:
        """
        단일 영상 포즈 추출.

        Args:
            video_path: 로컬 mp4 파일 경로
            run_id: labeling_runs.id
            dry_run: True면 DB 저장 안 함

        Returns:
            (성공 여부, PoseResult 리스트) — dry_run=True여도 결과 반환
        """
        video = Path(video_path)
        if not video.exists():
            print(f"영상 파일 없음: {video_path}")
            return False, []

        try:
            frames = self._run_superanimal(video, save_training_data=save_training_data)
        except Exception as exc:
            print(f"SuperAnimal 추론 오류: {exc}")
            return False, []

        if not frames:
            print(f"포즈 추출 결과 없음 (discard): {run_id}")
            return False, []

        pose_results = self._build_pose_results(frames, run_id)

        if not dry_run:
            self._save_to_db(pose_results)

        self._save_cache(pose_results, run_id)
        return True, pose_results

    # ── 내부 메서드 ────────────────────────────────────────────────────────────

    def _run_superanimal(
        self, video: Path, save_training_data: bool = True
    ) -> List[dict]:
        """
        .venv_dlc subprocess로 superanimal_infer.py 실행.
        결과 JSON 파일을 읽어 프레임 리스트 반환.

        A-07: 출력 포맷 [{"frame_id": int, "keypoints": [{bodypart, x, y, c}...]}]
        A-09: save_training_data=True면 프레임 이미지 + YOLO 라벨 저장
        """
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            output_path = Path(tmp.name)

        cmd = [
            str(Config.DLC_VENV_PYTHON),
            str(Config.SUPERANIMAL_INFER_SCRIPT),
            "--video", str(video),
            "--output", str(output_path),
        ]

        # A-09: 학습 데이터 저장 경로 전달 (영상 삭제 전 프레임 추출)
        if save_training_data:
            cmd.extend([
                "--training-frames-dir", str(Config.TRAINING_FRAMES_DIR),
                "--training-labels-dir", str(Config.TRAINING_LABELS_DIR),
            ])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 최대 1시간 (CPU 추론: 9분 영상 ≈ 540프레임, 600s 부족 확인됨)
            )

            if result.returncode != 0:
                print(f"superanimal_infer 오류:\n{result.stderr}")
                return []

            if not output_path.exists():
                print("superanimal_infer: 출력 파일 없음")
                return []

            return json.loads(output_path.read_text(encoding="utf-8"))

        finally:
            output_path.unlink(missing_ok=True)

    def _build_pose_results(self, frames: List[dict], run_id: str) -> List[PoseResult]:
        """A-07 프레임 리스트 → PoseResult 리스트 변환."""
        results = []
        for frame in frames:
            keypoints = [
                KeyPoint(
                    bodypart=kp["bodypart"],
                    x=kp["x"],
                    y=kp["y"],
                    c=kp["c"],
                )
                for kp in frame["keypoints"]
            ]

            if not keypoints:
                continue

            avg_conf = sum(kp.c for kp in keypoints) / len(keypoints)
            frame_id = frame["frame_id"]
            frame_path = Config.TRAINING_FRAMES_DIR / f"{frame_id:06d}.jpg"
            results.append(
                PoseResult(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    frame_id=frame_id,
                    keypoints=keypoints,
                    confidence=avg_conf,
                    frame_path=str(frame_path) if frame_path.exists() else None,
                )
            )
        return results

    def _save_to_db(self, pose_results: List[PoseResult]) -> None:
        """SQLite pose_results 테이블에 INSERT."""
        for pose_result in pose_results:
            keypoints_json = json.dumps(
                [{"bodypart": kp.bodypart, "x": kp.x, "y": kp.y, "c": kp.c}
                 for kp in pose_result.keypoints]
            )
            self.db.insert(
                """
                INSERT INTO pose_results
                (id, run_id, frame_id, keypoints_json, confidence, frame_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pose_result.id,
                    pose_result.run_id,
                    pose_result.frame_id,
                    keypoints_json,
                    pose_result.confidence,
                    pose_result.frame_path,
                    pose_result.created_at.isoformat(),
                ),
            )

    def _save_cache(self, pose_results: List[PoseResult], run_id: str) -> None:
        """JSON 캐시 파일 저장."""
        cache_file = self.cache_dir / f"{run_id}_poses.json"
        cache_file.write_text(
            json.dumps(
                [
                    {
                        "frame_id": pr.frame_id,
                        "keypoints": [
                            {"bodypart": kp.bodypart, "x": kp.x, "y": kp.y, "c": kp.c}
                            for kp in pr.keypoints
                        ],
                        "confidence": pr.confidence,
                    }
                    for pr in pose_results
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
