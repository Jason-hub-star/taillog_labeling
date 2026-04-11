"""Pose Extractor 에이전트 — YOLOv8 객체 탐지 및 포즈 추출"""

import json
import os
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime
import uuid

try:
    import cv2
    from ultralytics import YOLO
except ImportError:
    cv2 = None
    YOLO = None

from src.core.database import get_db
from src.core.models import PoseResult, KeyPoint


class PoseExtractor:
    """YOLOv8n 기반 포즈 추출 에이전트"""

    # OD-07 미결: 현재 YOLOv8n object detection 사용 (bounding box만)
    # TODO: SuperAnimal keypoint detection으로 교체 예정
    MODEL_PATH = "yolov8n.pt"  # Object detection 모델
    COCO_DOG_CLASS = 16  # COCO dataset에서 개(dog) 클래스
    FRAME_RATE = 1  # 1 FPS
    BATCH_SIZE = 16
    CONFIDENCE_THRESHOLD = 0.5

    def __init__(self, cache_dir: str = "data/cache/pose_results"):
        self.cache_dir = cache_dir
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        self.db = get_db()
        self._model = None

    def _get_model(self):
        """모델 lazy loading"""
        if YOLO is None:
            raise RuntimeError("ultralytics 패키지 필요: pip install ultralytics")

        if self._model is None:
            self._model = YOLO(self.MODEL_PATH)
        return self._model

    def run(self, video_path: str, run_id: str, dry_run: bool = False) -> bool:
        """
        영상에서 1 FPS로 프레임 추출 후 강아지 탐지

        Args:
            video_path: 로컬 mp4 파일
            run_id: labeling_runs.id
            dry_run: True면 DB 저장 안 함

        Returns:
            성공 여부
        """
        if not os.path.exists(video_path):
            print(f"영상 파일 없음: {video_path}")
            return False

        try:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            if fps == 0:
                print(f"FPS 읽기 실패: {video_path}")
                return False

            frame_interval = int(fps / self.FRAME_RATE)  # 1 FPS 간격
            pose_results = []

            model = self._get_model()
            frame_id = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # 1 FPS로 샘플링
                if frame_id % frame_interval != 0:
                    frame_id += 1
                    continue

                # YOLOv8 탐지 (개 클래스만)
                results = model(frame, conf=self.CONFIDENCE_THRESHOLD, classes=[self.COCO_DOG_CLASS])

                if len(results) > 0 and len(results[0].boxes) > 0:
                    # 강아지 탐지됨 (현재 단일 강아지만 지원)
                    # OD-07이 미결이므로 placeholder로 17개 dummy keypoints 생성
                    # 향후 SuperAnimal로 교체 시 실제 keypoints로 대체

                    dummy_keypoints = self._generate_dummy_keypoints(frame.shape, results[0])
                    pose_result = PoseResult(
                        id=str(uuid.uuid4()),
                        run_id=run_id,
                        frame_id=frame_id,
                        keypoints=dummy_keypoints,
                        confidence=results[0].boxes[0].conf.item() if len(results[0].boxes) > 0 else 0.7,
                    )
                    pose_results.append(pose_result)

                frame_id += 1

            cap.release()

            # DB 저장
            if len(pose_results) == 0:
                print(f"강아지 탐지 실패 (discard): {run_id}")
                return False

            if not dry_run:
                for pose_result in pose_results:
                    keypoints_json = json.dumps(
                        [{"x": kp.x, "y": kp.y, "c": kp.c} for kp in pose_result.keypoints]
                    )
                    self.db.insert(
                        """
                        INSERT INTO pose_results
                        (id, run_id, frame_id, keypoints_json, confidence, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            pose_result.id,
                            pose_result.run_id,
                            pose_result.frame_id,
                            keypoints_json,
                            pose_result.confidence,
                            pose_result.created_at.isoformat(),
                        ),
                    )

            # 포즈 결과 캐시 저장
            cache_file = os.path.join(self.cache_dir, f"{run_id}_poses.json")
            with open(cache_file, "w") as f:
                json.dump(
                    [
                        {
                            "frame_id": pr.frame_id,
                            "keypoints": [{"x": kp.x, "y": kp.y, "c": kp.c} for kp in pr.keypoints],
                            "confidence": pr.confidence,
                        }
                        for pr in pose_results
                    ],
                    f,
                )

            return True

        except Exception as e:
            print(f"포즈 추출 오류: {str(e)}")
            return False

    def _generate_dummy_keypoints(self, frame_shape: tuple, detection_result) -> List[KeyPoint]:
        """
        OD-07 미결 중 사용할 dummy keypoints 생성
        실제로는 SuperAnimal keypoint detection으로 교체될 예정

        Args:
            frame_shape: (H, W, C)
            detection_result: YOLOv8 detection 결과

        Returns:
            17개 keypoints (COCO 표준)
        """
        h, w, _ = frame_shape

        # bounding box에서 대략적인 강아지 위치 추정
        if len(detection_result.boxes) > 0:
            box = detection_result.boxes[0]
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            box_center_x = (x1 + x2) / 2
            box_center_y = (y1 + y2) / 2
            box_width = x2 - x1
            box_height = y2 - y1
        else:
            box_center_x = w / 2
            box_center_y = h / 2
            box_width = w / 4
            box_height = h / 3

        # COCO 17 keypoints (대략적 배치)
        # 0-4: 왼쪽 다리, 5-9: 오른쪽 다리, 10-13: 머리, 14-16: 기타
        keypoints = []
        keypoint_offsets = [
            (-box_width / 4, box_height / 3),  # 왼쪽 앞다리
            (-box_width / 4, 0),
            (-box_width / 4, -box_height / 3),
            (box_width / 4, box_height / 3),  # 오른쪽 앞다리
            (box_width / 4, 0),
            (-box_width / 3, -box_height / 2),  # 머리
            (-box_width / 6, -box_height / 2),
            (box_width / 6, -box_height / 2),
            (box_width / 3, -box_height / 2),
            (-box_width / 4, -box_height / 4),
            (box_width / 4, -box_height / 4),
            (-box_width / 3, 0),
            (box_width / 3, 0),
            (-box_width / 2, -box_height / 2),
            (0, -box_height / 2),
            (box_width / 2, -box_height / 2),
            (0, box_height / 2),
        ]

        for dx, dy in keypoint_offsets:
            x = max(0.0, min(float(w), box_center_x + dx))
            y = max(0.0, min(float(h), box_center_y + dy))
            # TECH-STACK-DECISIONS A-06: 저장 포맷은 절대 픽셀 좌표 (0~W, 0~H)
            # 모델 입력 시에만 x/W, y/H 정규화 적용
            keypoints.append(KeyPoint(x=x, y=y, c=0.8))

        return keypoints
