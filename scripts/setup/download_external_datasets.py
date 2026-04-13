"""
외부 강아지 행동 데이터셋 다운로드 스크립트
용도: Phase 2 few-shot 샘플 준비 + Phase 3 파인튜닝 데이터 준비

실행:
  python3 scripts/setup/download_external_datasets.py --mode few_shot
  python3 scripts/setup/download_external_datasets.py --mode full
  python3 scripts/setup/download_external_datasets.py --dataset dog_emotion --mode few_shot

데이터 저장 위치:
  few-shot: data/external/few_shot_samples/<dataset>/
  full:     data/external/full_datasets/<dataset>/
"""
import argparse
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

OUTPUT_FEW_SHOT = ROOT / "data/external/few_shot_samples"
OUTPUT_FULL     = ROOT / "data/external/full_datasets"

# Phase 2 few-shot: 각 감정 카테고리당 최대 몇 장 샘플링할지
FEW_SHOT_PER_LABEL = 10


# ──────────────────────────────────────────────
# 1. Dog Emotion Dataset v2 (HuggingFace)
#    라벨: sad, angry, relaxed, happy
#    TailLog 매핑: cond_tired, alert_aggression, cond_good, cond_excited
# ──────────────────────────────────────────────
EMOTION_LABEL_MAP = {
    "happy":   "cond_good",
    "relaxed": "cond_good",
    "sad":     "cond_tired",
    "angry":   "alert_aggression",
}

def download_dog_emotion_v2(mode: str):
    try:
        from datasets import load_dataset
    except ImportError:
        print("datasets 패키지 필요: pip install datasets")
        return

    print("Dog Emotion Dataset v2 다운로드 중 (HuggingFace)...")
    ds = load_dataset("Dewa/Dog_Emotion_Dataset_v2", split="train")
    print(f"  전체: {len(ds)}건")

    out_dir = (OUTPUT_FEW_SHOT if mode == "few_shot" else OUTPUT_FULL) / "dog_emotion_v2"

    if mode == "few_shot":
        _save_few_shot(ds, out_dir, label_col="emotion", id2label=None)
    else:
        _save_full(ds, out_dir, label_col="emotion", id2label=None)


def _save_few_shot(ds, out_dir: Path, label_col: str, id2label):
    """카테고리별 FEW_SHOT_PER_LABEL장씩 저장 (TailLog preset 폴더로 분류)"""
    from collections import defaultdict
    buckets = defaultdict(list)

    for item in ds:
        orig_label = (id2label[item[label_col]] if id2label and isinstance(item[label_col], int)
                      else str(item[label_col]))
        preset = EMOTION_LABEL_MAP.get(orig_label.lower(), "unknown")
        if len(buckets[preset]) < FEW_SHOT_PER_LABEL:
            buckets[preset].append((item["image"], orig_label))

    saved = 0
    for preset, items in buckets.items():
        preset_dir = out_dir / preset
        preset_dir.mkdir(parents=True, exist_ok=True)
        for i, (img, orig) in enumerate(items):
            img_path = preset_dir / f"{orig}_{i:03d}.jpg"
            img.save(img_path)
            saved += 1

    print(f"  few-shot 저장 완료: {saved}장 → {out_dir}")
    _print_summary(out_dir)


def _save_full(ds, out_dir: Path, label_col: str, id2label):
    """전체 저장 (orig 라벨 폴더 구조 유지)"""
    saved = 0
    for i, item in enumerate(ds):
        orig_label = (id2label[item[label_col]] if id2label and isinstance(item[label_col], int)
                      else str(item[label_col]))
        label_dir = out_dir / orig_label
        label_dir.mkdir(parents=True, exist_ok=True)
        img_path = label_dir / f"{i:05d}.jpg"
        item["image"].save(img_path)
        saved += 1
        if saved % 500 == 0:
            print(f"  {saved}건 저장 중...")

    print(f"  전체 저장 완료: {saved}장 → {out_dir}")
    _print_summary(out_dir)


def _print_summary(out_dir: Path):
    if not out_dir.exists():
        return
    print("\n  [폴더별 이미지 수]")
    for d in sorted(out_dir.iterdir()):
        if d.is_dir():
            count = len(list(d.glob("*.jpg")))
            print(f"    {d.name:<25} {count}장")


# ──────────────────────────────────────────────
# 2. Kaggle 데이터셋 (인증 필요)
#    - ziya07/dog-behavior-monitoring-dataset
#    - georgemartvel/dogflw
#    - benjamingray44/inertial-data-for-dog-behaviour-classification
# ──────────────────────────────────────────────
KAGGLE_DATASETS = {
    "ziya07":    "ziya07/dog-behavior-monitoring-dataset",
    "dogflw":    "georgemartvel/dogflw",
    "imu":       "benjamingray44/inertial-data-for-dog-behaviour-classification",
}

