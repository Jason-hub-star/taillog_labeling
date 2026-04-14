#!/usr/bin/env python3
"""
Backfill script: Import pose extraction results from JSON cache to SQLite DB.

Cache structure:
  - File: data/cache/pose_results/{run_id}_poses.json
  - Content: List[{frame_id, keypoints, confidence}]

DB schema:
  - labeling_runs(id, url, title, channel, duration_s, video_path, status, error_msg, ...)
  - pose_results(id, run_id, frame_id, keypoints_json, confidence, frame_path, ...)

Behavior:
  1. For each JSON file in data/cache/pose_results/
  2. Extract run_id from filename ({run_id}_poses.json)
  3. Ensure labeling_runs record exists (insert if not)
  4. Insert pose_results records from JSON (skip if UNIQUE constraint violated)
  5. Show progress: run_id: N imported, M skipped
  6. Support --dry-run and --run-id filters
"""

import json
import sqlite3
import argparse
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from typing import Optional, List, Tuple


class PoseBackfiller:
    def __init__(self, db_path: Path, cache_dir: Path, dry_run: bool = False):
        self.db_path = db_path
        self.cache_dir = cache_dir
        self.dry_run = dry_run
        self.conn = None
        self.cursor = None
        self.total_imported = 0
        self.total_skipped = 0
        self.total_runs = 0

    def connect(self):
        """Open database connection."""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def run_exists(self, run_id: str) -> bool:
        """Check if labeling_run record exists."""
        self.cursor.execute(
            "SELECT 1 FROM labeling_runs WHERE id = ?",
            (run_id,)
        )
        return self.cursor.fetchone() is not None

    def insert_labeling_run(self, run_id: str) -> bool:
        """Insert a new labeling_run record with placeholder values.

        Returns:
            True if inserted, False if already existed.
        """
        if self.run_exists(run_id):
            return False

        now = datetime.now(timezone.utc).isoformat()
        placeholder_url = f"https://youtube.com/watch?v={run_id}"
        placeholder_title = f"Video {run_id[:8]}"
        placeholder_channel = "unknown"
        placeholder_video_path = f"data/cache/youtube_videos/{run_id}.mp4"

        if self.dry_run:
            return True

        try:
            self.cursor.execute(
                """
                INSERT INTO labeling_runs (
                    id, url, title, channel, duration_s, video_path, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    placeholder_url,
                    placeholder_title,
                    placeholder_channel,
                    0.0,  # duration_s (placeholder)
                    placeholder_video_path,
                    "completed",
                    now,
                    now
                )
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # URL already exists (likely run_id collision)
            self.conn.rollback()
            return False

    def insert_pose_result(self, run_id: str, frame_data: dict) -> bool:
        """Insert a single pose_result record from JSON frame data.

        Args:
            run_id: The run ID
            frame_data: Dict with keys: frame_id, keypoints (list), confidence (float)

        Returns:
            True if inserted, False if skipped (already exists or error).
        """
        frame_id = frame_data["frame_id"]
        keypoints = frame_data["keypoints"]
        confidence = frame_data["confidence"]

        # Build frame_path
        frame_path = None
        expected_frame_path = Path("data/training/frames") / f"{frame_id:06d}.jpg"
        if expected_frame_path.exists():
            frame_path = str(expected_frame_path)

        # Serialize keypoints as JSON
        keypoints_json = json.dumps(keypoints)

        # Generate unique ID
        pose_result_id = str(uuid4())

        if self.dry_run:
            return True

        try:
            self.cursor.execute(
                """
                INSERT INTO pose_results (
                    id, run_id, frame_id, keypoints_json, confidence, frame_path, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pose_result_id,
                    run_id,
                    frame_id,
                    keypoints_json,
                    confidence,
                    frame_path,
                    datetime.now(timezone.utc).isoformat()
                )
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # UNIQUE(run_id, frame_id) violation - already exists
            self.conn.rollback()
            return False

    def process_json_file(self, json_path: Path) -> Tuple[str, int, int]:
        """Process a single JSON file from cache.

        Returns:
            (run_id, imported_count, skipped_count)
        """
        # Extract run_id from filename: {run_id}_poses.json
        run_id = json_path.stem.replace("_poses", "")

        # Load JSON
        try:
            with open(json_path, "r") as f:
                frames = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"  ERROR: Failed to load {json_path.name}: {e}")
            return run_id, 0, 0

        # Ensure labeling_run exists
        self.insert_labeling_run(run_id)

        # Process frames
        imported = 0
        skipped = 0

        for frame_data in frames:
            if self.insert_pose_result(run_id, frame_data):
                imported += 1
            else:
                skipped += 1

        return run_id, imported, skipped

    def backfill(self, run_id_filter: Optional[str] = None):
        """Main backfill process.

        Args:
            run_id_filter: If provided, only process this run_id.
        """
        # Find all JSON files
        json_files = sorted(self.cache_dir.glob("*_poses.json"))

        if not json_files:
            print(f"No JSON files found in {self.cache_dir}")
            return

        # Filter by run_id if specified
        if run_id_filter:
            json_files = [f for f in json_files if run_id_filter in f.name]
            if not json_files:
                print(f"No JSON files matching run_id={run_id_filter}")
                return

        print(f"Found {len(json_files)} JSON file(s) to process")
        if self.dry_run:
            print("DRY RUN MODE: No changes will be made to DB\n")
        else:
            print()

        # Process each file
        for json_path in json_files:
            run_id, imported, skipped = self.process_json_file(json_path)
            self.total_runs += 1
            self.total_imported += imported
            self.total_skipped += skipped

            status = "DRY RUN" if self.dry_run else ""
            print(f"{run_id}: {imported} imported, {skipped} skipped {status}".strip())

        # Print summary
        print("\n" + "=" * 60)
        print(f"Summary:")
        print(f"  Total runs processed: {self.total_runs}")
        print(f"  Total records imported: {self.total_imported}")
        print(f"  Total records skipped: {self.total_skipped}")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Backfill pose_results table from JSON cache",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/setup/backfill_pose_results.py --dry-run
  python scripts/setup/backfill_pose_results.py
  python scripts/setup/backfill_pose_results.py --run-id cda0767f-2257-4f47-a7db-d5278935b7fe
        """
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/databases/labeling.db"),
        help="Path to SQLite database (default: data/databases/labeling.db)"
    )

    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data/cache/pose_results"),
        help="Path to pose cache directory (default: data/cache/pose_results)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be imported without modifying DB"
    )

    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Only process this run_id (optional filter)"
    )

    args = parser.parse_args()

    # Resolve to absolute paths
    db_path = args.db.resolve()
    cache_dir = args.cache_dir.resolve()

    # Validate paths
    if not db_path.exists():
        print(f"ERROR: Database not found: {db_path}")
        return 1

    if not cache_dir.exists():
        print(f"ERROR: Cache directory not found: {cache_dir}")
        return 1

    # Run backfiller
    backfiller = PoseBackfiller(db_path, cache_dir, dry_run=args.dry_run)
    backfiller.connect()
    try:
        backfiller.backfill(run_id_filter=args.run_id)
    finally:
        backfiller.close()

    return 0


if __name__ == "__main__":
    exit(main())
