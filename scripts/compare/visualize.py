"""
YOLOv8 vs SuperAnimal 비교 시각화 + 리포트 생성
결과: data/exports/compare_report.md + 나란히 비교 이미지
"""

import os
import json
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, Optional

import cv2


# COCO 17 keypoint 연결선 (YOLOv8)
YOLO_SKELETON = [
    (0, 1), (0, 2), (1, 3), (2, 4),          # 머리
    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),  # 앞다리
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),  # 뒷다리
    (5, 11), (6, 12),                          # 몸통
]

# SuperAnimal 39-point (quadruped) 연결선
SUPERANIMAL_SKELETON = [
    (0, 1), (1, 2), (2, 3), (3, 4),   # 척추
    (4, 5), (5, 6),                    # 꼬리
    (7, 8), (8, 9),                    # 왼앞다리
    (10, 11), (11, 12),                # 오른앞다리
    (13, 14), (14, 15),                # 왼뒷다리
    (16, 17), (17, 18),                # 오른뒷다리
]


def draw_keypoints(
    image: np.ndarray,
    keypoints: list,
    color: Tuple = (0, 255, 0),
    skeleton: list = None,
    denorm: bool = True,
) -> np.ndarray:
    h, w = image.shape[:2]
    vis = image.copy()

    # keypoint 좌표 변환
    pts = []
    for kpt in keypoints:
        x = kpt.get("x", 0)
        y = kpt.get("y", 0)
        c = kpt.get("conf", kpt.get("likelihood", 1.0))
        if denorm:
            x, y = int(x * w), int(y * h)
        else:
            x, y = int(x), int(y)
        pts.append((x, y, c))

    # 연결선
    if skeleton:
        for a, b in skeleton:
            if a < len(pts) and b < len(pts):
                x1, y1, c1 = pts[a]
                x2, y2, c2 = pts[b]
                if c1 > 0.1 and c2 > 0.1:
                    cv2.line(vis, (x1, y1), (x2, y2), color, 1, cv2.LINE_AA)

    # keypoint 점
    for x, y, c in pts:
        if c > 0.1:
            cv2.circle(vis, (x, y), 4, color, -1, cv2.LINE_AA)

    return vis


def load_results(yolo_dir: str, superanimal_dir: str) -> Tuple[Dict, Dict]:
    yolo = {}
    for f in Path(yolo_dir).glob("*_yolo.json"):
        with open(f) as jf:
            name = f.stem.replace("_yolo", "")
            yolo[name] = json.load(jf)

    superanimal = {}
    for f in Path(superanimal_dir).glob("*_superanimal.json"):
        with open(f) as jf:
            name = f.stem.replace("_superanimal", "")
            superanimal[name] = json.load(jf)

    return yolo, superanimal


def create_comparison_images(
    yolo_results: Dict,
    superanimal_results: Dict,
    output_dir: str = "data/exports/compare_images",
    max_images: int = 5,
):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    saved = 0

    for video_name, yolo_data in yolo_results.items():
        sa_data = superanimal_results.get(video_name)
        if not sa_data:
            continue

        # detection이 있는 프레임만
        yolo_dets = {d["frame"]: d for d in yolo_data.get("detections", [])}
        sa_dets = {d["frame"]: d for d in sa_data.get("detections", [])}

        common_frames = sorted(set(yolo_dets) & set(sa_dets))[:max_images]

        for frame_idx in common_frames:
            yolo_det = yolo_dets[frame_idx]
            sa_det = sa_dets[frame_idx]

            frame_path = yolo_det["file"]
            frame = cv2.imread(frame_path)
            if frame is None:
                continue

            # 두 모델 keypoint 그리기
            yolo_vis = draw_keypoints(frame, yolo_det["keypoints"], (0, 220, 0), YOLO_SKELETON)
            sa_vis = draw_keypoints(frame, sa_det["keypoints"], (220, 0, 0), SUPERANIMAL_SKELETON)

            # 레이블
            for img, label, color in [(yolo_vis, "YOLOv8n-pose", (0, 220, 0)), (sa_vis, "SuperAnimal", (220, 0, 0))]:
                cv2.rectangle(img, (0, 0), (250, 32), (0, 0, 0), -1)
                cv2.putText(img, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

            comparison = np.hstack([yolo_vis, sa_vis])
            out_path = Path(output_dir) / f"{video_name}_frame{frame_idx:04d}.jpg"
            cv2.imwrite(str(out_path), comparison)
            saved += 1

    print(f"  비교 이미지 {saved}장 저장: {output_dir}")


def aggregate(results: Dict) -> Dict:
    det_rates, confs, kpt_valids, speeds, mems = [], [], [], [], []
    for v in results.values():
        det_rates.append(v.get("detection_rate_pct", v.get("detection_rate", 0)))
        confs.append(v.get("avg_confidence", 0))
        kpt_valids.append(v.get("keypoint_validity_pct", 0))
        speeds.append(v.get("avg_ms_per_frame", 0))
        mems.append(v.get("peak_memory_mb", 0))
    return {
        "det_rate": round(float(np.mean(det_rates)), 1) if det_rates else 0,
        "confidence": round(float(np.mean(confs)), 3) if confs else 0,
        "kpt_valid": round(float(np.mean(kpt_valids)), 1) if kpt_valids else 0,
        "speed_ms": round(float(np.mean(speeds)), 1) if speeds else 0,
        "memory_mb": round(float(np.mean(mems)), 1) if mems else 0,
    }


def generate_report(
    yolo_results: Dict,
    superanimal_results: Dict,
    output_dir: str = "data/exports",
) -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    ym = aggregate(yolo_results)
    sm = aggregate(superanimal_results)

    def winner(y, s, higher_better=True):
        if higher_better:
            return "🟢 SuperAnimal" if s > y else "🟢 YOLOv8"
        else:
            return "🟢 SuperAnimal" if s < y else "🟢 YOLOv8"

    lines = [
        "# YOLOv8n-pose vs SuperAnimal-Quadruped 비교 리포트\n",
        f"> 생성: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n",
        "## 종합 비교\n\n",
        "| 지표 | YOLOv8n-pose | SuperAnimal | 승자 |\n",
        "|------|-------------|-------------|------|\n",
        f"| 탐지율 (%) | {ym['det_rate']} | {sm['det_rate']} | {winner(ym['det_rate'], sm['det_rate'])} |\n",
        f"| 평균 신뢰도 | {ym['confidence']} | {sm['confidence']} | {winner(ym['confidence'], sm['confidence'])} |\n",
        f"| Keypoint 유효율 (%) | {ym['kpt_valid']} | {sm['kpt_valid']} | {winner(ym['kpt_valid'], sm['kpt_valid'])} |\n",
        f"| 처리 속도 (ms/frame) | {ym['speed_ms']} | {sm['speed_ms']} | {winner(ym['speed_ms'], sm['speed_ms'], False)} |\n",
        f"| 메모리 (MB) | {ym['memory_mb']} | {sm['memory_mb']} | {winner(ym['memory_mb'], sm['memory_mb'], False)} |\n",
        "\n## 영상별 상세\n\n",
    ]

    for vname in yolo_results:
        yv = yolo_results[vname]
        sv = superanimal_results.get(vname, {})
        lines.append(f"### {vname}\n\n")
        lines.append(f"| | YOLOv8n-pose | SuperAnimal |\n|--|--|--|\n")
        ydet = yv.get('detection_rate_pct', yv.get('detection_rate', 0))
        sdet = sv.get('detection_rate_pct', sv.get('detection_rate', '-')) if sv else '-'
        lines.append(f"| 탐지율 | {ydet}% | {sdet}% |\n")
        lines.append(f"| 신뢰도 | {yv.get('avg_confidence',0)} | {sv.get('avg_confidence','-')} |\n")
        lines.append(f"| 속도 | {yv.get('avg_ms_per_frame',0)}ms | {sv.get('avg_ms_per_frame','-')}ms |\n\n")

    # 최종 권장
    lines.append("## 🎯 최종 권장\n\n")

    if not superanimal_results:
        lines += [
            "⚠️ **SuperAnimal 미실행** — deeplabcut이 Python 3.14와 호환되지 않음\n\n",
            "- 원인: `tables==3.8.0` + `numpy<2.0` 요구 (Python 3.14 미지원)\n",
            "- YOLOv8 단독 결과 기준 판단:\n\n",
            f"  - 평균 탐지율: **{ym['det_rate']}%** (목표 80% 대비 매우 낮음)\n",
            "  - 소형견(포메라니안) 8.3%, 홈캠 6.7% → 실용 수준 미달\n\n",
            "**→ SuperAnimal 채택 권장 (YOLOv8 탐지율 불충분)**\n\n",
            "- deeplabcut 설치 가능 환경 필요 (Python 3.10 또는 3.11 가상환경)\n",
            "- `OPEN-DECISIONS.md` OD-07 → resolved 처리 예정\n",
            "- `TECH-STACK-DECISIONS.md` A-01 → SuperAnimal 채택으로 업데이트 필요\n",
        ]
    else:
        det_diff = sm["det_rate"] - ym["det_rate"]
        if det_diff >= 15:
            lines += [
                "**→ SuperAnimal 채택 권장**\n\n",
                f"- 탐지율이 YOLOv8 대비 {det_diff:.1f}%p 높음\n",
                "- 소형견 성능 우수\n",
                "- `TECH-STACK-DECISIONS.md` A-01 → SuperAnimal로 업데이트 필요\n",
                "- keypoint 포맷: COCO 17pt → SuperAnimal quadruped pt로 파이프라인 변경\n",
            ]
        elif det_diff <= -5:
            lines += [
                "**→ YOLOv8n-pose 유지**\n\n",
                "- 탐지율이 SuperAnimal 이상\n",
                "- 처리 속도 빠름, 기존 스택 호환\n",
                "- `TECH-STACK-DECISIONS.md` A-01 확정\n",
            ]
        else:
            lines += [
                f"**→ 성능 유사 ({det_diff:+.1f}%p) — 속도 기준 YOLOv8 권장**\n\n",
                "- 탐지율 차이 미미\n",
                "- YOLOv8이 더 빠르고 기존 스택과 호환\n",
                "- `TECH-STACK-DECISIONS.md` A-01 확정\n",
            ]

    report_path = Path(output_dir) / "compare_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print(f"✅ 리포트 저장: {report_path}")
    return str(report_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--yolo-dir", default="data/cache/compare/yolo_results")
    parser.add_argument("--superanimal-dir", default="data/cache/compare/superanimal_results")
    parser.add_argument("--output-dir", default="data/exports")
    parser.add_argument("--max-images", type=int, default=5)
    args = parser.parse_args()

    yolo_results, superanimal_results = load_results(args.yolo_dir, args.superanimal_dir)

    if not yolo_results:
        print("❌ YOLOv8 결과 없음. run_yolo.py 먼저 실행하세요.")
        exit(1)

    if superanimal_results:
        create_comparison_images(yolo_results, superanimal_results, args.output_dir + "/compare_images", args.max_images)

    generate_report(yolo_results, superanimal_results, args.output_dir)