def download_kaggle(dataset_key: str, mode: str):
    try:
        import kaggle  # noqa: F401
    except ImportError:
        print("kaggle 패키지 필요: pip install kaggle")
        print("Kaggle API 키 설정: ~/.kaggle/kaggle.json")
        print("  1. https://www.kaggle.com/account → Create New API Token")
        print("  2. 다운로드된 kaggle.json → ~/.kaggle/kaggle.json")
        return

    import subprocess
    dataset_id = KAGGLE_DATASETS[dataset_key]
    out_dir = (OUTPUT_FEW_SHOT if mode == "few_shot" else OUTPUT_FULL) / dataset_key
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"{dataset_id} 다운로드 중 (Kaggle)...")
    result = subprocess.run(
        ["kaggle", "datasets", "download", "-d", dataset_id, "-p", str(out_dir), "--unzip"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"  완료 → {out_dir}")
        # 폴더 크기
        total = sum(f.stat().st_size for f in out_dir.rglob("*") if f.is_file())
        print(f"  크기: {total / 1024 / 1024:.1f} MB")
    else:
        print(f"  오류: {result.stderr}")


# ──────────────────────────────────────────────
# 3. GitHub 기반 데이터셋 (git clone)
# ──────────────────────────────────────────────
GITHUB_DATASETS = {
    "decade":    "https://github.com/ehsanik/dogTorch",
    "rgbd_dog":  "https://github.com/CAMERA-Bath/RGBD-Dog",
    "sydog":     "https://github.com/mshooter/SyDogVideo_release",
}

def download_github(dataset_key: str):
    import subprocess
    url = GITHUB_DATASETS[dataset_key]
    out_dir = OUTPUT_FULL / dataset_key
    if out_dir.exists():
        print(f"  이미 존재: {out_dir} (스킵)")
        return
    print(f"{dataset_key} clone 중...")
    result = subprocess.run(["git", "clone", "--depth", "1", url, str(out_dir)],
                            capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  완료 → {out_dir}")
    else:
        print(f"  오류: {result.stderr}")


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────
DATASET_REGISTRY = {
    "dog_emotion":  {"fn": download_dog_emotion_v2,  "mode_aware": True,  "note": "HuggingFace, 4,000장, ~100MB"},
    "ziya07":       {"fn": lambda m: download_kaggle("ziya07", m),  "mode_aware": True,  "note": "Kaggle (인증 필요), 행동 계층 구조"},
    "dogflw":       {"fn": lambda m: download_kaggle("dogflw", m),  "mode_aware": True,  "note": "Kaggle (인증 필요), 얼굴 특징점 4,335장"},
    "imu":          {"fn": lambda m: download_kaggle("imu", m),     "mode_aware": True,  "note": "Kaggle (인증 필요), IMU 센서 데이터"},
    "decade":       {"fn": lambda _: download_github("decade"),     "mode_aware": False, "note": "GitHub, ego-centric 비디오"},
    "rgbd_dog":     {"fn": lambda _: download_github("rgbd_dog"),   "mode_aware": False, "note": "GitHub, RGB-D 포즈"},
    "sydog":        {"fn": lambda _: download_github("sydog"),      "mode_aware": False, "note": "GitHub, 합성 비디오 87,500프레임"},
}

def main():
    parser = argparse.ArgumentParser(description="외부 강아지 행동 데이터셋 다운로드")
    parser.add_argument("--dataset", choices=list(DATASET_REGISTRY.keys()) + ["all"],
                        default="dog_emotion", help="다운로드할 데이터셋")
    parser.add_argument("--mode", choices=["few_shot", "full"], default="few_shot",
                        help="few_shot: 라벨당 10장 샘플 / full: 전체 다운로드")
    parser.add_argument("--list", action="store_true", help="사용 가능한 데이터셋 목록 출력")
    args = parser.parse_args()

    if args.list:
        print("\n사용 가능한 데이터셋:")
        for key, info in DATASET_REGISTRY.items():
            print(f"  {key:<15} {info['note']}")
        return

    targets = list(DATASET_REGISTRY.keys()) if args.dataset == "all" else [args.dataset]

    for key in targets:
        info = DATASET_REGISTRY[key]
        print(f"\n{'='*50}")
        print(f"[{key}] {info['note']}")
        info["fn"](args.mode)

    print(f"\n완료. 저장 위치:")
    print(f"  few-shot: {OUTPUT_FEW_SHOT}")
    print(f"  full:     {OUTPUT_FULL}")


if __name__ == "__main__":
    main()
