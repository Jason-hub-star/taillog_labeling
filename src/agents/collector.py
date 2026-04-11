"""Collector 에이전트 — YouTube 영상 다운로드 및 메타데이터 수집"""

import os
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import uuid

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

from src.core.database import get_db
from src.core.models import LabelingRun


class Collector:
    """YouTube 영상 수집 에이전트"""

    def __init__(self, cache_dir: str = "data/cache/youtube_videos"):
        self.cache_dir = cache_dir
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        self.db = get_db()

    def run(self, url: str, dry_run: bool = False) -> Optional[LabelingRun]:
        """
        YouTube 영상 다운로드 및 라벨링 run 생성

        Args:
            url: YouTube URL
            dry_run: True면 DB 저장 안 함

        Returns:
            LabelingRun 객체 (성공) 또는 None (실패)
        """
        if yt_dlp is None:
            raise RuntimeError("yt-dlp 패키지 필요: pip install yt-dlp")

        # 1. 메타데이터 추출
        _TRANSIENT = (ConnectionError, TimeoutError, OSError)
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "format": "best[height>=480]/best",
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except _TRANSIENT as e:
            self._record_failure(url, f"메타 추출 실패 (transient): {str(e)}")
            return None
        except Exception as e:
            # permanent: 잘못된 URL, 비공개 영상, 저작권 차단 등
            self._record_failure(url, f"메타 추출 실패 (permanent): {str(e)}")
            return None

        # 2. 영상 품질 확인 (해상도, 길이)
        duration_s = info.get("duration", 0)
        if duration_s < 10 or duration_s > 600:
            self._record_failure(url, f"길이 부적합: {duration_s}초 (10~600초 필요)")
            return None

        # 3. 다운로드
        video_path = self._download_video(url, info)
        if not video_path:
            return None

        # 4. DB에 기록
        run_id = str(uuid.uuid4())
        run = LabelingRun(
            id=run_id,
            url=url,
            title=info.get("title", "Unknown"),
            channel=info.get("channel", "Unknown"),
            duration_s=duration_s,
            video_path=video_path,
            status="collected",
            created_at=datetime.utcnow(),
        )

        if not dry_run:
            try:
                self.db.insert(
                    """
                    INSERT INTO labeling_runs
                    (id, url, title, channel, duration_s, video_path, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run.id,
                        run.url,
                        run.title,
                        run.channel,
                        run.duration_s,
                        run.video_path,
                        run.status,
                        run.created_at.isoformat(),
                    ),
                )
            except Exception as e:
                self._record_failure(url, f"DB INSERT 실패: {str(e)}")
                return None

        return run

    def _download_video(self, url: str, info: Dict) -> Optional[str]:
        """yt-dlp로 영상 다운로드"""
        _TRANSIENT = (ConnectionError, TimeoutError, OSError)
        try:
            video_id = info.get("id", "unknown")
            output_path = os.path.join(self.cache_dir, f"{video_id}.mp4")

            if os.path.exists(output_path):
                return output_path

            ydl_opts = {
                "format": "best[height>=480]/best",
                "outtmpl": os.path.join(self.cache_dir, "%(id)s.%(ext)s"),
                "quiet": False,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            if os.path.exists(output_path):
                return output_path
            return None
        except _TRANSIENT as e:
            print(f"다운로드 실패 (transient, 재시도 가능): {str(e)}")
            return None
        except Exception as e:
            print(f"다운로드 실패 (permanent): {str(e)}")
            return None

    def _record_failure(self, url: str, error_msg: str):
        """실패 기록"""
        run_id = str(uuid.uuid4())
        self.db.insert(
            """
            INSERT INTO labeling_runs
            (id, url, title, channel, duration_s, video_path, status, error_msg, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                url,
                "Failed",
                "Unknown",
                0,
                "",
                "failed",
                error_msg,
                datetime.utcnow().isoformat(),
            ),
        )
