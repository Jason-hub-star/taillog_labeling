#!/usr/bin/env python3
"""
YouTube 영상 자동 검색 — 비교 테스트 & collector 에이전트 공용
검증된 API: yt_dlp extract_flat (다운로드 없이 메타데이터만 수집)

용도:
  1. 비교 테스트 (OD-07): 5종 검색어 → urls.txt 자동 생성
  2. collector 에이전트: search_videos() 함수 import해서 재사용

사용법:
  python scripts/compare/search_videos.py                  # 기본 5종 검색
  python scripts/compare/search_videos.py --per-query 3   # 종당 3개
  python scripts/compare/search_videos.py --queries "비글 일상" "진돗개 산책"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ──────────────────────────────────────────────
# YOUTUBE-SOURCE-POLICY.md 기준 필터 설정
# ──────────────────────────────────────────────
DURATION_MIN = 60    # 최소 60초
DURATION_MAX = 600   # 최대 10분
EXCLUDE_KEYWORDS = [
    "compilation", "best of", "highlights", "funny moments",
    "top 10", "remix", "animation", "cartoon", "cgv",
]

# 비교 테스트용 기본 검색어 5종
DEFAULT_QUERIES = [
    "포메라니안 일상",   # 소형견 일상
    "말티즈 산책",       # 소형견 산책
    "골든 리트리버 일상", # 대형견
    "강아지 두마리",     # 다중 강아지
    "강아지 홈캠",       # 고정 카메라
]


def _is_valid(entry: Dict) -> tuple[bool, str]:
    """
    단일 검색 결과가 정책 조건을 충족하는지 확인.
    반환: (통과 여부, 사유)
    """
    title = (entry.get("title") or "").lower()
    duration = entry.get("duration")
    url = entry.get("url") or entry.get("webpage_url") or ""

    if not url:
        return False, "URL 없음"

    if duration is None:
        return False, "길이 정보 없음"

    if duration < DURATION_MIN:
        return False, f"너무 짧음 ({duration}초 < {DURATION_MIN}초)"

    if duration > DURATION_MAX:
        return False, f"너무 긺 ({duration}초 > {DURATION_MAX}초)"

    for kw in EXCLUDE_KEYWORDS:
        if kw in title:
            return False, f"제외 키워드 포함: '{kw}'"

    return True, "OK"


def search_videos(
    queries: List[str],
    per_query: int = 1,
    search_pool: int = 10,
) -> Dict[str, List[Dict]]:
    """
    검색어 리스트로 YouTube 영상 검색.
    collector 에이전트에서 import해서 재사용 가능.

    Args:
        queries: 검색어 목록
        per_query: 검색어당 반환할 영상 수
        search_pool: 검색어당 후보 풀 크기 (필터링 전)

    Returns:
        {검색어: [{"url", "title", "duration", "channel", "view_count"}, ...]}
    """
    try:
        import yt_dlp
    except ImportError:
        print("❌ yt_dlp 미설치: pip install yt-dlp")
        raise SystemExit(1)

    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "no_warnings": True,
        "ignoreerrors": True,
    }

    results: Dict[str, List[Dict]] = {}
    seen_urls: set = set()  # 중복 URL 방지

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for query in queries:
            print(f"\n검색: '{query}'")
            candidates = []

            try:
                search_query = f"ytsearch{search_pool}:{query}"
                info = ydl.extract_info(search_query, download=False)
                entries = info.get("entries") or []
            except Exception as e:
                print(f"  ❌ 검색 실패: {e}")
                results[query] = []
                continue

            for entry in entries:
                if not entry:
                    continue

                url = entry.get("url") or entry.get("webpage_url") or ""
                # youtube.com 전체 URL로 변환
                if url and not url.startswith("http"):
                    url = f"https://www.youtube.com/watch?v={url}"

                if url in seen_urls:
                    continue

                valid, reason = _is_valid({**entry, "url": url})
                if not valid:
                    print(f"  ✗ 제외 [{reason}]: {entry.get('title', '')[:40]}")
                    continue

                candidate = {
                    "url": url,
                    "title": entry.get("title", ""),
                    "duration": entry.get("duration"),
                    "channel": entry.get("channel") or entry.get("uploader", ""),
                    "view_count": entry.get("view_count"),
                    "query": query,
                }
                candidates.append(candidate)
                print(f"  ✓ [{entry.get('duration')}초] {entry.get('title', '')[:50]}")

                if len(candidates) >= per_query:
                    break

            if not candidates:
                print(f"  ⚠️ 조건 충족 영상 없음 — 대안 검색어 시도: '{query} 강아지'")
                # 대안 검색어로 재시도
                try:
                    alt_info = ydl.extract_info(f"ytsearch{search_pool}:{query} 강아지", download=False)
                    for entry in (alt_info.get("entries") or []):
                        if not entry:
                            continue
                        url = entry.get("url") or entry.get("webpage_url") or ""
                        if url and not url.startswith("http"):
                            url = f"https://www.youtube.com/watch?v={url}"
                        if url in seen_urls:
                            continue
                        valid, reason = _is_valid({**entry, "url": url})
                        if valid:
                            candidates.append({
                                "url": url,
                                "title": entry.get("title", ""),
                                "duration": entry.get("duration"),
                                "channel": entry.get("channel") or entry.get("uploader", ""),
                                "view_count": entry.get("view_count"),
                                "query": query,
                            })
                            if len(candidates) >= per_query:
                                break
                except Exception:
                    pass

            for c in candidates[:per_query]:
                seen_urls.add(c["url"])

            results[query] = candidates[:per_query]
            found = len(results[query])
            print(f"  → {found}/{per_query}개 수집")

    return results


def save_results(
    results: Dict[str, List[Dict]],
    urls_path: Path,
    json_path: Path,
) -> int:
    """결과를 urls.txt와 search_results.json으로 저장. 수집된 URL 수 반환."""
    urls_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    all_urls = []
    lines = [
        "# TailLog 비교 테스트용 YouTube 영상 목록\n",
        f"# 자동 생성: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
        "# 사용법: bash scripts/compare/run_all.sh urls.txt\n\n",
    ]

    for query, videos in results.items():
        lines.append(f"# ── {query} ──\n")
        if not videos:
            lines.append("# (검색 결과 없음)\n")
        for v in videos:
            mins = v["duration"] // 60 if v["duration"] else 0
            secs = v["duration"] % 60 if v["duration"] else 0
            lines.append(f"{v['url']}  # {v['title'][:40]} ({mins}분{secs}초)\n")
            all_urls.append(v["url"])
        lines.append("\n")

    urls_path.write_text("".join(lines), encoding="utf-8")

    summary = {
        "generated_at": datetime.now().isoformat(),
        "total_urls": len(all_urls),
        "queries": {q: v for q, v in results.items()},
    }
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return len(all_urls)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="YouTube 강아지 영상 자동 검색 → urls.txt 생성"
    )
    parser.add_argument(
        "--queries", nargs="+",
        default=DEFAULT_QUERIES,
        help="검색어 목록 (기본: 비교 테스트 5종)",
    )
    parser.add_argument(
        "--per-query", type=int, default=1,
        help="검색어당 수집할 영상 수 (기본: 1)",
    )
    parser.add_argument(
        "--search-pool", type=int, default=10,
        help="검색어당 후보 풀 크기 (기본: 10)",
    )
    parser.add_argument(
        "--urls-out",
        default=str(PROJECT_ROOT / "urls.txt"),
        help="urls.txt 저장 경로",
    )
    parser.add_argument(
        "--json-out",
        default=str(PROJECT_ROOT / "data/cache/compare/search_results.json"),
        help="메타데이터 JSON 저장 경로",
    )
    args = parser.parse_args()

    print("══════════════════════════════════════")
    print("  TailLog YouTube 영상 자동 검색")
    print("══════════════════════════════════════")
    print(f"검색어 {len(args.queries)}종 × {args.per_query}개 = 최대 {len(args.queries) * args.per_query}개\n")

    results = search_videos(
        queries=args.queries,
        per_query=args.per_query,
        search_pool=args.search_pool,
    )

    urls_path = Path(args.urls_out)
    json_path = Path(args.json_out)
    total = save_results(results, urls_path, json_path)

    print(f"\n══════════════════════════════════════")
    print(f"✅ 완료: {total}개 URL 수집")
    print(f"   urls.txt → {urls_path}")
    print(f"   메타데이터 → {json_path}")

    if total == 0:
        print("\n⚠️ 수집된 영상이 없어요. 검색어를 바꿔서 다시 시도해보세요.")
        print("   예: python scripts/compare/search_videos.py --queries '강아지 일상' '개 산책'")
        return 1

    print(f"\n다음 단계:")
    print(f"  bash scripts/compare/run_all.sh {urls_path}")
    print("══════════════════════════════════════")
    return 0


if __name__ == "__main__":
    sys.exit(main())
