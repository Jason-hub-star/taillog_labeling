"""이미지 로드 및 base64 인코딩 유틸리티"""

import base64
from pathlib import Path
from typing import Optional


def load_frame_image(frame_path: str | Path) -> Optional[bytes]:
    """프레임 JPEG 로드. 파일 없거나 읽기 불가 시 None 반환."""
    path = Path(frame_path)
    if not path.exists():
        return None
    try:
        return path.read_bytes()
    except (PermissionError, IsADirectoryError) as e:
        print(f"[WARN] 이미지 접근 불가 ({type(e).__name__}): {frame_path}")
        return None
    except OSError as e:
        print(f"[WARN] 이미지 읽기 오류: {frame_path} — {e}")
        return None


def image_to_base64(image_bytes: bytes) -> str:
    """JPEG 바이너리 → base64 문자열 (Ollama images 필드용)"""
    return base64.b64encode(image_bytes).decode("utf-8")
