"""파이프라인 실행 CLI"""

import argparse
import os
import sys
from pathlib import Path
from typing import List

# 환경변수 로드
from dotenv import load_dotenv

load_dotenv(".env.local")

from src.core.database import init_db
from src.pipelines.orchestrator import Orchestrator


def load_urls_from_file(filepath: str = "urls.txt") -> List[str]:
    """urls.txt에서 URL 리스트 로드"""
    if not os.path.exists(filepath):
        return []

    urls = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if line and line.startswith("http"):
                urls.append(line)

    return urls


def main():
    parser = argparse.ArgumentParser(description="TailLog Labeling Pipeline")
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Single YouTube URL to process",
    )
    parser.add_argument(
        "--urls-file",
        type=str,
        default="urls.txt",
        help="File containing YouTube URLs (one per line)",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Maximum number of items to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run (no DB changes)",
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize database schema",
    )

    args = parser.parse_args()

    # 1. DB 초기화
    print("Initializing database...")
    init_db()
    print("✓ Database initialized")

    # 2. Orchestrator 생성
    orchestrator = Orchestrator()

    # 3. URL 수집
    urls = []
    if args.url:
        urls = [args.url]
    else:
        urls = load_urls_from_file(args.urls_file)

    if not urls:
        print("❌ No URLs provided")
        print("Usage: python src/pipelines/run.py --url <youtube_url>")
        print("       python src/pipelines/run.py --urls-file urls.txt")
        sys.exit(1)

    # 4. 파이프라인 실행
    print(f"\n{'='*60}")
    print(f"TailLog Labeling Pipeline")
    print(f"{'='*60}")
    print(f"URLs to process: {len(urls)}")
    if args.max_items:
        print(f"Max items: {args.max_items}")
    if args.dry_run:
        print("Mode: DRY RUN (no DB changes)")
    print(f"{'='*60}\n")

    results = orchestrator.run_batch_pipeline(
        urls,
        max_items=args.max_items,
        dry_run=args.dry_run,
    )

    # 5. 결과 리포트
    print(f"\n{'='*60}")
    print("PIPELINE SUMMARY")
    print(f"{'='*60}")
    print(f"Success: {results['success_count']}")
    print(f"Failed: {results['fail_count']}")
    print(f"Total: {results['success_count'] + results['fail_count']}")
    if results["run_ids"]:
        print(f"\nProcessed run IDs:")
        for run_id in results["run_ids"]:
            print(f"  - {run_id}")
    print(f"\nStart: {results['start_time']}")
    print(f"End: {results['end_time']}")
    print(f"{'='*60}\n")

    return 0 if results["fail_count"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
