#!/usr/bin/env python3
"""
검증된 API 기반 재작성 (2026-04-11)
- 다운로드: yt_dlp.YoutubeDL (Python 패키지 직접 사용)
- 핵심 설정: external_downloader=ffmpeg, external_downloader_args=[-ss,0,-to,60]
- 핵심 설정: format=bestvideo[height<=480]+bestaudio/best[height<=480], outtmpl=output.%(ext)s
- 후처리: ffmpeg로 1FPS 프레임 추출
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VIDEO_DIR = (PROJECT_ROOT / "data" / "cache" / "compare" / "videos").resolve()
DEFAULT_FRAME_DIR = (PROJECT_ROOT / "data" / "cache" / "compare" / "frames").resolve()


def _read_urls(args: argparse.Namespace) -> List[str]:
    """CLI 입력에서 URL 목록을 읽고 중복/빈 줄을 정리한다."""
    urls: List[str] = []

    if args.urls:
        urls.extend([u.strip() for u in args.urls if u.strip()])

    if args.urls_file:
        url_file = Path(args.urls_file).expanduser().resolve()
        if not url_file.is_file():
            raise FileNotFoundError(f"URL 파일을 찾을 수 없습니다: {url_file}")
        lines = [line.strip() for line in url_file.read_text(encoding="utf-8").splitlines()]
        urls.extend([line for line in lines if line and not line.startswith("#")])

    unique_urls = list(dict.fromkeys(urls))
    return unique_urls


def _download_single_clip(url: str, target_dir: Path) -> Path:
    """
    단일 URL에서 60초 클립을 다운로드한다.

    요구사항에 맞춰 yt_dlp Python API만 사용한다(서브프로세스 다운로드 금지).
    outtmpl을 output.%(ext)s로 고정하기 위해 URL별 전용 폴더를 사용한다.
    """
    try:
        import yt_dlp
    except ImportError as exc:
        print("❌ `yt_dlp` 패키지가 필요합니다.")
        print("   설치: pip install yt-dlp")
        raise SystemExit(1) from exc

    target_dir.mkdir(parents=True, exist_ok=True)
    output_template = str((target_dir / "output.%(ext)s").resolve())

    ydl_opts = {
        "format": "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "outtmpl": output_template,
        "noplaylist": True,
        "external_downloader": "ffmpeg",
        "external_downloader_args": ["-ss", "0", "-to", "60"],
        "quiet": False,
        "no_warnings": False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # download()는 성공 시 0 반환, 실패 시 예외를 던질 수 있다.
            ret_code = ydl.download([url])
            if ret_code != 0:
                raise RuntimeError(f"yt_dlp 반환 코드 비정상: {ret_code}")
    except Exception as exc:
        print(f"❌ 다운로드 실패: {url}")
        print("   점검 항목:")
        print("   1) URL 접근 가능 여부")
        print("   2) ffmpeg 설치 여부 (external_downloader에 필요)")
        print("   3) yt-dlp 최신 버전 여부")
        print("   설치: pip install -U yt-dlp")
        raise RuntimeError("yt_dlp 다운로드 실패") from exc

    candidates = [
        p
        for p in target_dir.glob("output.*")
        if p.is_file() and p.suffix not in {".part", ".ytdl"}
    ]
    if not candidates:
        raise FileNotFoundError(f"다운로드 결과 파일(output.*)을 찾지 못했습니다: {target_dir}")

    # outtmpl이 output.* 형태이므로 일반적으로 1개 파일이 생성된다.
    return sorted(candidates)[0].resolve()


def _extract_frames_1fps(video_path: Path, frame_dir: Path) -> int:
    """
    ffmpeg로 영상에서 1FPS 프레임을 추출한다.
    다운로드 단계에서 이미 60초로 잘렸으므로 여기서는 fps만 지정한다.
    """
    frame_dir.mkdir(parents=True, exist_ok=True)
    output_pattern = str((frame_dir / "frame_%04d.jpg").resolve())

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        "fps=1",
        output_pattern,
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        print("❌ ffmpeg 명령을 찾을 수 없습니다.")
        print("   macOS: brew install ffmpeg")
        print("   Ubuntu/Debian: sudo apt-get install ffmpeg")
        raise RuntimeError("ffmpeg 미설치") from exc

    if proc.returncode != 0:
        print("❌ ffmpeg 프레임 추출 실패")
        stderr = (proc.stderr or "").strip()
        if stderr:
            print("   ffmpeg 오류:")
            print(f"   {stderr.splitlines()[-1]}")
        raise RuntimeError("ffmpeg 프레임 추출 실패")

    frames = sorted(frame_dir.glob("frame_*.jpg"))
    return len(frames)


def run(urls: List[str], video_root: Path, frame_root: Path) -> Dict[str, Dict[str, str]]:
    """URL 목록을 처리하고 다운로드/프레임 추출 결과를 사전으로 반환한다."""
    if not urls:
        raise ValueError("URL 목록이 비어 있습니다.")

    video_root.mkdir(parents=True, exist_ok=True)
    frame_root.mkdir(parents=True, exist_ok=True)

    results: Dict[str, Dict[str, str]] = {}

    for idx, url in enumerate(urls, start=1):
        item_name = f"sample_{idx:02d}"
        print(f"\n[{idx}/{len(urls)}] 처리 시작: {url}")

        target_video_dir = (video_root / item_name).resolve()
        target_frame_dir = (frame_root / item_name).resolve()

        try:
            video_path = _download_single_clip(url=url, target_dir=target_video_dir)
            frame_count = _extract_frames_1fps(video_path=video_path, frame_dir=target_frame_dir)
            results[item_name] = {
                "url": url,
                "video_path": str(video_path),
                "frame_dir": str(target_frame_dir),
                "frame_count": str(frame_count),
            }
            print(f"  ✅ 완료: {video_path.name}, 추출 프레임 {frame_count}장")
        except Exception as exc:
            results[item_name] = {
                "url": url,
                "error": str(exc),
            }
            print(f"  ❌ 실패: {exc}")

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="yt_dlp + ffmpeg 기반 60초 클립 다운로드 및 1FPS 프레임 추출")
    parser.add_argument("--urls", nargs="+", help="YouTube URL 목록")
    parser.add_argument("--urls-file", help="URL 목록 텍스트 파일(한 줄당 1개 URL)")
    parser.add_argument("--video-dir", default=str(DEFAULT_VIDEO_DIR), help="다운로드 비디오 저장 폴더")
    parser.add_argument("--frame-dir", default=str(DEFAULT_FRAME_DIR), help="프레임 저장 폴더")
    parser.add_argument("--summary-json", default=str((PROJECT_ROOT / "data" / "cache" / "compare" / "download_summary.json").resolve()))
    args = parser.parse_args()

    try:
        urls = _read_urls(args)
    except Exception as exc:
        print(f"❌ URL 입력 처리 실패: {exc}")
        return 1

    if not urls:
        print("❌ URL이 없습니다. --urls 또는 --urls-file 로 입력해 주세요.")
        return 1

    video_root = Path(args.video_dir).expanduser().resolve()
    frame_root = Path(args.frame_dir).expanduser().resolve()
    summary_path = Path(args.summary_json).expanduser().resolve()
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    results = run(urls=urls, video_root=video_root, frame_root=frame_root)

    summary = {
        "video_root": str(video_root),
        "frame_root": str(frame_root),
        "total": len(urls),
        "success": sum(1 for v in results.values() if "video_path" in v),
        "results": results,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n요약 저장: {summary_path}")
    if summary["success"] == 0:
        print("❌ 모든 항목이 실패했습니다. 위 에러 메시지를 확인해 주세요.")
        return 1

    print(f"✅ 완료: {summary['success']}/{summary['total']} 성공")
    return 0


if __name__ == "__main__":
    sys.exit(main())
