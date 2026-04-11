#!/usr/bin/env python3
"""
검증된 API 기반 재작성 (2026-04-11)
- 모델: yolov8n.pt (object detection) — yolov8n-pose.pt 아님
- 이유: yolov8n-pose.pt는 인간 자세 전용. 강아지에 적용 시 keypoint 무의미.
- 측정: 강아지 탐지율, bounding box confidence, 처리 속도
- keypoint 없음 — SuperAnimal과 비교 시 '탐지 능력' 기준으로만 비교
- 공식 API: model.predict(classes=[16], conf=...) / result.boxes.conf

참고:
  https://docs.ultralytics.com/tasks/detect/
  https://blog.roboflow.com/microsoft-coco-classes/  (class 16 = dog)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import psutil

try:
    import cv2
    from ultralytics import YOLO
except ImportError as exc:
    print("❌ 패키지 설치 필요: pip install ultralytics opencv-python")
    raise SystemExit(1) from exc

PROJECT_ROOT = Path(__file__).resolve().parents[2]
COCO_DOG_CLASS = 16  # COCO 클래스 16 = dog (0-indexed)


def process_frame_dir(
    model: YOLO,
    frame_dir: Path,
    video_name: str,
    conf: float,
) -> Optional[Dict]:
    """
    프레임 디렉토리에서 강아지 탐지 벤치마크.

    ⚠️ keypoint 측정 없음.
    yolov8n.pt는 object detection 모델이므로 bounding box + confidence만 측정.
    강아지 자세 keypoint는 SuperAnimal 결과와 비교.
    """
    frame_files = sorted(frame_dir.glob("frame_*.jpg"))
    if not frame_files:
        print(f"  ⚠️ 프레임 없음: {frame_dir}")
        return None

    detected_frames = 0
    confidence_scores: List[float] = []
    box_areas: List[float] = []  # 탐지된 강아지 bounding box 면적 (정규화)
    detections = []

    proc = psutil.Process()
    mem_before = proc.memory_info().rss / 1024 / 1024
    t_start = time.perf_counter()

    print(f"\n[YOLOv8n detect] {video_name}: {len(frame_files)} frames")

    for idx, frame_path in enumerate(frame_files):
        if idx % 10 == 0:
            print(f"  {idx}/{len(frame_files)}", end="\r")

        frame = cv2.imread(str(frame_path))
        if frame is None:
            continue
        h, w = frame.shape[:2]

        # 공식 API: classes=[16] → dog만 탐지
        results = model.predict(
            source=frame,
            classes=[COCO_DOG_CLASS],
            conf=conf,
            verbose=False,
        )

        frame_dogs = []
        for result in results:
            if result.boxes is None or len(result.boxes) == 0:
                continue
            for box in result.boxes:
                box_conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                area = ((x2 - x1) / w) * ((y2 - y1) / h)  # 화면 대비 비율

                confidence_scores.append(box_conf)
                box_areas.append(area)
                frame_dogs.append({
                    "conf": round(box_conf, 4),
                    "area_ratio": round(area, 4),
                    "bbox": [round(x1/w, 4), round(y1/h, 4), round(x2/w, 4), round(y2/h, 4)],
                })

        if frame_dogs:
            detected_frames += 1
            detections.append({"frame": idx, "file": str(frame_path), "dogs": frame_dogs})

    elapsed = time.perf_counter() - t_start
    mem_peak = proc.memory_info().rss / 1024 / 1024 - mem_before
    n = len(frame_files)

    result = {
        "video_name": video_name,
        "model": "yolov8n.pt",
        "note": "object detection only — no keypoints (pose model is human-only)",
        "total_frames": n,
        "detected_frames": detected_frames,
        "detection_rate_pct": round(detected_frames / n * 100, 1),
        "avg_confidence": round(float(np.mean(confidence_scores)) if confidence_scores else 0.0, 3),
        "avg_box_area_ratio": round(float(np.mean(box_areas)) if box_areas else 0.0, 4),
        "processing_time_sec": round(elapsed, 2),
        "avg_ms_per_frame": round(elapsed * 1000 / n, 1),
        "peak_memory_mb": round(mem_peak, 1),
        "detections": detections,
    }

    print(
        f"\n  탐지율: {result['detection_rate_pct']}%  |"
        f"  신뢰도: {result['avg_confidence']}  |"
        f"  속도: {result['avg_ms_per_frame']}ms/frame"
    )
    return result


def run(frames_dir: str, output_dir: str, conf: float) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    frames_root = Path(frames_dir)
    frame_dirs = sorted([d for d in frames_root.iterdir() if d.is_dir()])
    if not frame_dirs:
        print(f"❌ 프레임 디렉토리 없음: {frames_dir}")
        print("   download.py를 먼저 실행하세요.")
        return

    print("yolov8n.pt 로딩...")
    model = YOLO("yolov8n.pt")  # object detection (NOT pose)

    summary = {
        "model": "yolov8n.pt",
        "task": "object_detection",
        "coco_class_filtered": COCO_DOG_CLASS,
        "timestamp": datetime.now().isoformat(),
        "videos": {},
    }

    for frame_dir in frame_dirs:
        result = process_frame_dir(model, frame_dir, frame_dir.name, conf)
        if result:
            summary["videos"][frame_dir.name] = result
            json_path = out / f"{frame_dir.name}_yolo.json"
            json_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    (out / "yolo_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n✅ YOLOv8 결과 저장: {output_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description="YOLOv8n 강아지 탐지 벤치마크 (object detection)")
    parser.add_argument("--frames-dir", default=str(PROJECT_ROOT / "data/cache/compare/frames"))
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "data/cache/compare/yolo_results"))
    parser.add_argument("--conf", type=float, default=0.3)
    args = parser.parse_args()
    run(args.frames_dir, args.output_dir, args.conf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
