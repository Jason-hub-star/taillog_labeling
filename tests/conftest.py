"""pytest 설정"""

import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def temp_db():
    """임시 SQLite DB"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    # cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def temp_dir():
    """임시 디렉토리"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir
