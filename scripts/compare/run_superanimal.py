#!/usr/bin/env python3
"""
검증된 API 기반 재작성 (2026-04-11)
- 핵심 API: deeplabcut.video_inference_superanimal() — 비디오 파일 단위 처리
- 입력: 비디오 파일 (프레임 디렉토리 아님)
- 출력: H5 파일 (프레임별 keypoint DataFrame)
- 모델 다운로드: dlclibrary.download_huggingface_model()

설치:
  pip install dlclibrary
  pip install "deeplabcut[modelzoo]"   # video_inference_superanimal 포함

참고:
  https://github.com/DeepLabCut/DLClibrary
  https://deeplabcut.github.io/DeepLabCut/docs/ModelZoo.html
  https://github.com/DeepLabCut/DeepLabCut/blob/main/examples/COLAB/COLAB_DEMO_SuperAnimal.ipynb
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

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUPERANIMAL_NAME = "superanimal_quadruped"
MODEL_NAME = "hrnet_w32"
DETECTOR_NAME = "fasterrcnn_resnet50_fpn_v2"


def _check_deps() -> tuple:
    """dlclibrary, deeplabcut, pandas 설치 여부 확인."""
    try:
        import dlclibrary  # noqa: F401
    except ImportError:
        print("❌ dlclibrary 미설치: pip install dlclibrary")
        raise SystemExit(1)

    try:
        import deeplabcut  # noqa: F401
    except ImportError:
        print('❌ deeplabcut 미설치: pip install "deeplabcut[modelzoo]"')
        raise SystemExit(1)

    try:
        import pandas  # noqa: F401
    except ImportError:
        print("❌ pandas 미설치: pip install pandas tables")
        raise SystemExit(1)

    import deeplabcut
    import dlclibrary
    import pandas
    return dlclibrary, deeplabcut, pandas


def ensure_model_downloaded(model_cache_dir: Path) -> None:
    """
    superanimal_quadruped 모델을 로컬에 다운로드.
    이미 있으면 스킵.
    """
    dlclibrary, _, _ = _check_deps()

    marker = model_cache_dir / ".downloaded"
    if marker.exists():
        print(f"  모델 캐시 존재: {model_cache_dir}")
        return

    model_cache_dir.mkdir(parents=True, exist_ok=True)
    print(f"  superanimal_quadruped 다운로드 중 (최초 1회, 수 분 소요)...")

    # 검증된 API: download_huggingface_model(dataset_name, target_dir)
    dlclibrary.download_huggingface_model(SUPERANIMAL_NAME, model_cache_dir)
    marker.touch()
    print("  ✅ 다운로드 완료")


def run_inference_on_video(
    deeplabcut,
    video_path: Path,
    output_dir: Path,
) -> Optional[Path]:
    """
    단일 비디오에 superanimal_quadruped 추론 실행.
    결과: H5 파일 경로 반환.

    검증된 API:
      deeplabcut.video_inference_superanimal(
          videos=[str],
          superanimal_name="superanimal_quadruped",
          model_name="hrnet_w32",
          detector_name="fasterrcnn_resnet50_fpn_v2",
          video_adapt=False,
      )
    H5 출력 파일은 video_path와 같은 디렉토리에 생성됨.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # DeepLabCut은 비디오와 같은 폴더에 결과 저장 → 비디오를 output_dir에 복사하거나
    # video_path 자체가 output_dir 안에 있어야 함.
    # 여기서는 symlink 또는 원본 경로 그대로 사용.
    print(f"  SuperAnimal 추론: {video_path.name}")
    t_start = time.perf_counter()

    try:
        deeplabcut.video_inference_superanimal(
            videos=[str(video_path)],
            superanimal_name=SUPERANIMAL_NAME,
            model_name=MODEL_NAME,
            detector_name=DETECTOR_NAME,
            video_adapt=False,  # True 시 도메인 적응 (느림)
        )
    except Exception as exc:
        print(f"  ❌ 추론 실패: {exc}")
        return None

    elapsed = time.perf_counter() - t_start
    print(f"  추론 완료: {elapsed:.1f}초")

    # 생성된 H5 파일 찾기 (video_path 디렉토리 또는 현재 디렉토리)
    search_dirs = [video_path.parent, Path(".")]
    for search_dir in search_dirs:
        h5_files = list(search_dir.glob(f"{video_path.stem}*DLC*.h5"))
        if h5_files:
            h5_path = sorted(h5_files)[-1]  # 가장 최신 파일
            print(f"  H5 파일: {h5_path}")
            return h5_path

    print("  ⚠️ H5 파일을 찾지 못했습니다.")
    return None


def parse_h5_to_metrics(pandas, h5_path: Path, video_name: str, n_frames: int) -> Dict:
    """
    H5 파일에서 프레임별 keypoint 추출 및 지표 계산.

    H5 구조: MultiIndex DataFrame (scorer, bodypart, coords)
    coords: x, y, likelihood
    """
    df = pandas.read_hdf(str(h5_path))

    # scorer 이름 (첫 번째 레벨)
    scorer = df.columns.get_level_values(0)[0]
    bodyparts = df.columns.get_level_values(1).unique().tolist()

    print(f"  Bodyparts ({len(bodyparts)}개): {bodyparts[:5]}...")

    detected_frames = 0
    all_likelihoods: List[float] = []
    frame_results = []

    for frame_idx in range(len(df)):
        row = df.iloc[frame_idx]
        frame_likelihoods = []

        kpt_list = []
        for bp in bodyparts:
            try:
                x = float(row[(scorer, bp, "x")])
                y = float(row[(scorer, bp, "y")])
                likelihood = float(row[(scorer, bp, "likelihood")])
                kpt_list.append({"bodypart": bp, "x": x, "y": y, "likelihood": likelihood})
                frame_likelihoods.append(likelihood)
            except KeyError:
                continue

        if frame_likelihoods:
            avg_likelihood = float(np.mean(frame_likelihoods))
            valid_kpts = sum(1 for l in frame_likelihoods if l > 0.1)

            if avg_likelihood > 0.1:
                detected_frames += 1
                all_likelihoods.extend(frame_likelihoods)

            frame_results.append({
                "frame": frame_idx,
                "avg_likelihood": round(avg_likelihood, 4),
                "valid_keypoints": valid_kpts,
                "total_keypoints": len(frame_likelihoods),
                "keypoints": kpt_list,
            })

    total_frames = len(df)
    valid_lkh = [l for l in all_likelihoods if l > 0.1]

    return {
        "video_name": video_name,
        "model": f"{SUPERANIMAL_NAME}/{MODEL_NAME}",
        "bodyparts": bodyparts,
        "n_bodyparts": len(bodyparts),
        "total_frames": total_frames,
        "detected_frames": detected_frames,
        "detection_rate_pct": round(detected_frames / total_frames * 100, 1) if total_frames else 0,
        "avg_likelihood": round(float(np.mean(valid_lkh)) if valid_lkh else 0.0, 3),
        "keypoint_validity_pct": round(len(valid_lkh) / len(all_likelihoods) * 100, 1) if all_likelihoods else 0,
        "frames": frame_results,
    }


def run(video_dir: str, output_dir: str) -> None:
    """
    video_dir 안의 비디오 파일들에 SuperAnimal 추론 실행.
    (run_yolo.py와 달리 프레임 디렉토리가 아닌 비디오 파일 사용)
    """
    dlclibrary, deeplabcut, pandas = _check_deps()

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 모델 캐시 확인
    model_cache = PROJECT_ROOT / "data" / "models" / "superanimal"
    ensure_model_downloaded(model_cache)

    # 비디오 파일 탐색 (sample_XX/output.* 구조)
    video_root = Path(video_dir)
    video_files: List[Path] = []
    for sample_dir in sorted(video_root.iterdir()):
        if sample_dir.is_dir():
            vids = [
                f for f in sample_dir.iterdir()
                if f.suffix.lower() in (".mp4", ".mkv", ".avi", ".mov", ".webm")
                and f.stem == "output"
            ]
            video_files.extend(vids)

    if not video_files:
        print(f"❌ 비디오 파일 없음: {video_dir}")
        print("   download.py를 먼저 실행하세요.")
        return

    summary = {
        "model": f"{SUPERANIMAL_NAME}/{MODEL_NAME}",
        "detector": DETECTOR_NAME,
        "timestamp": datetime.now().isoformat(),
        "videos": {},
    }

    t_total = time.perf_counter()

    for video_path in video_files:
        video_name = video_path.parent.name  # sample_01, sample_02 ...
        print(f"\n처리: {video_name} ({video_path.name})")

        h5_path = run_inference_on_video(deeplabcut, video_path, out)
        if h5_path is None:
            summary["videos"][video_name] = {"error": "추론 실패"}
            continue

        metrics = parse_h5_to_metrics(pandas, h5_path, video_name, n_frames=0)
        summary["videos"][video_name] = metrics

        json_path = out / f"{video_name}_superanimal.json"
        json_path.write_text(
            json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        print(
            f"  탐지율: {metrics['detection_rate_pct']}%  |"
            f"  평균 likelihood: {metrics['avg_likelihood']}  |"
            f"  keypoint 유효율: {metrics['keypoint_validity_pct']}%"
        )

    summary["total_time_sec"] = round(time.perf_counter() - t_total, 1)
    (out / "superanimal_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n✅ SuperAnimal 결과 저장: {output_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description="SuperAnimal-Quadruped 강아지 자세 추정 벤치마크")
    parser.add_argument(
        "--video-dir",
        default=str(PROJECT_ROOT / "data/cache/compare/videos"),
        help="다운로드된 비디오 루트 디렉토리 (sample_XX/output.* 구조)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "data/cache/compare/superanimal_results"),
    )
    args = parser.parse_args()
    run(args.video_dir, args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
